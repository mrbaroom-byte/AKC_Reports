# v3 consistency pass for public-fund documents.
# One identity across every page: the approved wave cover, a matching wave back cover, a wave band for
# quarterly statements, house fonts on the cover (no fallback fonts), full-bleed dark pages (no white
# strip at the page edge), and class colours only in charts.
import re, sys, os, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cv'))
from bs4 import BeautifulSoup
import wave  # cv/wave.py: transform(t, k) v2 cover -> wave cover, PAL, ART

SP = os.environ.get('AKC_SP', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/')
NIGHT = '#021640'
FONT = {'ar': ("'Alyamama','IBM Plex Sans Arabic',sans-serif", "'IBM Plex Sans Arabic','IBM Plex Sans',sans-serif"),
        'en': ("'IBM Plex Sans','IBM Plex Sans Arabic',sans-serif", "'IBM Plex Sans','IBM Plex Sans Arabic',sans-serif")}
# capital-markets charts must not borrow the private-equity indigo
SWAP_CM = {'#5F64C4': '#1F4E86', '#5f64c4': '#1F4E86', '#5257A8': '#1F4E86', '#5257a8': '#1F4E86'}

def lang_of(t):
    m = re.search(r'<html[^>]*lang="(\w\w)"', t)
    return m.group(1) if m else 'ar'

def section_span(t, start_pat):
    i = t.find(start_pat)
    if i < 0: return None
    d = 0
    for m in re.finditer(r'<(/?)section\b[^>]*>', t[i:]):
        d += -1 if m.group(1) else 1
        if d == 0: return i, i + m.end()

def div_span(t, i):
    d = 0
    for m in re.finditer(r'<(/?)div\b[^>]*>', t[i:]):
        d += -1 if m.group(1) else 1
        if d == 0: return i, i + m.end()

def back_css(k, lang):
    p = wave.PAL[k]; hf, bf = FONT[lang]
    return ('section.back.wvb{page:cover;break-before:page;width:210mm;height:297mm;position:relative;overflow:hidden;'
            f'background:{NIGHT};color:#fff}}'
            f'section.back.wvb .wvb-art{{position:absolute;left:0;right:0;top:118mm;height:140mm;background:url({wave.ART[k]}) center/210mm 140mm no-repeat;transform:scaleX(-1);opacity:.9}}'
            'section.back.wvb .wvb-flogo{position:absolute;top:58mm;left:50%;transform:translateX(-50%);width:74mm;height:auto}'
            'section.back.wvb .wvb-logo{position:absolute;top:96mm;left:50%;transform:translateX(-50%);width:46mm;height:auto}'
            f'section.back.wvb .wvb-bar{{position:absolute;top:86mm;left:50%;transform:translateX(-50%);width:14mm;height:.9mm;background:{p["bar"]}}}'
            f'section.back.wvb .wvb-ad{{position:absolute;bottom:12mm;left:18mm;right:18mm;text-align:center;font-family:{bf};font-size:7.6pt;line-height:1.85;color:{p["eyb"]};'
            f'border-top:.3mm solid rgba({p["line"]},.35);padding-top:3.5mm}}')

def band_css(k, lang):
    p = wave.PAL[k]; hf, bf = FONT[lang]
    side = 'right' if lang == 'ar' else 'left'
    # dark at both ends (numeral on one side, title on the other); the waves show through the middle
    shade = 'linear-gradient(90deg,rgba(2,22,64,.9) 0,rgba(2,22,64,.35) 38%,rgba(2,22,64,.35) 62%,rgba(2,22,64,.9) 100%)'
    return ('.band.wvq{position:relative;height:87mm;padding:0;margin:0 -17mm 8mm;overflow:hidden;'
            f'background:{shade},url({wave.ART[k]}) 0 -34mm/210mm 140mm no-repeat,{NIGHT}}}'
            '.band.wvq:after{display:none}'
            '.band.wvq svg.sig{display:none}'
            f'.band.wvq .q{{color:{p["soft"]}}}'
            f'.band.wvq .q small{{color:{p["eyb"]}}}'
            f'.band.wvq h1.bh{{font-family:{hf};color:#fff}}'
            f'.band.wvq .sub{{color:{p["soft"]}}}'
            f'.band.wvq:before{{content:"";position:absolute;bottom:0;{side}:17mm;width:14mm;height:.9mm;background:{p["bar"]};z-index:1}}')

LOGO_FILES = {'albilad-capital': 'assets/b1lad000-albilad-capital.png'}
NOTES = ('Approximate curve redrawn from the original chart', 'Approximate values measured from the original chart',
         'منحنى تقريبي مُعاد رسمه من الرسم الأصلي', 'قيم تقريبية مقاسة من الرسم الأصلي')

def fix_source(t, lang):
    # 1. list items that an earlier company-data update appended after </html> belong at the end of that list
    j = t.find('</html')
    if j >= 0 and '<li>' in t[j:]:
        junk = re.findall(r'<li>.*?</li>', t[j:], re.S)
        t = t[:j] + '</html>'
        for li in junk:
            if li in t: continue
            yr = re.search(r'(20\d\d)', li)
            prev = None
            if yr:
                y = int(yr.group(1))
                for py in range(y - 1, y - 6, -1):
                    m = [m for m in re.finditer(r'<li>[^<]*%d[^<]*</li>' % py, t) if 'إيرادات' in m.group(0) or 'revenue' in m.group(0).lower()]
                    if m: prev = m[-1]; break
            if prev: t = t[:prev.end()] + li + t[prev.end():]
    elif j >= 0:
        t = t[:j] + '</html>'
    # 2. production notes under redrawn charts are not part of the document
    for n in NOTES: t = re.sub(r'<div class="cap">\s*%s\s*</div>' % re.escape(n), '', t)
    # 3. partner logo slots: fill from the registry, drop slots of parties that have no logo (no empty boxes)
    def slot(m):
        slug = m.group(2)
        if slug in LOGO_FILES:
            return '<div class="pl"><img data-p="%s" src="%s" style="max-height:12.0mm" alt=""></div>%s' % (slug, LOGO_FILES[slug], m.group(1))
        return m.group(1)
    t = re.sub(r'<div class="pl"></div>(<div class="pn" data-p="([\w-]+)")', slot, t)
    # 4. letter subject lines are not chapter openers (they pushed the whole letter body to page 2)
    t = re.sub(r'<h1 class="h1 brk">((?:الموضوع|Subject)\s*:.*?)</h1>', r'<h2>\1</h2>', t, flags=re.S)
    # 5. CMA licence number reads 07074-37 in Arabic text too
    if lang == 'ar':
        t = re.sub(r'(?<![>\w-])07074-37(?![\w-])', '<bdo dir="ltr">07074-37</bdo>', t)
        t = re.sub(r'(?<![>\w-])٠٧٠٧٤-٣٧', '<bdo dir="ltr">٠٧٠٧٤-٣٧</bdo>', t)
    return t

GAL_H = {'ar': ('الأصول العقارية', 'الأصول العقارية الحالية', 'الأصول العقارية الإضافية التي يستهدفها الصندوق', 'الطرح الإضافي الثاني'),
         'en': ('Real Estate Assets', 'Current Real Estate Assets', 'Additional Real Estate Assets Targeted by the Fund', 'Second Subsequent Offering')}
GAL_CSS = ('.gal3{display:grid;grid-template-columns:repeat(3,46mm);justify-content:center;gap:5mm 7mm;margin:3mm 0 7mm;break-inside:avoid}'
           '.gal3 figure{margin:0;break-inside:avoid}.gal3 img{display:block;width:46mm;height:29mm;object-fit:cover;border-radius:1mm}'
           '.gal3 figcaption{font-size:7.8pt;line-height:1.4;color:#12284B;text-align:center;margin-top:1.6mm}')

def _gallery(items, start):
    return '<div class="gal3">' + ''.join('<figure><img src="assets/gal%02d-reit-asset.jpg" alt=""><figcaption>%s</figcaption></figure>' % (start + i, c)
                                          for i, c in enumerate(items)) + '</div>'

def reit_gallery(t, lang, kind):
    """Carry over the property photo gallery of the original REIT fact sheet / executive summary (12 assets)."""
    src = open(SP + 'pub2/html/reit/exec.%s.html' % lang, encoding='utf-8').read()
    H = GAL_H[lang]
    def items(h):
        m = re.search(r'<h2>%s</h2>\s*<ul>(.*?)</ul>' % re.escape(h), src, re.S)
        return re.findall(r'<li>(.*?)</li>', m.group(1), re.S) if m else []
    cur, add = items(H[1]), items(H[2])
    if len(cur) + len(add) != 12: return t
    if kind == 'exec':
        t = re.sub(r'(<h2>%s</h2>)\s*<ul>.*?</ul>' % re.escape(H[1]), lambda m: m.group(1) + _gallery(cur, 1), t, count=1, flags=re.S)
        t = re.sub(r'(<h2>%s</h2>)\s*<ul>.*?</ul>' % re.escape(H[2]), lambda m: m.group(1) + _gallery(add, 11), t, count=1, flags=re.S)
    else:
        sec = ('<h1 class="h1 brk">%s</h1><h2>%s</h2>%s<h2>%s</h2>%s' % (H[0], H[1], _gallery(cur, 1), H[2], _gallery(add, 11)))
        m = re.search(r'<h1 class="h1 brk">%s</h1>' % re.escape(H[3]), t)
        if not m: return t
        t = t[:m.start()] + sec + t[m.start():]
    return t.replace('</head>', '<style id="gal">' + GAL_CSS + '</style></head>', 1)

def apply(t, k, key=''):
    """t: html text, k: 'cm' or 're'. Returns the v3 html."""
    lang = lang_of(t); hf, bf = FONT[lang]
    t = fix_source(t, lang)
    if key in ('reit.exec.ar', 'reit.exec.en'): t = reit_gallery(t, lang, 'exec')
    if key in ('reit.factsheet.ar', 'reit.factsheet.en'): t = reit_gallery(t, lang, 'factsheet')
    # 1. cover: v2 -> wave (if not done yet), then house fonts instead of the unavailable Alexandria
    if '<section class="cover v2">' in t:
        t = wave.transform(t, k)
    t = t.replace('"Alexandria",sans-serif', hf).replace("'Alexandria',sans-serif", hf)
    # small cover texts in the body face
    # full-height dark pages: 297 mm (841.89 pt) fits Chrome's A4 page (841.92 pt); the old 296.6 mm left a white hairline
    css = ['table.t th,table.t td{overflow-wrap:break-word!important;hyphens:manual!important}'
           'table.t.sm th,table.t.sm td{padding:1.4mm 1.5mm}',
           f'section.cover.wv .wv-code,section.cover.wv .wv-dt,section.cover.wv .wv-ft{{font-family:{bf}}}',
           'section.cover,section.back,.orig{height:297mm!important}',
           # the code is set LTR, so its logical end resolves to the right in Arabic and collides with the logo
           ('section.cover.wv .wv-code{inset-inline-end:auto;right:auto;left:18mm}' if lang == 'ar'
            else 'section.cover.wv .wv-code{inset-inline-end:auto;left:auto;right:18mm}')]
    # Latin stacks fall back to DejaVu for Arabic letters (section letters «أ.», «ب.»): add the Arabic face
    t = t.replace("'IBM Plex Sans',sans-serif", "'IBM Plex Sans','IBM Plex Sans Arabic',sans-serif")
    # 2. back cover: v2 signal line -> wave
    sp = section_span(t, '<section class="back v2"')
    if sp:
        a, b = sp
        s = BeautifulSoup(t[a:b], 'html.parser')
        fl = s.select_one('img.flogo'); lg = s.select_one('img.logo'); ad = s.select_one('.ad')
        new = ('<section class="back wvb"><div class="wvb-art"></div>'
               + (f'<img class="wvb-flogo" src="{fl["src"]}" alt="">' if fl else '')
               + '<div class="wvb-bar"></div>'
               + (f'<img class="wvb-logo" src="{lg["src"]}" alt="">' if lg else '')
               + (f'<div class="wvb-ad">{ad.decode_contents()}</div>' if ad else '') + '</section>')
        t = t[:a] + new + t[b:]
        css.append(back_css(k, lang))
    # 3. quarterly band: v2 signal line -> wave band
    i = t.find('<div class="band v2">')
    if i >= 0:
        t = t[:i] + '<div class="band v2 wvq">' + t[i + len('<div class="band v2">'):]
        css.append(band_css(k, lang))
    # 4. chart colours of the class only
    if k == 'cm':
        for a_, b_ in SWAP_CM.items(): t = t.replace(a_, b_)
    t = t.replace('</head>', '<style id="v3">' + ''.join(css) + '</style></head>', 1)
    return t

if __name__ == '__main__':
    src, dst, k = sys.argv[1:4]
    open(dst, 'w', encoding='utf-8').write(apply(open(src, encoding='utf-8').read(), k))
