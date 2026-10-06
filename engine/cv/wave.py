# Swap the "signal line" cover (cover v2) for the approved wave-art cover used by public / listed funds.
import re, sys, json, base64, os, html as H
from bs4 import BeautifulSoup
SP = os.environ.get('AKC_SP', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/')
ART = {k: 'data:image/jpeg;base64,' + base64.b64encode(open(SP + 'cv/art-%s.jpg' % k, 'rb').read()).decode() for k in ('cm', 're')}
PAL = {'cm': dict(bar='#3B7DD8', eyb='#9DB8E0', doc='#7FB0EA', soft='#C9D6EE', line='157,184,224'),
       're': dict(bar='#9A6A45', eyb='#D8C3AE', doc='#E2B98F', soft='#E8DCCF', line='216,195,174')}

def css(k):
    p = PAL[k]
    return ('<style id="wv-cover">'
        'section.cover.wv{background:#021640}'
        f'section.cover.wv .wv-art{{position:absolute;left:0;right:0;top:56mm;height:140mm;background:url({ART[k]}) center/210mm 140mm no-repeat}}'
        'section.cover.wv .wv-logo{position:absolute;top:20mm;inset-inline-start:18mm;height:15mm;width:auto;max-width:70mm}'
        'section.cover.wv .wv-code{position:absolute;top:22mm;inset-inline-end:18mm;font-size:6.5pt;letter-spacing:.06em;color:rgba(%s,.7);direction:ltr}' % p['line'] +
        'section.cover.wv .wv-tx{position:absolute;bottom:36mm;inset-inline:18mm}'
        f'section.cover.wv .wv-tx:before{{content:"";display:block;width:14mm;height:.9mm;background:{p["bar"]};margin-bottom:5mm}}'
        f'section.cover.wv .wv-eyb{{font-family:"Alexandria",sans-serif;font-size:10pt;color:{p["eyb"]};line-height:1.6;max-width:160mm}}'
        'section.cover.wv .wv-fund{font-family:"Alexandria",sans-serif;font-weight:700;font-size:24pt;line-height:1.5;margin-top:3mm;max-width:160mm;color:#fff}'
        f'section.cover.wv .wv-doc{{font-family:"Alexandria",sans-serif;font-weight:600;font-size:16pt;line-height:1.5;color:{p["doc"]};margin:6mm 0 0;padding-top:5mm;border-top:.3mm solid rgba({p["line"]},.3);max-width:130mm}}'
        f'section.cover.wv .wv-dt{{font-size:11pt;color:{p["soft"]};margin-top:2mm}}'
        f'section.cover.wv .wv-ft{{position:absolute;bottom:12mm;inset-inline:18mm;font-size:7.5pt;color:{p["eyb"]};display:flex;justify-content:space-between;align-items:center;gap:6mm;border-top:.3mm solid rgba({p["line"]},.35);padding-top:3mm}}'
        'section.cover.wv .wv-ft img{height:13.5mm;width:auto}'
        '</style>')

def cover_span(t):
    i = t.find('<section class="cover v2">')
    if i < 0: return None
    d = 0
    for m in re.finditer(r'<(/?)section\b[^>]*>', t[i:]):
        d += -1 if m.group(1) else 1
        if d == 0: return i, i + m.end()

def transform(t, k):
    sp = cover_span(t)
    if not sp: return None
    a, b = sp
    c = BeautifulSoup(t[a:b], 'html.parser')
    logo = c.select_one('img.flogo')['src']
    akc = c.select_one('.ft img')['src']
    ft = c.select_one('.ft span').decode_contents()
    code = c.select_one('.code').get_text(strip=True) if c.select_one('.code') else ''
    fund = c.select_one('.fund').decode_contents()
    doc = c.select_one('.doc').decode_contents()
    mt = [s.decode_contents() for s in c.select('.mt span')]
    eyb = mt[-1] if mt else ''
    dt = mt[0] if len(mt) > 1 else ''
    new = ('<section class="cover wv"><div class="wv-art"></div>'
           f'<img class="wv-logo" src="{logo}" alt="">'
           + (f'<div class="wv-code">{code}</div>' if code else '') +
           f'<div class="wv-tx"><div class="wv-eyb">{eyb}</div><div class="wv-fund">{fund}</div><h1 class="wv-doc">{doc}</h1>'
           + (f'<div class="wv-dt">{dt}</div>' if dt else '') + '</div>'
           f'<div class="wv-ft"><img src="{akc}" alt=""><span>{ft}</span></div></section>')
    t = t[:a] + new + t[b:]
    t = t.replace('</head>', css(k) + '</head>', 1)
    return t

if __name__ == '__main__':
    jobs = json.load(open(SP + 'word/jobs.json'))
    done = []
    for j in jobs:
        src = SP + j['html']
        k = 're' if '-REIT-' in j['fname'] else 'cm'
        t = transform(open(src, encoding='utf-8').read(), k)
        if t is None: print('skip (no cover)', j['fname']); continue
        out = src[:-5] + '.wv.html'
        open(out, 'w', encoding='utf-8').write(t)
        os.makedirs(os.path.dirname(out) + '/pdf', exist_ok=True)
        done.append(out)
    json.dump(done, open(SP + 'cv/list.json', 'w'), indent=0)
    print(len(done), 'written')
