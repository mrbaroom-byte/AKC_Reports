"""منصة البيانات الربعية — Alkhabeer Capital quarterly statements for the capital-market funds."""
import os, json, re, hmac, hashlib, threading, traceback, datetime, mimetypes, zipfile, io
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from jinja2 import Environment, FileSystemLoader, select_autoescape
import model as M, store, pipeline as P

APP = os.path.dirname(os.path.abspath(__file__))
ENG = P.ENG
SECRET = os.environ.get('SESSION_SECRET') or hashlib.sha256((os.environ.get('ADMIN_PASSWORD', '') + 'akc-q').encode()).hexdigest()
SER = URLSafeTimedSerializer(SECRET, salt='akc-q-session')
DOC_CENTRE = os.environ.get('DOC_CENTRE_URL', 'https://claude.ai/artifact/7bddTJzzSApLduLWWzKwXv')
SEED_Q = 'q2-2026'
env = Environment(loader=FileSystemLoader(os.path.join(APP, 'templates')), autoescape=select_autoescape(['html']))
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
JOBS = {}


# ---------- auth ----------
def authed(req: Request):
    tok = req.cookies.get('akcq')
    if not tok: return False
    try: SER.loads(tok, max_age=60 * 60 * 12); return True
    except BadSignature: return False


def need(req: Request):
    if not authed(req): raise HTTPException(status_code=401)


@app.exception_handler(401)
async def _401(req, exc):
    if req.url.path.startswith('/api/'): return JSONResponse({'error': 'login'}, status_code=401)
    return RedirectResponse('/login', status_code=303)


@app.get('/login', response_class=HTMLResponse)
def login_page(req: Request, e: str = ''):
    return env.get_template('login.html').render(err=bool(e), configured=bool(os.environ.get('ADMIN_PASSWORD')))


@app.post('/login')
def login(password: str = Form(...)):
    pw = os.environ.get('ADMIN_PASSWORD', '').strip().strip('"').strip("'").strip()
    if not pw or not hmac.compare_digest(password.strip().encode(), pw.encode()):
        return RedirectResponse('/login?e=1', status_code=303)
    r = RedirectResponse('/', status_code=303)
    r.set_cookie('akcq', SER.dumps('admin'), httponly=True, secure=os.environ.get('RAILWAY_ENVIRONMENT') is not None, samesite='lax', max_age=60 * 60 * 12)
    return r


@app.get('/logout')
def logout():
    r = RedirectResponse('/login', status_code=303); r.delete_cookie('akcq'); return r


@app.get('/health')
def health(): return {'ok': True}


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


STATUS = {'new': 'لم يبدأ', 'draft': 'قيد الإدخال', 'generated': 'مسودة جاهزة', 'final': 'نهائي'}


# ---------- pages ----------
@app.get('/', response_class=HTMLResponse)
def home(req: Request, q: str = ''):
    need(req); q = q if re.match(r'q[1-4]-\d{4}$', q or '') else current_q()
    cards = []
    for fund, F in M.FUNDS.items():
        s = store.get(fund, q) or {}
        prev, pq, _ = prev_values(fund, q)
        v = M.validate(fund, s['data'], prev, q) if s.get('data') and prev else []
        cards.append({'fund': fund, 'name': F['ar'], 'en': F['en'], 'status': STATUS.get(s.get('status', 'new')), 'st': s.get('status', 'new'),
                      'updated': s.get('updated', ''), 'blocks': sum(1 for x in v if x['level'] == 'block'),
                      'warns': sum(1 for x in v if x['level'] == 'warn'), 'base_ok': prev is not None, 'pq': pq})
    qn, y = M.qparse(q); end = M.qend(qn, y); due = end + datetime.timedelta(days=10)
    return env.get_template('home.html').render(q=q, ql=M.qlabel(q, 'ar'), cards=cards, due=M.ar_date(due), prevq=M.prev_q(q), nextq=M.next_q(q), doc_centre=DOC_CENTRE)


@app.get('/s/{fund}/{q}', response_class=HTMLResponse)
def editor(req: Request, fund: str, q: str):
    need(req)
    if fund not in M.FUNDS or not re.match(r'q[1-4]-\d{4}$', q): raise HTTPException(404)
    prev, pq, _ = prev_values(fund, q)
    if prev is None:
        return HTMLResponse(env.get_template('nobase.html').render(fund=M.FUNDS[fund]['ar'], ql=M.qlabel(q, 'ar'), pql=M.qlabel(pq, 'ar')))
    s = store.get(fund, q) or store.put(fund, q, data=blank(prev, fund, q), status='new')
    F = M.FUNDS[fund]
    meta = {'fund': fund, 'q': q, 'ql': M.qlabel(q, 'ar'), 'pql': M.qlabel(pq, 'ar'), 'name': F['ar'], 'traded': F['traded'], 'wad': F['wad'],
            'pe': F['pe'], 'perf': F['perf'], 'symbol': F['symbol'], 'periods': prev.get('periods_ar'), 'risk_names': M.RISK_AR, 'risk_keys': M.RISK}
    return env.get_template('editor.html').render(meta=meta, data_json=json.dumps(s['data'], ensure_ascii=False), prev_json=json.dumps(prev, ensure_ascii=False),
                                                  meta_json=json.dumps(meta, ensure_ascii=False), s=s, status=STATUS.get(s['status']), doc_centre=DOC_CENTRE,
                                                  events=store.events(fund, q))


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
    need(req); body = await req.json(); d = _clean(body.get('data') or {})
    if not M.FUNDS[fund]['traded']: d['price'] = d.get('nav_unit')
    prev, pq, _ = prev_values(fund, q)
    cur = store.get(fund, q) or {}
    st = cur.get('status', 'new'); st = 'draft' if st in ('new', 'generated', 'final') else st
    s = store.put(fund, q, data=d, status=st)
    store.event(fund, q, 'حُفظت البيانات')
    v = M.validate(fund, d, prev, q); der = M.derive(d, prev)
    return {'ok': True, 'status': STATUS[s['status']], 'validation': v, 'derived': der, 'updated': s['updated']}


@app.post('/api/s/{fund}/{q}/check')
async def check(req: Request, fund: str, q: str):
    need(req); body = await req.json(); d = _clean(body.get('data') or {})
    if not M.FUNDS[fund]['traded']: d['price'] = d.get('nav_unit')
    prev, pq, _ = prev_values(fund, q)
    return {'validation': M.validate(fund, d, prev, q), 'derived': M.derive(d, prev)}


@app.post('/api/s/{fund}/{q}/notes')
async def notes(req: Request, fund: str, q: str):
    need(req); body = await req.json(); store.put(fund, q, notes=body.get('notes', '')); store.event(fund, q, 'حُدّثت الملاحظات')
    return {'ok': True}


def _generate(fund, q, final=False):
    key = f'{fund}:{q}'
    try:
        JOBS[key] = {'state': 'running', 'step': 'تجهيز البيانات'}
        s = store.get(fund, q); d = s['data']
        prev, pq, b = prev_values(fund, q)
        v = M.validate(fund, d, prev, q)
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
        if final:
            for lang in ('ar', 'en'):
                json.dump(structs[lang], open(store.struct_path(fund, q, lang), 'w', encoding='utf-8'), ensure_ascii=False)
            store.put(fund, q, status='final', final_at=store.now(), files={'draft': (s.get('files') or {}).get('draft'), 'final': files}, log=notes_)
            store.event(fund, q, 'اعتُمدت النسخة النهائية')
        else:
            store.put(fund, q, status='generated', generated=store.now(), files={'draft': files, 'final': (s.get('files') or {}).get('final')}, log=notes_)
            store.event(fund, q, 'صدرت المسودات')
        JOBS[key] = {'state': 'done', 'notes': notes_}
    except Exception as e:
        traceback.print_exc(); JOBS[key] = {'state': 'error', 'msg': 'تعذّر الإخراج: ' + str(e)[:300]}


@app.post('/api/s/{fund}/{q}/generate')
async def generate(req: Request, fund: str, q: str):
    need(req); body = await req.json() if (await req.body()) else {}
    final = bool(body.get('final'))
    key = f'{fund}:{q}'
    if JOBS.get(key, {}).get('state') == 'running': return {'ok': True, 'running': True}
    threading.Thread(target=_generate, args=(fund, q, final), daemon=True).start()
    return {'ok': True}


@app.get('/api/s/{fund}/{q}/job')
def job(req: Request, fund: str, q: str):
    need(req); s = store.get(fund, q) or {}
    return {'job': JOBS.get(f'{fund}:{q}', {'state': 'idle'}), 'files': s.get('files'), 'status': STATUS.get(s.get('status', 'new')), 'log': s.get('log')}


@app.get('/f/{fund}/{q}/{kind}/{name:path}')
def files(req: Request, fund: str, q: str, kind: str, name: str):
    need(req)
    base_ = store.out_dir(fund, q) if kind == 'draft' else os.path.join(store.out_dir(fund, q), 'final')
    p = os.path.abspath(os.path.join(base_, name))
    if not p.startswith(os.path.abspath(base_)) or not os.path.exists(p): raise HTTPException(404)
    dl = p.endswith(('.pdf', '.docx')) and req.query_params.get('dl')
    return FileResponse(p, filename=os.path.basename(p) if dl else None, media_type=mimetypes.guess_type(p)[0])


@app.get('/zip/{fund}/{q}/{kind}')
def zipall(req: Request, fund: str, q: str, kind: str):
    need(req); s = store.get(fund, q) or {}; fs = (s.get('files') or {}).get(kind) or {}
    base_ = store.out_dir(fund, q) if kind == 'draft' else os.path.join(store.out_dir(fund, q), 'final')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for lang, f in fs.items():
            for k in ('pdf', 'docx'):
                if f.get(k): z.write(os.path.join(base_, f[k]), f[k])
    buf.seek(0)
    return StreamingResponse(buf, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{fund}-{q}-{kind}.zip"'})
