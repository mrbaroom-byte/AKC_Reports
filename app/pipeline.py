"""Quarterly statement pipeline: struct JSON -> print HTML (render.py) -> web HTML (web.py) -> v3 identity (style.py)
-> review fixes (qfix.py) -> PDF (Playwright) -> Word (build3.py). Same engine that produced the published statements."""
import os, sys, json, subprocess, shutil, re, asyncio, importlib
ENG = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'engine'))
FUNDDIR = {'dif2030': 'i30', 'income': 'inc', 'gif': 'gif'}
PREFIX = {'dif2030': 'AKC-DIF2030', 'income': 'AKC-DIF', 'gif': 'AKC-GIF'}
sys.path.insert(0, os.path.join(ENG, 'v3')); sys.path.insert(0, os.path.join(ENG, 'cv'))

def _mod(name):
    return importlib.import_module(name)

def fname(fund, q, lang):
    m = re.match(r'q(\d)-(\d{4})', q)
    pfx = json.load(open(os.path.join(ENG, FUNDDIR[fund], 'fund.json'))).get('file_prefix') if fund != 'dif2030' else PREFIX[fund]
    return f"{pfx}-QUARTERLY-STATEMENT-{m.group(2)}-Q{m.group(1)}-{lang.upper()}"

def render_html(fund, q, lang, struct, outdir):
    """Write struct, run render.py + web.convert, apply v3 styling and review fixes; return final HTML path."""
    fd = os.path.join(ENG, FUNDDIR[fund])
    os.makedirs(os.path.join(fd, 'struct'), exist_ok=True)
    sp = os.path.join(fd, 'struct', f'{q}.{lang}.json')
    keep = open(sp, 'rb').read() if os.path.exists(sp) else None   # the published original stays untouched in the engine
    json.dump(struct, open(sp, 'w', encoding='utf-8'), ensure_ascii=False)
    env = dict(os.environ, FUND_DIR=fd)
    try:
        r = subprocess.run([sys.executable, os.path.join(ENG, 'i30', 'render.py'), q, lang], env=env, capture_output=True, text=True)
        if r.returncode: raise RuntimeError('render: ' + r.stderr[-1500:])
        code = (
            "import sys,json;sys.path.insert(0,%r);import web;m=web.convert(%r,%r);print(json.dumps(m))" % (os.path.join(ENG, 'i30'), q, lang))
        r = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, cwd=os.path.join(ENG, 'i30'))
        if r.returncode: raise RuntimeError('web: ' + r.stderr[-1500:])
    finally:
        if keep is not None: open(sp, 'wb').write(keep)   # the published original goes back
        elif os.path.exists(sp): os.remove(sp)              # a new quarter leaves nothing behind in the engine
    man = json.loads(r.stdout.strip().splitlines()[-1])
    hub = os.path.join(ENG, 'i30', 'hub')
    src = open(os.path.join(hub, man['html']), encoding='utf-8').read()
    style = _mod('style'); qfix = _mod('qfix')
    key = (fund + '.' if fund != 'dif2030' else '') + f'{q}.{lang}'
    fresh = style.apply(src, 'cm', key)
    tpl = open(os.path.join(ENG, 'templates', fund, lang + '.html'), encoding='utf-8').read()
    h = compose(tpl, fresh, q, lang)
    donor = open(os.path.join(ENG, 'templates', fund, lang + '.donor.html'), encoding='utf-8').read()
    h, rep = qfix.apply(h, lang, fund, donor)
    os.makedirs(outdir, exist_ok=True)
    a = os.path.join(outdir, 'assets'); os.makedirs(a, exist_ok=True)
    for d in (os.path.join(hub, 'assets'), os.path.join(ENG, 'assets')):
        for n in os.listdir(d):
            if not os.path.exists(os.path.join(a, n)): shutil.copy(os.path.join(d, n), os.path.join(a, n))
    p = os.path.join(outdir, fname(fund, q, lang) + '.html')
    open(p, 'w', encoding='utf-8').write(h)
    return p, rep

async def _pdf(paths):
    from playwright.async_api import async_playwright
    out = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); pg = await b.new_page()
        for f in paths:
            await pg.goto('file://' + f, wait_until='networkidle', timeout=180000)
            await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(500)
            o = f[:-5] + '.pdf'; await pg.pdf(path=o, prefer_css_page_size=True, print_background=True, tagged=True); out.append(o)
        await b.close()
    return out

def pdf(paths):
    return asyncio.run(_pdf(paths))

def _labels(html_path):
    from bs4 import BeautifulSoup
    s = BeautifulSoup(open(html_path, encoding='utf-8').read(), 'html.parser')
    g = lambda e: re.sub(r'\s+', ' ', e.get_text(' ', strip=True)) if e else ''
    f = s.select_one('.wv-fund'); d = s.select_one('.wv-doc') or s.select_one('h1.bh')
    fund = g(f)
    if not fund:
        t = s.title.string if s.title else ''; fund = t.split('·')[0].strip() if '·' in t else ''
    return fund, g(d)

def word(html_path, lang, fund):
    b3 = _mod('build3'); o = html_path[:-5] + '.docx'
    fl, dl = _labels(html_path)
    b3.build(html_path, o, lang, [], fund_label=fl, doc_label=dl, accent='3B7DD8'); return o

QAR = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع'}
QEN = {1: 'First', 2: 'Second', 3: 'Third', 4: 'Fourth'}
def compose(tpl, fresh, q, lang):
    """Published shell (head, styles, wave cover) + freshly rendered body. Cover texts move to the new quarter."""
    from bs4 import BeautifulSoup
    T = BeautifulSoup(tpl, 'html.parser'); N = BeautifulSoup(fresh, 'html.parser')
    tm, nm = T.find('main'), N.find('main')
    band = tm.find('div', class_='band')
    for c in list(tm.children):
        if c is not band: c.extract()
    for c in list(nm.children):
        if getattr(c, 'name', None) == 'div' and 'band' in (c.get('class') or []): continue
        tm.append(c.extract() if hasattr(c, 'extract') else c)
    m = re.match(r'q(\d)-(\d{4})', q); qn, y = int(m.group(1)), m.group(2)
    qd = band.find('div', class_='q')
    if qd:
        sm = qd.find('small'); qd.clear(); qd.append(str(qn))
        if sm is not None: sm.string = y; qd.append(sm)
    sub = band.find('div', class_='sub')
    if sub:
        t = sub.get_text()
        t = re.sub(r'الربع (الأول|الثاني|الثالث|الرابع) \d{4}', f'الربع {QAR[qn]} {y}', t)
        t = re.sub(r'Q\d \d{4}', f'Q{qn} {y}', t)
        t = re.sub(r'(First|Second|Third|Fourth) Quarter of \d{4}', f'{QEN[qn]} Quarter of {y}', t)
        sub.string = t
    out = str(T)
    # page headers (@top-left in CSS) and <title> carry the quarter too
    i = out.find('<main')
    head, rest = out[:i], out[i:]
    head = re.sub(r'الربع (الأول|الثاني|الثالث|الرابع) \d{4}', f'الربع {QAR[qn]} {y}', head)
    head = re.sub(r'Q[1-4] \d{4}', f'Q{qn} {y}', head)
    head = re.sub(r'(First|Second|Third|Fourth) Quarter of \d{4}', f'{QEN[qn]} Quarter of {y}', head)
    return head + rest
