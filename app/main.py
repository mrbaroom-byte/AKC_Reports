"""منصة البيانات الربعية — Alkhabeer Capital quarterly statements for the capital-market funds."""
import os, json, re, hmac, hashlib, threading, traceback, datetime, mimetypes, zipfile, io
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from urllib.parse import urlparse
import time
from itsdangerous import URLSafeTimedSerializer, BadSignature
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
import compare as CMP
import mimetypes as _mt; _mt.add_type('image/webp', '.webp')
import model as M, store, pipeline as P, records as R, backup as BK, xl, shutil, i18n, audit as A, ai, intake as IN, commentary as CM, assistant as AS
from jinja2 import BaseLoader, TemplateNotFound

APP = os.path.dirname(os.path.abspath(__file__))
ENG = P.ENG
def _secret():
    if os.environ.get('SESSION_SECRET'): return os.environ['SESSION_SECRET']
    f = os.path.join(store.DATA, '.session_secret')
    if not os.path.exists(f):
        import secrets; open(f, 'w').write(secrets.token_hex(32)); os.chmod(f, 0o600)
    return open(f).read().strip()
SECRET = _secret()
SER = URLSafeTimedSerializer(SECRET, salt='akc-q-session')
DOC_CENTRE = os.environ.get('DOC_CENTRE_URL', 'https://claude.ai/artifact/7bddTJzzSApLduLWWzKwXv')
SEED_Q = 'q2-2026'
class _EnLoader(FileSystemLoader):
    """Same templates, interface text translated to English when loaded (statement content is passed in at render time)."""
    def get_source(self, environment, template):
        src, path, up = super().get_source(environment, template)
        return i18n.source(src), path, up


env = Environment(loader=FileSystemLoader(os.path.join(APP, 'templates')), autoescape=select_autoescape(['html']))
env_en = Environment(loader=_EnLoader(os.path.join(APP, 'templates')), autoescape=select_autoescape(['html']))
LANGS, THEMES = ('ar', 'en'), ('system', 'light', 'dark')


def lang_of(req):
    v = req.cookies.get('lang') if req is not None else None
    return v if v in LANGS else 'ar'


def theme_of(req):
    v = req.cookies.get('theme') if req is not None else None
    return v if v in THEMES else 'system'


def page(req, _tpl, **ctx):
    """Render a page in the viewer's language and theme."""
    lang = lang_of(req)
    ctx = i18n.deep(ctx, lang)
    ctx.update(lang=lang, dir='rtl' if lang == 'ar' else 'ltr', theme=theme_of(req), here=str(req.url.path) + (('?' + req.url.query) if req.url.query else ''),
               t=lambda x: i18n.T(x, lang), alt_lang='en' if lang == 'ar' else 'ar', ai_on=ai.configured())
    return (env_en if lang == 'en' else env).get_template(_tpl).render(**ctx)


def _js(v):
    """JSON safe to place inside <script>: no «</script>» or HTML comment can close the block early."""
    return json.dumps(v, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


for _e in (env, env_en): _e.filters['js'] = lambda v: Markup(_js(v))
APP_EN_JS = i18n.source(open(os.path.join(APP, 'static', 'app.js'), encoding='utf-8').read())
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static', StaticFiles(directory=os.path.join(APP, 'static')), name='static')
JOBS = {}
ACTORS = {}   # job key -> who started it, for the audit row written when the job ends
RENDER = threading.Lock()   # the engine renders through shared folders, so one document set is built at a time


_TR_KEYS = {'msg', 'status', 'step', 'notes', 'log', 'what', 'label'}


def _tr_json(v, lang, key=''):
    if isinstance(v, dict): return {k: _tr_json(x, lang, k) for k, x in v.items()}
    if isinstance(v, list): return [_tr_json(x, lang, key) for x in v]
    if isinstance(v, str) and key in _TR_KEYS: return i18n.T(v, lang)
    return v


@app.middleware('http')
async def guard(req: Request, call_next):
    t0 = time.time(); req.state.rid = req.headers.get('x-request-id', '')[:32] or A.new_rid()
    req.state.user = who(req) if not req.url.path.startswith('/static/') else None
    # writes only from this site (blocks cross-site form posts)
    if req.method == 'POST':
        src = req.headers.get('origin') or req.headers.get('referer')
        if src and urlparse(src).netloc != req.headers.get('host'):
            A.log(req, 'auth.origin', req.url.path, 'denied', origin=src)
            return JSONResponse({'error': 'origin', 'msg': i18n.T('طلب من خارج الموقع.', lang_of(req))}, status_code=403)
    r = await call_next(req)
    lang = lang_of(req)
    if lang == 'en' and req.url.path.startswith('/api/') and r.headers.get('content-type', '').startswith('application/json'):
        body = b''.join([c async for c in r.body_iterator])
        try: r = JSONResponse(_tr_json(json.loads(body), lang), status_code=r.status_code, headers={k: v for k, v in r.headers.items() if k.lower() not in ('content-length', 'content-type')})
        except ValueError: r = Response(body, status_code=r.status_code, headers=dict(r.headers))
    r.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    r.headers.setdefault('X-Content-Type-Options', 'nosniff')
    r.headers.setdefault('Referrer-Policy', 'same-origin')
    r.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    r.headers['X-Request-ID'] = req.state.rid
    if os.environ.get('RAILWAY_ENVIRONMENT'): r.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    if req.url.path.startswith('/static/'): r.headers['Cache-Control'] = 'public, max-age=86400'
    elif req.url.path not in ('/health',):
        r.headers.setdefault('Cache-Control', 'no-store')
        A.access(req, r.status_code, int((time.time() - t0) * 1000))
    return r


# ---------- auth ----------
ROLE_AR = {'admin': 'المعتمِد', 'editor': 'مُدخل البيانات'}


def who(req: Request):
    """{'user','name','role'} for a signed-in viewer, else None."""
    tok = req.cookies.get('akcq')
    if not tok: return None
    try: u = SER.loads(tok, max_age=60 * 60 * 12)
    except BadSignature: return None
    if isinstance(u, str): u = {'user': 'admin', 'name': 'المعتمِد', 'role': 'admin'}
    if u.get('role') != 'admin':
        if not any(x['username'] == u['user'] and x['active'] for x in store.users()): return None
    return u


def need(req: Request, role=None):
    u = who(req)
    if not u: raise HTTPException(status_code=401)
    if role and u['role'] != role: raise HTTPException(status_code=403)
    return u


@app.exception_handler(401)
async def _401(req, exc):
    if req.url.path.startswith('/api/'): return JSONResponse({'error': 'login'}, status_code=401)
    return RedirectResponse('/login', status_code=303)


@app.exception_handler(403)
async def _403(req, exc):
    A.log(req, 'auth.denied', req.url.path, 'denied')
    lang = lang_of(req)
    if req.url.path.startswith('/api/'): return JSONResponse({'error': 'forbidden', 'msg': i18n.T('هذا الإجراء للمعتمِد فقط.', lang)}, status_code=403)
    return HTMLResponse(f'<p style="font-family:sans-serif;padding:24px" dir="{"rtl" if lang == "ar" else "ltr"}">{i18n.T("هذه الصفحة للمعتمِد فقط.", lang)} <a href="/">{i18n.T("العودة", lang)}</a></p>', status_code=403)


@app.get('/login', response_class=HTMLResponse)
def login_page(req: Request, e: str = ''):
    return page(req, 'login.html', err=e, configured=bool(os.environ.get('ADMIN_PASSWORD')))


def _set(resp, u):
    resp.set_cookie('akcq', SER.dumps(u), httponly=True, secure=os.environ.get('RAILWAY_ENVIRONMENT') is not None, samesite='lax', max_age=60 * 60 * 12)
    return resp


FAILS = {}   # ip -> [time of each failed sign-in in the last 15 minutes]


def _throttled(ip):
    t = time.time(); FAILS[ip] = [x for x in FAILS.get(ip, []) if t - x < 900]
    return len(FAILS[ip]) >= 8


@app.post('/login')
def login(req: Request, password: str = Form(...), username: str = Form('')):
    ip = req.client.host if req.client else '-'
    uname = (username or '').strip().lower() or 'admin'
    if _throttled(ip):
        A.log(req, 'auth.throttled', uname, 'denied', _actor=uname); return RedirectResponse('/login?e=2', status_code=303)
    r = _login(username, password)
    if r is None:
        FAILS.setdefault(ip, []).append(time.time()); A.log(req, 'auth.login_failed', uname, 'failed', _actor=uname)
        return RedirectResponse('/login?e=1', status_code=303)
    FAILS.pop(ip, None)
    A.log(req, 'auth.login', uname, actor={'user': uname, 'role': 'admin' if uname == 'admin' else 'editor'}); return r


def _login(username, password):
    username = (username or '').strip().lower()
    if username in ('', 'admin'):
        pw = os.environ.get('ADMIN_PASSWORD', '').strip().strip('"').strip("'").strip()
        if pw and hmac.compare_digest(password.strip().encode(), pw.encode()):
            return _set(RedirectResponse('/', status_code=303), {'user': 'admin', 'name': 'المعتمِد', 'role': 'admin'})
        return None
    r = store.check_user(username, password.strip().upper())
    if not r: return None
    return _set(RedirectResponse('/', status_code=303), {'user': r['username'], 'name': r['name'], 'role': r['role']})


@app.get('/logout')
def logout(req: Request):
    if req.state.user: A.log(req, 'auth.logout', req.state.user.get('user', ''))
    r = RedirectResponse('/login', status_code=303); r.delete_cookie('akcq'); return r


# ---------- preferences: language and theme ----------
@app.get('/pref')
def pref(req: Request, lang: str = '', theme: str = '', next: str = '/'):
    nxt = next if next.startswith('/') and not next.startswith('//') else '/'
    r = RedirectResponse(nxt, status_code=303)
    secure = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    if lang in LANGS:
        r.set_cookie('lang', lang, max_age=365 * 86400, samesite='lax', secure=secure)
        if req.state.user: A.log(req, 'pref.lang', lang)
    if theme in THEMES:
        r.set_cookie('theme', theme, max_age=365 * 86400, samesite='lax', secure=secure)
    return r


@app.get('/i18n/app.en.js')
def app_en_js():
    return Response(APP_EN_JS, media_type='application/javascript', headers={'Cache-Control': 'public, max-age=3600'})


@app.get('/users', response_class=HTMLResponse)
def users_page(req: Request, new: str = '', pw: str = ''):
    u = need(req, 'admin')
    return page(req, 'users.html', me=u, nav='users', users=store.users(), roles=ROLE_AR, new=new, pw=pw)


@app.post('/users')
def users_add(req: Request, username: str = Form(...), name: str = Form(...)):
    need(req, 'admin')
    username = re.sub(r'[^a-z0-9._-]', '', username.strip().lower())[:40]
    if not username or username == 'admin': return RedirectResponse('/users', status_code=303)
    pw = store.create_user(username, name.strip()[:80], 'editor')
    A.log(req, 'user.create', username, name=name.strip()[:80], role='editor')
    # the one-time password is shown on the next page only; it is never stored in clear
    return HTMLResponse(page(req, 'users.html', me=who(req), nav='users', users=store.users(), roles=ROLE_AR, new=username, pw=pw), headers={'Cache-Control': 'no-store'})


@app.post('/users/{username}/toggle')
def users_toggle(req: Request, username: str):
    need(req, 'admin')
    cur = next((x for x in store.users() if x['username'] == username), None)
    if cur:
        store.set_active(username, not cur['active']); A.log(req, 'user.toggle', username, active=not cur['active'])
    return RedirectResponse('/users', status_code=303)


@app.post('/users/{username}/reset')
def users_reset(req: Request, username: str):
    need(req, 'admin')
    cur = next((x for x in store.users() if x['username'] == username), None)
    if not cur: return RedirectResponse('/users', status_code=303)
    pw = store.create_user(username, cur['name'], cur['role'])
    A.log(req, 'user.reset', username)
    return HTMLResponse(page(req, 'users.html', me=who(req), nav='users', users=store.users(), roles=ROLE_AR, new=username, pw=pw), headers={'Cache-Control': 'no-store'})


@app.get('/health')
def health():
    # whether the AI key works is reported, the key itself never is
    return {'ok': True, 'ai': {'configured': ai.configured(), 'ok': ai.STATUS['ok'], 'checked': ai.STATUS['checked'], 'model': ai.MODEL,
                               'detail': ai.STATUS['detail'][:160] if ai.STATUS['ok'] is False else ai.STATUS['detail']}}


# ---------- quarter helpers ----------
def current_q():
    """The quarter whose statement is due: the last quarter that has ended."""
    t = datetime.date.today(); qn = (t.month - 1) // 3 + 1
    return f'q{qn - 1}-{t.year}' if qn > 1 else f'q4-{t.year - 1}'


def base(fund, q):
    """Previous quarter's structs (AR, EN): the finalised statement of the previous quarter, else the published seed."""
    pq = M.prev_q(q); out = {}
    for lang in ('ar', 'en'):
        p = store.struct_path(fund, pq, lang)
        if not os.path.exists(p) and pq == SEED_Q:
            p = os.path.join(ENG, M.FUNDS[fund]['dir'], 'struct', f'{pq}.{lang}.json')
        if not os.path.exists(p): return None, pq
        out[lang] = json.load(open(p, encoding='utf-8'))
    return out, pq


def prev_values(fund, q):
    b, pq = base(fund, q)
    if not b: return None, pq, None
    v = M.extract(b['ar'], b['en'], fund)
    ps = store.get(fund, pq)
    if ps and ps.get('data'): v['valuation_date'] = ps['data'].get('valuation_date')
    return v, pq, b


def blank(prev, fund, q):
    """New quarter's starting data: names and fixed items from the previous quarter, figures empty."""
    F = M.FUNDS[fund]; qn, y = M.qparse(q); end = M.qend(qn, y)
    d = {'valuation_date': end.isoformat(), 'nav_unit': None, 'fund_size': None, 'units': None, 'avg_nav': None,
         'ter_amount': None, 'borrowing': None, 'dealing': None, 'mgr_invest': None, 'wad_days': None,
         'dist_total': None, 'dist_units': None, 'dist_per_unit': None, 'dist_entitle': prev.get('dist_entitle'),
         'price': None, 'pe': None, 'own_full': prev.get('own_full', 100), 'own_use': prev.get('own_use', 0),
         'top10': [{'ar': x['ar'], 'en': x['en'], 'pct': None} for x in prev.get('top10', [])],
         'alloc': [{'title_ar': a['title_ar'], 'title_en': a['title_en'], 'items': [{'ar': x['ar'], 'en': x['en'], 'pct': None} for x in a['items']]} for a in prev.get('alloc', [])],
         'rating': prev.get('rating'), 'ret_fund': [None] * len(prev.get('ret_fund', [])), 'ret_bench': [None] * len(prev.get('ret_bench', [])),
         'risk': {k: [None] * len(v) for k, v in prev.get('risk', {}).items()},
         'commentary': {'ar': '', 'en': ''}, 'tollfree': '', 'perf_points': []}
    months = [M.qstart(qn, y).replace(month=M.qstart(qn, y).month + i) for i in range(3)]
    import calendar
    for m in months:
        last = m.replace(day=calendar.monthrange(m.year, m.month)[1]).isoformat()
        d['perf_points'].append({'date': last, 'value': None, 'fund': None, 'bench': None})
    return d


def _ok(fund, q):
    if fund not in M.FUNDS or not re.match(r'q[1-4]-\d{4}$', q): raise HTTPException(404)


STATUS = {'new': 'لم يبدأ', 'draft': 'قيد الإدخال', 'generated': 'مسودة جاهزة', 'submitted': 'بانتظار الاعتماد', 'returned': 'أُعيد للتعديل', 'final': 'نهائي', 'published': 'منشور', 'corrected': 'منشور · مصحَّح'}
LOCKED = ('submitted', 'final', 'published', 'corrected')
DONE = ('published', 'corrected')
VERIFIED = json.load(open(os.path.join(APP, 'verified.json'), encoding='utf-8'))   # AR/EN differences checked against the original PDFs


# every statement already published in the fund documents becomes a record (idempotent; runs at each start)
R.import_history()


def _clear_test_q3():
    """One-off: the Q3 2026 statement of the Income fund was filled with Q2's own figures while testing the
    platform. Remove it only while it is still exactly that copy (same NAV, size and units as Q2) and not locked."""
    s = store.get('income', 'q3-2026')
    if not s or s.get('status') in LOCKED: return
    prev, _, _ = prev_values('income', 'q3-2026'); d = s.get('data') or {}
    if not prev or d.get('nav_unit') is None: return
    if all(d.get(k) == prev.get(k) for k in ('nav_unit', 'fund_size', 'units')):
        BK.take('event', 'before-clearing-test-income-q3-2026')
        A.log(None, 'statement.clear_test', 'income:q3-2026', actor={'user': 'system', 'role': 'system'}, data=d)
        store.delete('income', 'q3-2026'); shutil.rmtree(store.out_dir('income', 'q3-2026'), ignore_errors=True)
        print('cleared the Q3 2026 test copy of the Income fund', flush=True)


try: _clear_test_q3()
except Exception as e: print('test-data check skipped:', e)
BK.start()   # one backup a day, kept 30 days


# ---------- pages ----------
@app.get('/', response_class=HTMLResponse)
def home(req: Request, q: str = ''):
    me = need(req); q = q if re.match(r'q[1-4]-\d{4}$', q or '') else current_q()
    cards = []
    for fund, F in M.FUNDS.items():
        s = store.get(fund, q) or {}
        if s.get('status') in DONE: prev, pq, v = s['data'], M.prev_q(q), []
        else:
            prev, pq, _ = prev_values(fund, q)
            v = _validate(fund, s['data'], prev, q) if s.get('data') and prev else []
        cards.append({'fund': fund, 'name': F['ar'], 'en': F['en'], 'status': STATUS.get(s.get('status', 'new')), 'st': s.get('status', 'new'), 'traded': F['traded'], 'symbol': F['symbol'],
                      'updated': s.get('updated', ''), 'blocks': sum(1 for x in v if x['level'] == 'block'),
                      'warns': sum(1 for x in v if x['level'] == 'warn'), 'base_ok': prev is not None, 'pq': pq})
    qn, y = M.qparse(q); end = M.qend(qn, y); due = end + datetime.timedelta(days=10)
    left = (due - datetime.date.today()).days
    return page(req, 'home.html', done=DONE, q=q, ql=M.qlabel(q, 'ar'), cards=cards, due=M.ar_date(due), left=left, end=M.ar_date(end),
                                                cur=q == current_q(), curq=current_q(), prevq=M.prev_q(q), nextq=M.next_q(q), doc_centre=DOC_CENTRE, me=me, roles=ROLE_AR, nav='home')


@app.get('/s/{fund}/{q}', response_class=HTMLResponse)
def editor(req: Request, fund: str, q: str):
    me = need(req)
    if fund not in M.FUNDS or not re.match(r'q[1-4]-\d{4}$', q): raise HTTPException(404)
    s0 = store.get(fund, q)
    if s0 and s0.get('status') in DONE:   # published statements live as records
        return RedirectResponse(f'/r/{fund}/{q}', status_code=303)
    prev, pq, _ = prev_values(fund, q)
    if prev is None:
        return HTMLResponse(page(req, 'nobase.html', me=me, roles=ROLE_AR, nav='home', fund=M.FUNDS[fund]['ar'], fkey=fund, ql=M.qlabel(q, 'ar'), pql=M.qlabel(pq, 'ar'), pq=pq))
    s = store.get(fund, q) or store.put(fund, q, data=blank(prev, fund, q), status='new')
    F = M.FUNDS[fund]
    meta = {'fund': fund, 'q': q, 'ql': M.qlabel(q, 'ar'), 'pql': M.qlabel(pq, 'ar'), 'name': F['ar'], 'traded': F['traded'], 'symbol': F['symbol'], 'wad': F['wad'],
            'pe': F['pe'], 'perf': F['perf'], 'symbol': F['symbol'], 'periods': prev.get('periods_ar'), 'risk_names': M.RISK_AR, 'risk_keys': M.RISK, 'role': me['role'], 'st': s['status'], 'locked': s['status'] in LOCKED}
    meta['statuses'] = STATUS; meta['en'] = F['en']; meta['ai'] = ai.configured()
    if lang_of(req) == 'en':
        meta = i18n.deep(meta, 'en'); meta['periods'] = prev.get('periods_en') or meta['periods']; meta['name'] = F['en']
    return page(req, 'editor.html', meta=meta, data_json=_js(s['data']), prev_json=_js(prev), meta_json=_js(meta), s=s,
                                                  status=STATUS.get(s['status']), doc_centre=DOC_CENTRE, events=store.events(fund, q), me=me, roles=ROLE_AR, nav='home')


def _validate(fund, d, prev, q):
    v = M.validate(fund, d, prev, q)
    for l, name in (('ar', 'العربي'), ('en', 'الإنجليزي')):
        if ((d or {}).get('commentary_mt') or {}).get(l):
            v.insert(0, {'level': 'block', 'field': f'commentary.{l}', 'msg': f'تعليق مدير الصندوق {name} مترجم آليًا ولم تؤكَّد مراجعته.'})
    return v


def _clean(d):
    """Numbers typed with thousands separators, Arabic digits or % arrive as text; store them as numbers."""
    num = ['nav_unit', 'fund_size', 'units', 'avg_nav', 'ter_amount', 'borrowing', 'dealing', 'mgr_invest', 'wad_days',
           'dist_total', 'dist_units', 'dist_per_unit', 'price', 'own_full', 'own_use']
    for k in num:
        if k in d: d[k] = M.to_float(d[k]) if d[k] not in (None, '') else None
    for x in d.get('top10', []): x['pct'] = M.to_float(x.get('pct')) if x.get('pct') not in (None, '') else None
    for a in d.get('alloc', []):
        for x in a['items']: x['pct'] = M.to_float(x.get('pct')) if x.get('pct') not in (None, '') else None
    for k in ('ret_fund', 'ret_bench'): d[k] = [M.to_float(v) if v not in (None, '') else None for v in d.get(k, [])]
    d['risk'] = {k: [M.to_float(v) if v not in (None, '') else None for v in vs] for k, vs in (d.get('risk') or {}).items()}
    for p in d.get('perf_points', []):
        for k in ('value', 'fund', 'bench'): p[k] = M.to_float(p.get(k)) if p.get(k) not in (None, '') else None
    return d


@app.post('/api/s/{fund}/{q}')
async def save(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q)
    cur0 = store.get(fund, q) or {}
    if cur0.get('status') in LOCKED: return JSONResponse({'error': 'locked', 'msg': 'البيان ' + STATUS[cur0['status']] + '، فلا يُعدَّل إلا بعد إعادته للتعديل.'}, status_code=409)
    body = await req.json(); d = _clean(body.get('data') or {})
    if not M.FUNDS[fund]['traded']: d['price'] = d.get('nav_unit')
    prev, pq, _ = prev_values(fund, q)
    cur = store.get(fund, q) or {}
    st = 'draft'
    changes = A.diff(cur.get('data') or {}, d)
    s = store.put(fund, q, data=d, status=st)
    store.event(fund, q, f"{me['name']}: حفظ البيانات")
    A.log(req, 'statement.save', f'{fund}:{q}', changes=changes, n=len(changes), status_before=cur.get('status'))
    v = _validate(fund, d, prev, q); der = M.derive(d, prev)
    return {'ok': True, 'st': s['status'], 'status': STATUS[s['status']], 'validation': v, 'derived': der, 'updated': s['updated'], 'events': store.events(fund, q)}


@app.post('/api/s/{fund}/{q}/check')
async def check(req: Request, fund: str, q: str):
    need(req); _ok(fund, q); body = await req.json(); d = _clean(body.get('data') or {})
    if not M.FUNDS[fund]['traded']: d['price'] = d.get('nav_unit')
    prev, pq, _ = prev_values(fund, q)
    return {'validation': _validate(fund, d, prev, q), 'derived': M.derive(d, prev)}


@app.post('/api/s/{fund}/{q}/notes')
async def notes(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q); body = await req.json(); old = (store.get(fund, q) or {}).get('notes', '')
    store.put(fund, q, notes=str(body.get('notes', ''))[:20000]); store.event(fund, q, f"{me['name']}: تحديث الملاحظات")
    A.log(req, 'statement.notes', f'{fund}:{q}', before=old, after=str(body.get('notes', ''))[:20000])
    return {'ok': True, 'events': store.events(fund, q)}


def _generate(fund, q, final=False, by=''):
    key = f'{fund}:{q}'
    JOBS[key] = {'state': 'running', 'step': 'بانتظار انتهاء إصدار آخر'}
    with RENDER: _generate_locked(fund, q, final, by)


def _generate_locked(fund, q, final, by):
    key = f'{fund}:{q}'
    try:
        JOBS[key] = {'state': 'running', 'step': 'تجهيز البيانات'}
        s = store.get(fund, q); d = s['data']
        prev, pq, b = prev_values(fund, q)
        v = _validate(fund, d, prev, q)
        if any(x['level'] == 'block' for x in v):
            JOBS[key] = {'state': 'error', 'msg': 'يوجد نقص يمنع الإصدار. راجع قائمة التحقق.'}; return
        od = store.out_dir(fund, q) if not final else os.path.join(store.out_dir(fund, q), 'final')
        files, structs, notes_ = {}, {}, []
        htmls = []
        for lang in ('ar', 'en'):
            JOBS[key]['step'] = 'بناء النسخة ' + ('العربية' if lang == 'ar' else 'الإنجليزية')
            st = M.build(fund, lang, b[lang], pq, q, d, prev); structs[lang] = st
            lo = M.leftovers(st, pq, lang)
            if lo: notes_.append(('العربية' if lang == 'ar' else 'الإنجليزية') + ': بقيت إشارات إلى الربع السابق: ' + '، '.join(lo))
            p, rep = P.render_html(fund, q, lang, st, od); htmls.append((lang, p))
        JOBS[key]['step'] = 'إخراج PDF'
        pdfs = P.pdf([p for _, p in htmls])
        for (lang, p), pdf in zip(htmls, pdfs):
            JOBS[key]['step'] = 'إخراج Word ' + ('العربي' if lang == 'ar' else 'الإنجليزي')
            try: docx = P.word(p, lang, fund)
            except Exception as e: docx = None; notes_.append('تعذّر إخراج Word ' + lang + ': ' + str(e)[:120])
            files[lang] = {'html': os.path.basename(p), 'pdf': os.path.basename(pdf), 'docx': os.path.basename(docx) if docx else None}
        JOBS[key]['step'] = 'المقارنة بالربع السابق'
        try: CMP.build(fund, q, 'final' if final else 'draft', od, files, structs, b)
        except Exception as e: traceback.print_exc(); notes_.append('تعذّر إعداد المقارنة بالربع السابق: ' + str(e)[:120])
        if final:
            try: BK.take('event', f'before-final-{fund}-{q}')
            except Exception as e: notes_.append('تعذّرت النسخة الاحتياطية قبل الاعتماد: ' + str(e)[:120])
            for lang in ('ar', 'en'):
                json.dump(structs[lang], open(store.struct_path(fund, q, lang), 'w', encoding='utf-8'), ensure_ascii=False)
            store.put(fund, q, status='final', final_at=store.now(), files={'draft': (s.get('files') or {}).get('draft'), 'final': files}, log=notes_)
            store.event(fund, q, f'{by}: اعتماد النسخة النهائية')
        else:
            store.put(fund, q, status='generated', generated=store.now(), files={'draft': files, 'final': (s.get('files') or {}).get('final')}, log=notes_)
            store.event(fund, q, f'{by}: إصدار المسودات')
        JOBS[key] = {'state': 'done', 'notes': notes_}
        A.log(None, 'statement.final' if final else 'statement.generate', key, 'ok', actor=ACTORS.get(key), files=files, notes=notes_)
    except Exception as e:
        traceback.print_exc(); JOBS[key] = {'state': 'error', 'msg': 'تعذّر الإخراج: ' + str(e)[:300]}
        A.log(None, 'statement.final' if final else 'statement.generate', key, 'failed', actor=ACTORS.get(key), error=str(e)[:300])


@app.post('/api/s/{fund}/{q}/generate')
async def generate(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q); body = await req.json() if (await req.body()) else {}
    final = bool(body.get('final'))
    cur = store.get(fund, q) or {}
    if final and me['role'] != 'admin': raise HTTPException(403)
    if final and cur.get('status') != 'submitted':
        return JSONResponse({'error': 'state', 'msg': 'يُعتمد البيان بعد أن يُرفع للاعتماد.'}, status_code=409)
    if not final and cur.get('status') in LOCKED:
        return JSONResponse({'error': 'locked', 'msg': 'البيان ' + STATUS[cur['status']] + '.'}, status_code=409)
    key = f'{fund}:{q}'
    if JOBS.get(key, {}).get('state') == 'running': return {'ok': True, 'running': True}
    JOBS[key] = {'state': 'running', 'step': 'في الطابور'}; ACTORS[key] = {'user': me['user'], 'role': me['role'], 'rid': req.state.rid, 'ip': A.client_ip(req)}
    A.log(req, 'statement.final' if final else 'statement.generate', key, 'started')
    threading.Thread(target=_generate, args=(fund, q, final, me['name']), daemon=True).start()
    return {'ok': True}


@app.post('/api/s/{fund}/{q}/submit')
async def submit(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q); cur = store.get(fund, q) or {}
    if cur.get('status') != 'generated':
        return JSONResponse({'error': 'state', 'msg': 'أصدر المسودات بعد آخر تعديل، ثم ارفعها للاعتماد.'}, status_code=409)
    if any(((cur.get('data') or {}).get('commentary_mt') or {}).values()):
        return JSONResponse({'error': 'mt', 'msg': 'في التعليق نص مترجم آليًا لم تؤكَّد مراجعته.'}, status_code=409)
    store.put(fund, q, status='submitted')
    store.event(fund, q, f"{me['name']}: رفع المسودة للاعتماد")
    A.log(req, 'statement.submit', f'{fund}:{q}')
    return {'ok': True, 'status': STATUS['submitted']}


@app.post('/api/s/{fund}/{q}/return')
async def return_(req: Request, fund: str, q: str):
    me = need(req, 'admin'); _ok(fund, q); body = await req.json() if (await req.body()) else {}
    cur = store.get(fund, q) or {}
    if cur.get('status') not in ('submitted', 'final'): return JSONResponse({'error': 'state', 'msg': 'لا شيء بانتظار الاعتماد.'}, status_code=409)
    note = (body.get('note') or '').strip()
    notes_ = (cur.get('notes') or '')
    if note: notes_ = (notes_ + '\n\n' if notes_ else '') + f"[{store.now()} · {me['name']}] {note}"
    store.put(fund, q, status='returned', notes=notes_)
    A.log(req, 'statement.return', f'{fund}:{q}', note=note, status_before=cur.get('status'))
    store.event(fund, q, f"{me['name']}: إعادة البيان للتعديل" + (f' — {note}' if note else ''))
    return {'ok': True, 'status': STATUS['returned'], 'notes': notes_}


@app.get('/api/s/{fund}/{q}/job')
def job(req: Request, fund: str, q: str):
    need(req); _ok(fund, q); s = store.get(fund, q) or {}
    return {'st': s.get('status', 'new'), 'job': JOBS.get(f'{fund}:{q}', {'state': 'idle'}), 'files': s.get('files'), 'status': STATUS.get(s.get('status', 'new')),
            'log': s.get('log'), 'events': store.events(fund, q), 'cmp': CMP.summary(fund, q)}


@app.get('/s/{fund}/{q}/compare', response_class=HTMLResponse)
def compare_page(req: Request, fund: str, q: str, kind: str = 'draft'):
    me = need(req); _ok(fund, q)
    if kind not in ('draft', 'final'): raise HTTPException(404)
    rep = CMP.load(fund, q, kind)
    if not rep: return RedirectResponse(f'/s/{fund}/{q}', status_code=303)
    F = M.FUNDS[fund]; L = lang_of(req); pq = M.prev_q(q)
    head = {'fund': fund, 'q': q, 'kind': kind, 'name': F[L], 'ql': M.qlabel(q, L), 'pql': M.qlabel(pq, L),
            'has_final': bool(CMP.load(fund, q, 'final')), 'has_draft': bool(CMP.load(fund, q, 'draft'))}
    return page(req, 'compare.html', me=me, roles=ROLE_AR, nav='home', h=head, rep_json=_js(rep), head_json=_js(head))


def _kdir(fund, q, kind):
    if kind == 'published': return os.path.join(R.PUB, fund, q)
    if kind == 'draft': return store.out_dir(fund, q)
    if kind in ('final', 'corr', 'corrected'): return os.path.join(store.out_dir(fund, q), kind)
    raise HTTPException(404)


@app.get('/f/{fund}/{q}/{kind}/{name:path}')
def files(req: Request, fund: str, q: str, kind: str, name: str):
    need(req); _ok(fund, q)
    base_ = _kdir(fund, q, kind)
    p = os.path.abspath(os.path.join(base_, name))
    if not p.startswith(os.path.abspath(base_) + os.sep) or not os.path.isfile(p): raise HTTPException(404)
    dl = p.endswith(('.pdf', '.docx')) and req.query_params.get('dl')
    if p.endswith(('.pdf', '.docx')): A.log(req, 'file.download', f'{fund}:{q}', kind=kind, name=name)
    return FileResponse(p, filename=os.path.basename(p) if dl else None, media_type=mimetypes.guess_type(p)[0])


@app.get('/zip/{fund}/{q}/{kind}')
def zipall(req: Request, fund: str, q: str, kind: str):
    need(req); _ok(fund, q); s = store.get(fund, q) or {}; fs = (s.get('files') or {}).get(kind) or {}
    base_ = _kdir(fund, q, kind)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for lang, f in fs.items():
            for k in ('pdf', 'docx'):
                if f.get(k) and os.path.isfile(os.path.join(base_, f[k])): z.write(os.path.join(base_, f[k]), os.path.basename(f[k]))
    buf.seek(0); A.log(req, 'file.zip', f'{fund}:{q}', kind=kind)
    return StreamingResponse(buf, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{fund}-{q}-{kind}.zip"'})


# ---------- historical records: view, correct, re-issue ----------


@app.get('/records', response_class=HTMLResponse)
def records_page(req: Request, fund: str = ''):
    me = need(req)
    fund = fund if fund in M.FUNDS else next(iter(M.FUNDS))
    cc = store.correction_counts()
    rows = []
    for r in sorted((x for x in store.all_records() if x['fund'] == fund and x['status'] in DONE), key=lambda x: R.qkey(x['q']), reverse=True):
        c = store.get_conflicts(fund, r['q']) or []
        s = store.get(fund, r['q'])
        rows.append({'q': r['q'], 'ql': M.qlabel(r['q'], 'ar'), 'st': r['status'], 'status': STATUS[r['status']], 'conf': len(c),
                     'corr': cc.get(f"{fund}:{r['q']}", 0), 'draft': R.has_draft(fund, r['q']), 'files': (s.get('files') or {})})
    funds = [{'key': k, 'name': F['ar']} for k, F in M.FUNDS.items()]
    return page(req, 'records.html', me=me, roles=ROLE_AR, nav='records', rows=rows, fund=fund, fname=M.FUNDS[fund]['ar'], fen=M.FUNDS[fund]['en'], funds=funds,
                                                    nconf=sum(r['conf'] for r in rows), ncorr=sum(r['corr'] for r in rows),
                                                    total=sum(1 for x in store.all_records() if x['status'] in DONE))


@app.get('/r/{fund}/{q}', response_class=HTMLResponse)
def record_page(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q)
    s = store.get(fund, q)
    if not s or s['status'] not in DONE: return RedirectResponse(f'/s/{fund}/{q}', status_code=303)
    cur = {l: R.load(fund, q, l) for l in ('ar', 'en')}
    work = {l: (R.load(fund, q, l, True) or cur[l]) for l in ('ar', 'en')}
    meta = {'fund': fund, 'q': q, 'admin': me['role'] == 'admin', 'draft': R.has_draft(fund, q), 'st': s['status'],
            'deps': [M.qlabel(x, 'ar') for x in R.dependents(fund, q)]}
    pend = sum(len(R.diff(cur[l], work[l], l)) for l in ('ar', 'en')) if meta['draft'] else 0
    ver = [dict(v) for v in VERIFIED if v['fund'] == fund and v['q'] == q]
    for v in ver:   # hide a proposal once it has been applied
        if v.get('path') and v.get('after'):
            ks = v['path'].split('.'); x = cur[v['lang']]['blocks'][int(ks[0])]
            for k in ks[1:]: x = x[int(k)] if k.isdigit() else x[k]
            v['done'] = (x == v['after'])
    return page(req, 'record.html', 
        me=me, roles=ROLE_AR, nav='records', s=s, status=STATUS[s['status']], name=M.FUNDS[fund]['ar'], ql=M.qlabel(q, 'ar'), fund=fund, q=q,
        conflicts=store.get_conflicts(fund, q) or [], verified=ver, verified_json=_js(ver), corrections=store.corrections(fund, q), events=store.events(fund, q), pend=pend,
        cur_json=_js(cur), work_json=_js(work), meta_json=_js(meta), meta=meta)


def _changes(fund, q):
    out = []
    for l in ('ar', 'en'):
        a, b = R.load(fund, q, l), R.load(fund, q, l, True)
        if a and b: out += R.diff(a, b, l)
    return out


@app.post('/api/r/{fund}/{q}/draft')
async def record_draft(req: Request, fund: str, q: str):
    me = need(req, 'admin'); _ok(fund, q)
    s = store.get(fund, q)
    if not s or s['status'] not in DONE: return JSONResponse({'error': 'state', 'msg': 'ليس بيانًا منشورًا.'}, status_code=409)
    body = await req.json()
    for l in ('ar', 'en'):
        st = body.get(l); cur = R.load(fund, q, l)
        if not isinstance(st, dict) or not isinstance(st.get('blocks'), list) or not R.same_shape(cur, st):
            return JSONResponse({'error': 'shape', 'msg': 'التصحيح يعدّل القيم فقط، ولا يضيف أقسامًا أو صفوفًا أو يحذفها.'}, status_code=400)
        json.dump(st, open(store.draft_struct_path(fund, q, l), 'w', encoding='utf-8'), ensure_ascii=False)
    ch = _changes(fund, q)
    if not ch:
        for l in ('ar', 'en'):
            p = store.draft_struct_path(fund, q, l)
            if os.path.exists(p): os.remove(p)
    else:
        store.event(fund, q, f"{me['name']}: حفظ مسودة تصحيح ({len(ch)} تعديل)")
    A.log(req, 'record.draft', f'{fund}:{q}', changes=ch, n=len(ch))
    return {'ok': True, 'changes': ch, 'draft': bool(ch)}


@app.post('/api/r/{fund}/{q}/discard')
async def record_discard(req: Request, fund: str, q: str):
    me = need(req, 'admin'); _ok(fund, q)
    for l in ('ar', 'en'):
        p = store.draft_struct_path(fund, q, l)
        if os.path.exists(p): os.remove(p)
    shutil.rmtree(os.path.join(store.out_dir(fund, q), 'corr'), ignore_errors=True)
    s = store.get(fund, q); fs = s.get('files') or {}; fs.pop('corr', None); store.put(fund, q, files=fs)
    store.event(fund, q, f"{me['name']}: إلغاء مسودة التصحيح")
    A.log(req, 'record.discard', f'{fund}:{q}')
    return {'ok': True}


def _render_set(fund, q, structs, od):
    htmls = []
    for lang in ('ar', 'en'):
        JOBS[f'{fund}:{q}']['step'] = 'بناء النسخة ' + ('العربية' if lang == 'ar' else 'الإنجليزية')
        p, _ = P.render_html(fund, q, lang, structs[lang], od); htmls.append((lang, p))
    JOBS[f'{fund}:{q}']['step'] = 'إخراج PDF'
    pdfs = P.pdf([p for _, p in htmls]); files, notes_ = {}, []
    rel = os.path.relpath(od, _kdir(fund, q, 'corrected')) if od.startswith(_kdir(fund, q, 'corrected')) else ''
    for (lang, p), pdf in zip(htmls, pdfs):
        JOBS[f'{fund}:{q}']['step'] = 'إخراج Word ' + ('العربي' if lang == 'ar' else 'الإنجليزي')
        try: docx = P.word(p, lang, fund)
        except Exception as e: docx = None; notes_.append('تعذّر إخراج Word: ' + str(e)[:120])
        j = (lambda n: os.path.join(rel, n) if rel else n)
        files[lang] = {'html': j(os.path.basename(p)), 'pdf': j(os.path.basename(pdf)), 'docx': j(os.path.basename(docx)) if docx else None}
    return files, notes_


def _record_job(fund, q, approve, by, reason):
    JOBS[f'{fund}:{q}'] = {'state': 'running', 'step': 'بانتظار انتهاء إصدار آخر'}
    with RENDER: _record_job_locked(fund, q, approve, by, reason)


def _record_job_locked(fund, q, approve, by, reason):
    key = f'{fund}:{q}'
    try:
        JOBS[key] = {'state': 'running', 'step': 'تجهيز'}
        work = {l: R.load(fund, q, l, True) for l in ('ar', 'en')}
        if not all(work.values()): JOBS[key] = {'state': 'error', 'msg': 'لا توجد مسودة تصحيح.'}; return
        if not approve:
            od = _kdir(fund, q, 'corr'); shutil.rmtree(od, ignore_errors=True)
            files, notes_ = _render_set(fund, q, work, od)
            s = store.get(fund, q); fs = s.get('files') or {}; fs['corr'] = files
            store.put(fund, q, files=fs); store.event(fund, q, f'{by}: إصدار معاينة التصحيح')
            JOBS[key] = {'state': 'done', 'notes': notes_}; A.log(None, 'record.preview', key, actor=ACTORS.get(key)); return
        ver = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y%m%d-%H%M')
        od = os.path.join(_kdir(fund, q, 'corrected'), ver)
        files, notes_ = _render_set(fund, q, work, od)
        try: BK.take('event', f'before-correction-{fund}-{q}')
        except Exception as e: notes_.append('تعذّرت النسخة الاحتياطية قبل التصحيح: ' + str(e)[:120])
        rows = _changes(fund, q)
        for l in ('ar', 'en'):
            op = store.orig_struct_path(fund, q, l)
            if not os.path.exists(op): shutil.copy(store.struct_path(fund, q, l), op)   # the published original, kept once
            shutil.copy(store.draft_struct_path(fund, q, l), store.struct_path(fund, q, l))
            os.remove(store.draft_struct_path(fund, q, l))
        store.add_corrections(fund, q, by, reason, rows)
        store.set_conflicts(fund, q, R.conflicts(work['ar'], work['en']))
        s = store.get(fund, q); fs = s.get('files') or {}; fs.pop('corr', None); fs['corrected'] = files
        data = s.get('data') or {}
        if data and R.is_annex4(work['ar']):
            try:
                nd = M.extract(work['ar'], work['en'], fund); nd['valuation_date'] = data.get('valuation_date'); nd['perf_points'] = data.get('perf_points', []); data = nd
            except Exception: pass
        shutil.rmtree(_kdir(fund, q, 'corr'), ignore_errors=True)
        store.put(fund, q, status='corrected', files=fs, data=data, log=notes_)
        store.event(fund, q, f'{by}: اعتماد التصحيح ({len(rows)} تعديل) — {reason}')
        JOBS[key] = {'state': 'done', 'notes': notes_}
        A.log(None, 'record.approve', key, actor=ACTORS.get(key), reason=reason, changes=rows, files=files)
    except Exception as e:
        traceback.print_exc(); JOBS[key] = {'state': 'error', 'msg': 'تعذّر الإخراج: ' + str(e)[:300]}
        A.log(None, 'record.approve' if approve else 'record.preview', key, 'failed', actor=ACTORS.get(key), error=str(e)[:300])


@app.post('/api/r/{fund}/{q}/run')
async def record_run(req: Request, fund: str, q: str):
    me = need(req, 'admin'); _ok(fund, q)
    body = await req.json() if (await req.body()) else {}
    approve = bool(body.get('approve')); reason = (body.get('reason') or '').strip()
    if not R.has_draft(fund, q): return JSONResponse({'error': 'state', 'msg': 'احفظ التعديلات أولًا.'}, status_code=409)
    if approve and len(reason) < 5: return JSONResponse({'error': 'reason', 'msg': 'اكتب سبب التصحيح (مثل: طلب هيئة السوق المالية رقم …).'}, status_code=400)
    key = f'{fund}:{q}'
    if JOBS.get(key, {}).get('state') == 'running': return {'ok': True, 'running': True}
    JOBS[key] = {'state': 'running', 'step': 'في الطابور'}; ACTORS[key] = {'user': me['user'], 'role': me['role']}
    threading.Thread(target=_record_job, args=(fund, q, approve, me['name'], reason), daemon=True).start()
    return {'ok': True}


@app.get('/api/r/{fund}/{q}/changes')
def record_changes(req: Request, fund: str, q: str):
    need(req); _ok(fund, q)
    return {'changes': _changes(fund, q) if R.has_draft(fund, q) else []}


# ---------- Excel intake: a workbook per fund and quarter, a sheet per source ----------
@app.get('/s/{fund}/{q}/template.xlsx')
def xl_template(req: Request, fund: str, q: str):
    need(req); _ok(fund, q)
    prev, pq, _ = prev_values(fund, q)
    if prev is None: raise HTTPException(404)
    s = store.get(fund, q) or {}
    data = s.get('data') or blank(prev, fund, q)
    blob = xl.build(fund, q, data, prev); A.log(req, 'statement.template', f'{fund}:{q}')
    name = f"{M.FUNDS[fund].get('doc_centre', fund)}-{q}-inputs.xlsx"
    return StreamingResponse(io.BytesIO(blob), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={'Content-Disposition': f'attachment; filename="{name}"', 'Cache-Control': 'no-store'})


@app.post('/api/s/{fund}/{q}/import')
async def xl_import(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q)
    s = store.get(fund, q) or {}
    if s.get('status') in LOCKED: return JSONResponse({'error': 'locked', 'msg': 'البيان ' + STATUS[s['status']] + '، فلا يُستورد إليه.'}, status_code=409)
    form = await req.form(); f = form.get('file')
    if f is None or not hasattr(f, 'read'): return JSONResponse({'error': 'file', 'msg': 'اختر ملف Excel.'}, status_code=400)
    blob = await f.read()
    if len(blob) > 15 * 1024 * 1024: return JSONResponse({'error': 'size', 'msg': 'الملف أكبر من 15 ميغابايت.'}, status_code=400)
    body = form.get('data')
    try: cur = json.loads(body) if body else (s.get('data') or {})
    except ValueError: cur = s.get('data') or {}
    if not cur:
        prev, _, _ = prev_values(fund, q); cur = blank(prev, fund, q) if prev else {}
    try: d, ch, probs = xl.parse(blob, fund, q, cur)
    except xl.WrongFile as e:
        return JSONResponse({'error': 'wrong', 'msg': str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({'error': 'parse', 'msg': 'تعذّرت قراءة الملف. استخدم قالب المنصة بصيغة xlsx.'}, status_code=400)
    # keep the uploaded file as the source of these figures
    up = os.path.join(store.DATA, 'uploads', fund, q); os.makedirs(up, exist_ok=True)
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', getattr(f, 'filename', 'inputs.xlsx'))[-80:]
    open(os.path.join(up, f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe}"), 'wb').write(blob)
    store.event(fund, q, f"{me['name']}: قراءة ملف Excel ({len(ch)} تغيير)")
    A.log(req, 'statement.import', f'{fund}:{q}', file=getattr(f, 'filename', ''), changes=ch, problems=probs)
    return {'ok': True, 'data': d, 'changes': ch, 'problems': probs}


# ---------- backups (admin) ----------
@app.get('/backups', response_class=HTMLResponse)
def backups_page(req: Request):
    me = need(req, 'admin')
    return page(req, 'backups.html', me=me, roles=ROLE_AR, nav='backups', items=BK.listing(), keep=BK.KEEP_DAILY)


@app.post('/api/backups')
async def backups_take(req: Request):
    me = need(req, 'admin')
    name = await run_in_threadpool(BK.take, 'manual'); A.log(req, 'backup.create', name)
    return {'ok': True, 'name': name, 'items': BK.listing()}


@app.get('/backups/f/{name}')
def backups_file(req: Request, name: str):
    need(req, 'admin')
    if not re.match(r'^[A-Za-z0-9._-]+\.zip$', name): raise HTTPException(404)
    p = os.path.join(BK.DIR, name)
    if not os.path.isfile(p): raise HTTPException(404)
    A.log(req, 'backup.download', name)
    return FileResponse(p, filename=name, media_type='application/zip')


# ---------- audit trail (admin) ----------
@app.get('/audit', response_class=HTMLResponse)
def audit_page(req: Request, actor: str = '', action: str = '', obj: str = '', since: str = '', until: str = '', outcome: str = '', page_: int = 0):
    me = need(req, 'admin'); lang = lang_of(req)
    page_ = max(0, int(req.query_params.get('p', 0) or 0))
    total, rows = A.query(actor, action, obj, since, (until + 'T23:59:59.999') if until else '', outcome, 50, page_ * 50)
    ok, n = A.verify()
    acts = {k: v[1 if lang == 'en' else 0] for k, v in i18n.ACTIONS.items()}
    request_q = '&'.join(f'{k}={v}' for k, v in req.query_params.items() if k != 'p' and v)
    return page(req, 'audit.html', request_q=request_q, me=me, roles=ROLE_AR, nav='audit', rows=rows, total=total, p=page_, pages=(total + 49) // 50, chain_ok=ok, chain_n=n,
                f={'actor': actor, 'action': action, 'obj': obj, 'since': since, 'until': until, 'outcome': outcome}, actors=A.actors(), acts=acts, stats=A.stats(), aiu=ai.usage_summary())


@app.get('/audit.csv')
def audit_csv(req: Request, actor: str = '', action: str = '', obj: str = '', since: str = '', until: str = '', outcome: str = ''):
    need(req, 'admin')
    A.log(req, 'audit.export', '', filters={'actor': actor, 'action': action, 'obj': obj, 'since': since, 'until': until, 'outcome': outcome})
    data = A.export_csv(actor=actor, action=action, obj=obj, since=since, until=(until + 'T23:59:59.999') if until else '', outcome=outcome)
    name = 'audit-' + datetime.datetime.now().strftime('%Y%m%d-%H%M') + '.csv'
    return Response(data, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{name}"'})


A.prune_access()


# ---------- AI: any file in, commentary, assistant ----------
@app.post('/api/s/{fund}/{q}/intake')
async def intake_files(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q); lang = lang_of(req)
    s = store.get(fund, q) or {}
    if s.get('status') in LOCKED: return JSONResponse({'error': 'locked', 'msg': 'البيان ' + STATUS[s['status']] + '، فلا يُستورد إليه.'}, status_code=409)
    form = await req.form(); ups = [f for f in form.getlist('files') if hasattr(f, 'read')]
    if not ups: return JSONResponse({'error': 'file', 'msg': 'اختر ملفًا واحدًا على الأقل.'}, status_code=400)
    files, total = [], 0
    up = os.path.join(store.DATA, 'uploads', fund, q); os.makedirs(up, exist_ok=True)
    for f in ups[:20]:
        b = await f.read(); total += len(b)
        if total > 60 * 1024 * 1024: return JSONResponse({'error': 'size', 'msg': 'مجموع الملفات أكبر من 60 ميغابايت.'}, status_code=400)
        name = os.path.basename(getattr(f, 'filename', '') or 'file')[-120:]
        open(os.path.join(up, datetime.datetime.now().strftime('%Y%m%d-%H%M%S-') + re.sub(r'[^A-Za-z0-9._\u0600-\u06FF-]', '_', name)), 'wb').write(b)
        files.append((name, b))
    try: cur = json.loads(form.get('data') or 'null') or s.get('data') or {}
    except ValueError: cur = s.get('data') or {}
    prev, pq, _ = prev_values(fund, q)
    if not prev: return JSONResponse({'error': 'base', 'msg': 'لا يوجد بيان معتمد للربع السابق.'}, status_code=409)
    if not cur: cur = blank(prev, fund, q)
    content = IN.read(files)
    data, changes, problems = cur, [], list(content['skipped'])
    for name, b in content['templates']:
        try: data, ch, pr = xl.parse(b, fund, q, data); changes += ch; problems += pr
        except xl.WrongFile as e: problems.append(f'{name}: {e}')
    res = {'proposals': [], 'summary': '', 'conflicts': [], 'not_found': []}
    if content['text'] or content['images']:
        if not ai.configured():
            problems.append('قراءة الملفات غير القالب تحتاج تفعيل الذكاء الاصطناعي.')
        else:
            try: res = await run_in_threadpool(IN.propose, fund, q, data, prev, content, me['user'], lang_of(req))
            except ai.AIError as e: problems.append(str(e))
    A.log(req, 'statement.intake', f'{fund}:{q}', files=[n for n, _ in files], template_changes=changes, proposals=res['proposals'], conflicts=res['conflicts'], problems=problems)
    store.event(fund, q, f"{me['name']}: قراءة ملفات ({len(files)})")
    if lang == 'en':
        for p in res['proposals']: p['label'] = p['label'].split(' / ')[-1] if ' / ' in p['label'] else p['label']
    return {'ok': True, 'data': data, 'changes': changes, 'problems': problems, **res}


@app.post('/api/s/{fund}/{q}/commentary')
async def commentary_ai(req: Request, fund: str, q: str):
    me = need(req); _ok(fund, q); body = await req.json()
    act, src = body.get('action'), body.get('lang')
    text = (body.get('text') or '').strip()
    if act not in ('improve', 'translate') or src not in ('ar', 'en') or not text:
        return JSONResponse({'error': 'input', 'msg': 'اكتب نص التعليق أولًا.'}, status_code=400)
    prev, _, _ = prev_values(fund, q)
    try:
        fn = CM.improve if act == 'improve' else CM.translate
        r = await run_in_threadpool(fn, src, text, prev or {}, me['user'], f'{fund}:{q}', lang_of(req))
    except ai.AIError as e:
        return JSONResponse({'error': 'ai', 'msg': str(e)}, status_code=503)
    dst = src if act == 'improve' else ('en' if src == 'ar' else 'ar')
    other = ((body.get('data') or {}).get('commentary') or {}).get('en' if dst == 'ar' else 'ar', '') if act == 'improve' else text
    r['figures'] = CM.check(r.get('text', ''), other, body.get('data') or {})
    r['target'] = dst; r['action'] = act
    A.log(req, 'commentary.' + act, f'{fund}:{q}', lang=src, target=dst, source=text, result=r.get('text', ''), changes=r.get('changes'), doubts=r.get('doubts'))
    return r


@app.post('/api/assistant')
async def assistant_ask(req: Request):
    me = need(req); body = await req.json(); lang = lang_of(req)
    page_ = body.get('page') or {}
    if page_.get('fund') not in M.FUNDS: page_ = {}
    msgs = body.get('messages') or []
    q_text = next((m.get('content') for m in reversed(msgs) if m.get('role') == 'user'), '')
    sess = AS.Session(me, {'current_q': current_q, 'prev_values': prev_values, 'clean': _clean, 'verified': VERIFIED}, lang, page_)
    try:
        out = await run_in_threadpool(sess.run, msgs, req)
    except ai.AIError as e:
        A.log(req, 'assistant.ask', f"{page_.get('fund', '')}:{page_.get('q', '')}".strip(':'), 'failed', question=q_text, error=str(e))
        return JSONResponse({'error': 'ai', 'msg': str(e)}, status_code=503)
    A.log(req, 'assistant.ask', f"{page_.get('fund', '')}:{page_.get('q', '')}".strip(':'), question=q_text, answer=out['text'][:4000], tools=out['tools'], actions=out['actions'])
    return out


@app.post('/api/assistant/undo/{uid}')
async def assistant_undo(req: Request, uid: int):
    me = need(req)
    r = AS.undo(uid, me, req)
    if r.get('error'): return JSONResponse({'error': 'undo', 'msg': r['error']}, status_code=409)
    return r


@app.get('/api/ai/usage')
def ai_usage(req: Request):
    need(req, 'admin'); return ai.usage_summary()


threading.Thread(target=ai.selfcheck, daemon=True, name='ai-selfcheck').start()
