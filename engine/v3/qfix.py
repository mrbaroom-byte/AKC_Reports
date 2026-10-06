# Quarterly statements: changes requested in "Quarter Reports - Comments" (5 Oct 2026).
# Applied to the v3 HTML after style.apply(); idempotent (guarded by a marker).
import re, json, os
from bs4 import BeautifulSoup, NavigableString, Tag

MARK = '<!--qfix1-->'
AR_ORD = {'1': 'الأول', '2': 'الثاني', '3': 'الثالث', '4': 'الرابع'}
AR_M = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
EN_M = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
EN_AB = {m[:3].lower(): i for i, m in enumerate(EN_M)}; EN_AB['sept'] = 8
AR_ALIAS = {'ستمبر': 'سبتمبر', 'إبريل': 'أبريل', 'ابريل': 'أبريل', 'اغسطس': 'أغسطس', 'اكتوبر': 'أكتوبر'}
IND = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
TO_IND = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')

QCSS = """
/* qfix: quarterly comments 5 Oct 2026 */
.band.v2 .q{font-size:108pt!important;top:13mm!important}
.band.v2 .q small{font-size:22pt!important}
.band.v2 h1.bh{top:41mm!important}
.band.v2 .sub{top:53.5mm!important;font-size:10pt!important;line-height:1.35}
main h2{margin:4.5mm 0 2mm!important}
main h3{margin:3mm 0 1.5mm!important}
main p{margin:0 0 1.8mm}
.facts{margin-bottom:3.5mm!important}
.note{margin:1mm 0 3mm!important}
figure.chart{margin:1mm 0 3.5mm!important}
.note.disc{break-inside:auto!important;margin-top:1.5mm!important;font-size:7.8pt;line-height:1.6;border:.25mm solid #DCE3EE!important;border-inline-start:.9mm solid ACC!important;background:#F5F7FB!important;padding:3mm 3.6mm!important}
h2.disc-h,h3.disc-h{break-after:avoid;margin-top:4mm!important}
sup.fn{font-size:.62em;vertical-align:super;line-height:0;margin-inline-start:.4mm}
table.t.eqt td{vertical-align:top}
table.t.eqt td.f{direction:ltr;text-align:left;unicode-bidi:isolate;font-family:'Cambria Math','STIX Two Math','IBM Plex Sans',serif;font-style:italic;font-size:9pt;color:#12284B;white-space:nowrap}
table.t.eqt td.w{direction:ltr;text-align:left;unicode-bidi:isolate;font-family:'IBM Plex Sans',sans-serif;font-size:7.6pt;line-height:1.55;color:#3A4458}
.pct{direction:ltr;unicode-bidi:isolate}
"""
QCSS_AR = """
h2 .n,h3 .n{font-family:'Alyamama','IBM Plex Sans Arabic',serif!important;font-weight:700!important;margin-left:2.8mm!important}
"""
# REIT quarterlies (5 Oct 2026 decision): 2030 font sizes and layout, REIT bronze colours kept, own cover art.
QCSS_REIT = """
main h4{font-family:'IBM Plex Sans Arabic','IBM Plex Sans',sans-serif;font-weight:600;font-size:9.6pt;line-height:1.4;color:#12284B;margin:2.6mm 0 1.4mm;break-after:avoid}
main h4 .n{color:ACC;margin-inline-end:1.6mm;font-family:'IBM Plex Sans',sans-serif;font-weight:500}
main h2 .n{margin-inline-end:2.2mm}
"""
INFO_RE = re.compile(r'^(للحصول على المزيد|إشعار مهم|For more information|For further information|Important Notice|Disclaimer)', re.I)

def demote_reit(soup):
    """REIT statements set numbered sections as h1.h1 (17pt, rule); 2030 sets them as h2. Shift one level down."""
    n = 0
    if not soup.select('main h1.h1, h1.h1'):
        for h in soup.find_all('h3'):
            if INFO_RE.match(_txt(h)): h.name = 'h2'; n += 1
        return n
    for h in soup.find_all('h3'):
        if INFO_RE.match(_txt(h)): h.name = 'h2'; h['data-up'] = '1'
        else: h.name = 'h4'
        n += 1
    for h in soup.find_all('h2'):
        if h.get('data-up'): del h['data-up']
        else: h.name = 'h3'; n += 1
    for h in soup.find_all('h1', class_='h1'):
        h.name = 'h2'; c = [x for x in h.get('class', []) if x != 'h1']
        if c: h['class'] = c
        else: del h['class']
        n += 1
    return n

# ---------- icons from the bank (template library slide 9), fund-class colour as the only accent ----------
import importlib.util as _iu
_sp = _iu.spec_from_file_location('icons', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons.py'))
ICONS = _iu.module_from_spec(_sp); _sp.loader.exec_module(ICONS)
CLASS_LABEL = {'cm': ('أسواق المال', 'Capital Markets'), 're': ('العقار', 'Real Estate')}
QCSS_ICO = """
main h2 .ico{width:5.2mm;height:5.2mm;vertical-align:-1.2mm;margin-inline-end:2.2mm;flex:none}
.band.v2 .cls{position:absolute;right:17mm;top:31mm;display:flex;align-items:center;gap:2mm;font-family:'IBM Plex Sans Arabic','IBM Plex Sans',sans-serif;font-size:8.6pt;font-weight:500;color:#DCE3EE;padding:1.2mm 3mm 1.2mm 3mm;border:.25mm solid rgba(220,227,238,.35);border-radius:4mm;z-index:2}
.band.v2 .cls .ico{width:4.6mm;height:4.6mm}
html[dir=ltr] .band.v2 .cls,body.en .band.v2 .cls{right:auto;left:17mm}
"""

def add_icons(soup, cls, acc, lang):
    n = 0
    band = soup.find('div', class_='band')
    if band is not None and not band.find(class_='cls'):
        lab = CLASS_LABEL[cls][0 if lang == 'ar' else 1]
        chip = BeautifulSoup('<div class="cls">%s<span>%s</span></div>' % (ICONS.icon(cls, acc, ink='#DCE3EE', size='4.6mm'), lab), 'html.parser')
        bh = band.find('h1')
        (bh.insert_before if bh else band.append)(chip)
    for h in soup.find_all('h2'):
        if h.find('svg', class_='ico') or h.find_parent(class_='band'): continue
        name = ICONS.pick(_txt(h)) or 'factsheet'
        if name == 'CLASS': name = cls
        h.insert(0, BeautifulSoup(ICONS.icon(name, acc, size='5.2mm'), 'html.parser')); n += 1
    return n

def _txt(e): return re.sub(r'\s+', ' ', e.get_text(' ', strip=True))

def fmt_ar(d, m, y, ind, hijri_m=True):
    s = ('%d %s %sم' % (d, AR_M[m], y)) if d else ('%s %sم' % (AR_M[m], y))
    return s.translate(TO_IND) if ind else s

def fmt_en(d, m, y):
    return ('%d %s %s' % (d, EN_M[m], y)) if d else ('%s %s' % (EN_M[m], y))

def norm_date(label, lang):
    """Chart date labels to «29 سبتمبر 2024م» / «16 July 2024»; keeps a (Listing Date) note."""
    raw = label
    ind = bool(re.search('[٠-٩]', raw))
    t = raw.translate(IND)
    for a, b in AR_ALIAS.items(): t = t.replace(a, b)
    note = ''
    m = re.search(r'\(?\s*(تاريخ الإدراج|تاريخ الادراج|Listing Date)\s*\)?', t)
    if m:
        note = m.group(1).replace('الادراج', 'الإدراج'); t = (t[:m.start()] + t[m.end():]).strip()
    t = t.strip().rstrip('م').strip()
    t = re.sub(r'(\d{4})G\b', r'\1', t)
    d = mo = y = None
    if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', t):
        d, mo, y = t.split('/'); d = int(d); mo = int(mo) - 1
    elif re.fullmatch(r'\d{1,2}-[A-Za-z]{3,4}-\d{2,4}', t):
        a, b, c = t.split('-'); d = int(a); mo = EN_AB.get(b[:4].lower(), EN_AB.get(b[:3].lower())); y = c if len(c) == 4 else '20' + c
    elif re.fullmatch(r'[A-Za-z]{3,9}-\d{2,4}', t):
        b, c = t.split('-'); mo = EN_AB.get(b[:3].lower()); y = c if len(c) == 4 else '20' + c
    elif re.fullmatch(r'[A-Za-z]{3,9}\.? \d{1,2}, \d{4}', t):
        b, rest = t.split(' ', 1); dd, y = rest.split(', '); d = int(dd); mo = EN_AB.get(b[:3].lower())
    elif re.fullmatch(r'\d{1,2} [A-Za-z]{3,9}\.? \d{2,4}', t):
        a, b, c = t.split(' '); d = int(a); mo = EN_AB.get(b.rstrip('.')[:4].lower(), EN_AB.get(b[:3].lower())); y = c if len(c) == 4 else '20' + c
    elif re.fullmatch(r'[A-Za-z]{3,9}\.? \d{4}', t):
        b, y = t.split(' '); mo = EN_AB.get(b.rstrip('.')[:4].lower(), EN_AB.get(b[:3].lower()))
    else:
        mm = re.fullmatch(r'(?:(\d{1,2}) )?(\S+?)[ -](\d{2,4})', t)
        if mm and mm.group(2) in AR_M:
            d = int(mm.group(1)) if mm.group(1) else None; mo = AR_M.index(mm.group(2)); y = mm.group(3)
            if len(y) == 2: y = '20' + y
    if mo is None or y is None: return None
    if lang == 'ar':
        out = fmt_ar(d, mo, y, ind)
        if note: out = out + ' (' + note + ')'
    else:
        out = fmt_en(d, mo, y)
        if note: out = out + ' (' + note + ')'
    return out

def _two(attrs, l1, l2, lang):
    if lang == 'ar': l1, l2 = '\u202b' + l1 + '\u202c', '\u202b' + l2 + '\u202c'
    mx = re.search(r'\bx="([\d.]+)"', attrs); xx = mx.group(1) if mx else '0'
    return attrs + '<tspan x="%s" dy="0">%s</tspan><tspan x="%s" dy="8.6">%s</tspan>' % (xx, l1, xx, l2)

def fix_svg_dates(h, lang):
    def one_svg(sm):
        svg = sm.group(0)
        labs = [t for t in re.findall(r'<text[^>]*>([^<]*\d[^<]*)</text>', svg) if re.search(r'[A-Za-z\u0600-\u06FF/]', t)]
        dense = len(labs) > 5
        def rep(m):
            attrs, txt = m.group(1), m.group(2)
            if '\u202b' in txt: return m.group(0)
            n = norm_date(txt, lang) if re.search(r'[A-Za-z\u0600-\u06FF/]', txt) else None
            if not n: return m.group(0)
            mx = re.search(r'\bx="([\d.]+)"', attrs); x = float(mx.group(1)) if mx else 320
            if 'text-anchor="middle"' in attrs:
                if x > 612: attrs = attrs.replace('text-anchor="middle"', 'text-anchor="end"')
                elif x < 30: attrs = attrs.replace('text-anchor="middle"', 'text-anchor="start"')
            attrs = re.sub(r'font-size="(9|10)"', 'font-size="%s"' % ('7.4' if dense else '8.4'), attrs)
            mnote = re.match(r'^(.*?) \((تاريخ الإدراج|Listing Date)\)$', n)
            if mnote: return _two(attrs, mnote.group(1), '(' + mnote.group(2) + ')', lang) + m.group(3)
            if dense and n.count(' ') >= 2:
                w = n.split(' '); return _two(attrs, ' '.join(w[:-1]), w[-1], lang) + m.group(3)
            if lang == 'ar': n = '\u202b' + n + '\u202c'
            return attrs + n + m.group(3)
        return re.sub(r'(<text[^>]*>)([^<]*\d[^<]*)(</text>)', rep, svg)
    return re.sub(r'<svg.*?</svg>', one_svg, h, flags=re.S)

# ---------- NAV / unit price bar chart: series by measure, groups by date ----------
NAV_RE = re.compile(r'صافي|Net Asset|NAV', re.I)
MKT_RE = re.compile(r'سعر الوحدة في السوق|Market|Trading|Unit Price|سعر الوحدة', re.I)
C_NAV, C_MKT = '#12284B', '#3B7DD8'
FUND_ACC = {'reit': '#9A6A45'}

def parse_bars(svg):
    els = re.findall(r'<(rect|text)\b([^>]*?)(?:/>|></rect>|>([^<]*)</text>)', svg)
    ticks = []; groups = []; cur = []
    for tag, attrs, txt in els:
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
        if tag == 'rect' and 'height' in a and a.get('fill', '').upper() not in ('#FFFFFF', 'NONE', '') and float(a.get('height', 0)) > 0 and float(a.get('width', 99)) < 60:
            cur.append({'fill': a['fill'], 'x': float(a['x']), 'y': float(a['y']), 'h': float(a['height']), 'v': None})
        elif tag == 'text':
            if a.get('text-anchor') == 'end': ticks.append((float(a['y']), txt)); continue
            if cur and cur[-1]['v'] is None and abs(float(a['y']) - (cur[-1]['y'] - 3)) < 4: cur[-1]['v'] = txt; continue
            if cur and float(a.get('y', 0)) > 195: groups.append((txt, cur)); cur = []
    return ticks, groups

def bar_svg(groups, series, colors, ymax, ticks):
    # groups: [label]; series: [name]; values[g][s]
    W, H, x0, x1, y0, y1 = 640, 230, 46, 630, 190.0, 30.5
    out = ['<svg viewBox="0 0 640 230" width="100%" style="direction:ltr">']
    for tv in ticks:
        y = y0 - (y0 - y1) * float(tv) / ymax
        out.append('<line x1="46" x2="630" y1="%.1f" y2="%.1f" stroke="#DCE3EE" stroke-width="1"/>' % (y, y))
        out.append('<text x="40" y="%.1f" text-anchor="end" font-size="10" fill="#5A6478">%s</text>' % (y + 3.5, tv))
    n = len(groups); slot = (x1 - x0) / n; bw = 20.8; gap = 1.2
    for gi, (lab, vals) in enumerate(groups):
        cx = x0 + slot * (gi + .5); k = len(vals); start = cx - (k * bw + (k - 1) * gap) / 2
        for si, v in enumerate(vals):
            if v is None: continue
            try: fv = float(str(v).replace(',', ''))
            except ValueError: continue
            hgt = (y0 - y1) * fv / ymax; x = start + si * (bw + gap)
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1" fill="%s"/>' % (x, y0 - hgt, bw, hgt, colors[si]))
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="8.5" fill="#0B1733">%s</text>' % (x + bw / 2, y0 - hgt - 3, v))
        if n > 4 and ' ' in lab.strip():
            w = lab.strip().split(' '); top, bot = ' '.join(w[:-1]), w[-1]
            if re.search(r'[\u0600-\u06FF]', lab): top, bot = '\u202b' + top + '\u202c', '\u202b' + bot + '\u202c'
            out.append('<text x="%.1f" y="202" text-anchor="middle" font-size="7.6" fill="#5A6478"><tspan x="%.1f" dy="0">%s</tspan><tspan x="%.1f" dy="9">%s</tspan></text>' % (cx, cx, top, cx, bot))
        else:
            if re.search(r'[\u0600-\u06FF]', lab) and '\u202b' not in lab: lab = '\u202b' + lab + '\u202c'
            out.append('<text x="%.1f" y="204" text-anchor="middle" font-size="8.4" fill="#5A6478">%s</text>' % (cx, lab))
    out.append('</svg>')
    return ''.join(out)

def fix_nav_chart(fig, lang):
    svg = fig.find('svg'); mleg = fig.find(class_='mleg')
    if svg is None or mleg is None: return False
    spans = mleg.find_all('span')
    names = [_txt(sp) for sp in spans]
    cols = []
    for sp in spans:
        i = sp.find('i'); m = re.search(r'background:\s*(#[0-9A-Fa-f]{6})', i.get('style', '')) if i else None
        cols.append(m.group(1).upper() if m else None)
    ticks, groups = parse_bars(str(svg))
    if names and cols and all(cols) and (any(NAV_RE.search(nm) for nm in names)):
        want = {c: (C_NAV if NAV_RE.search(nm) else C_MKT) for c, nm in zip(cols, names)}
        if any(k != v for k, v in want.items()):
            sv = str(svg); tmp = {k: '#TMP%d' % i for i, k in enumerate(want)}
            for k, t in tmp.items(): sv = re.sub('fill="%s"' % k, 'fill="%s"' % t, sv, flags=re.I)
            for k, t in tmp.items(): sv = sv.replace('fill="%s"' % t, 'fill="%s"' % want[k])
            nsvg = BeautifulSoup(sv, 'html.parser'); svg.replace_with(nsvg); svg = fig.find('svg')
            for sp, c in zip(spans, cols):
                i = sp.find('i')
                if i: i['style'] = re.sub(r'#[0-9A-Fa-f]{6}', want[c], i.get('style', ''))
            ticks, groups = parse_bars(str(svg))
    if len(groups) < 1 or not names or not ticks or len(groups) > 6: return False
    if any(r['v'] is None for _, rs in groups for r in rs): return False
    if str(svg).count('<rect') != sum(len(rs) for _, rs in groups): return False
    labels = [g[0] for g in groups]
    measures_in_legend = any(NAV_RE.search(nm) for nm in names) and any(MKT_RE.search(nm) and not NAV_RE.search(nm) for nm in names)
    measures_in_groups = any(NAV_RE.search(l) for l in labels) and any(MKT_RE.search(l) and not NAV_RE.search(l) for l in labels)
    tick_vals = [t for _, t in sorted(ticks, key=lambda z: -z[0])]
    try: ymax = max(float(t.replace(',', '')) for t in tick_vals)
    except ValueError: return False
    if measures_in_groups and not measures_in_legend:
        # transpose: groups become dates (legend entries), series become measures
        col2name = {c.upper(): nm for c, nm in zip(cols, names) if c}
        dates = names
        meas = labels
        vals = {}
        for lab, rs in groups:
            for r in rs: vals[(col2name.get(r['fill'].upper()), lab)] = r['v']
        order = sorted(range(len(meas)), key=lambda i: 0 if MKT_RE.search(meas[i]) and not NAV_RE.search(meas[i]) else 1)
        meas = [meas[i] for i in order]
        new_groups = [(norm_date(d, lang) or d, [vals.get((d, m)) for m in meas]) for d in dates]
        series = meas
    elif measures_in_legend:
        series = names
        new_groups = [(norm_date(lab, lang) or lab, [r['v'] for r in rs]) for lab, rs in groups]
        # legend order follows bar order inside a group
    else:
        return False
    colors = [C_NAV if NAV_RE.search(s) else C_MKT for s in series]
    svg.replace_with(BeautifulSoup(bar_svg(new_groups, series, colors, ymax, tick_vals), 'html.parser'))
    mleg.clear()
    for s, c in zip(series, colors):
        sp = BeautifulSoup('<span><i style="background:%s"></i>%s</span>' % (c, s), 'html.parser')
        mleg.append(sp)
    return True

# ---------- percent sign after the number, read left to right ----------
NUM = r'[\d٠-٩][\d٠-٩.,٫٬]*'
PCT_RES = [
    (re.compile(r'[%٪](' + NUM + r')-'), lambda m: '-' + m.group(1) + '%'),
    (re.compile(r'[%٪]-(' + NUM + r')'), lambda m: '-' + m.group(1) + '%'),
    (re.compile(r'[%٪](' + NUM + r')'), lambda m: m.group(1) + '%'),
    (re.compile(r'(?<![\d٠-٩.,])-?(' + NUM + r')[%٪]-'), None),
]

def fix_pct(soup, lang):
    n = 0
    for s in list(soup.find_all(string=True)):
        if s.parent is None or s.parent.name in ('style', 'script', 'text', 'title') or s.find_parent('svg'): continue
        t = str(s)
        if '%' not in t and '٪' not in t: continue
        parts = []; last = 0; changed = False
        pat = re.compile(r'[%٪](' + NUM + r')(-?)|[%٪]-(' + NUM + r')|(-?)(' + NUM + r')[%٪](-?)')
        for m in pat.finditer(t):
            if m.group(1):
                val = ('-' if m.group(2) else '') + m.group(1) + '%'
            elif m.group(3):
                val = '-' + m.group(3) + '%'
            else:
                neg = m.group(4) or m.group(6)
                val = ('-' if neg else '') + m.group(5) + '%'
                if lang == 'en' and not m.group(6): continue  # already correct in English
            parts.append(t[last:m.start()]); parts.append(('PCT', val)); last = m.end(); changed = True
        if not changed: continue
        parts.append(t[last:])
        new = []
        for p in parts:
            if isinstance(p, tuple):
                if lang == 'ar':
                    b = soup.new_tag('bdi'); b['dir'] = 'ltr'; b['class'] = 'pct'; b.string = p[1]; new.append(b)
                else: new.append(NavigableString(p[1]))
            elif p: new.append(NavigableString(p))
        for x in new: s.insert_before(x)
        s.extract(); n += 1
    return n

def fix_footnotes(soup):
    n = 0
    for e in soup.find_all(['th', 'td', 'span', 'b']):
        if any(isinstance(k, Tag) for k in e.children): continue
        t = e.get_text()
        m = re.search(r'([ء-يa-z\)])(\d)\s*$', t)
        if not m or re.search(r'[A-Z]\d\s*$', t): continue
        if re.search(r'\d\s*$', t) and re.search(r'(Q|H|SOFR|AB)\d\s*$', t): continue
        e.string = t[:m.start(2)]
        sup = soup.new_tag('sup'); sup['class'] = 'fn'; sup.string = m.group(2); e.append(sup); n += 1
    return n

DISC_RE = re.compile(r'^\s*(إشعار مهم|اشعار مهم|disclaimer|important notice)\s*:?\s*$', re.I)

def disc_block(soup):
    for h in soup.find_all(['h2', 'h3']):
        if DISC_RE.match(_txt(h)): return h
    return None

def fix_disclaimer(soup, lang, donor_html):
    h = disc_block(soup)
    if h is None and donor_html:
        d = BeautifulSoup(donor_html, 'html.parser'); dh = disc_block(d)
        if dh is not None:
            body = []
            for sib in dh.find_next_siblings():
                if sib.name in ('h1', 'h2', 'h3'): break
                body.append(sib)
            main = soup.find('main') or soup.body
            nh = soup.new_tag('h2'); nh.string = _txt(dh); main.append(nh)
            for b in body: main.append(BeautifulSoup(str(b), 'html.parser'))
            h = nh
    if h is None: return 'none'
    h['class'] = (h.get('class') or []) + ['disc-h']
    sibs = []
    for sib in h.find_next_siblings():
        if sib.name in ('h1', 'h2', 'h3') or (sib.name == 'section'): break
        sibs.append(sib)
    if len(sibs) == 1 and sibs[0].name == 'div' and 'note' in (sibs[0].get('class') or []):
        sibs[0]['class'] = sibs[0]['class'] + ['disc']; return 'boxed'
    box = soup.new_tag('div'); box['class'] = ['note', 'disc']
    h.insert_after(box)
    for sib in sibs:
        if sib.name == 'p':
            for k in list(sib.contents): box.append(k)
            box.append(soup.new_tag('br'))
            sib.decompose()
        else: box.append(sib.extract())
    if box.contents and getattr(box.contents[-1], 'name', None) == 'br': box.contents[-1].extract()
    return 'wrapped'

def fix_equations(soup):
    n = 0
    for h in soup.find_all(['h2', 'h3']):
        if not re.search(r'المعادلات|equation|formula', _txt(h), re.I): continue
        tw = h.find_next(class_='tw'); tb = tw.find('table') if tw else None
        if tb is None: continue
        tb['class'] = (tb.get('class') or []) + ['eqt']
        for tr in tb.find_all('tr'):
            for td in tr.find_all(['td', 'th']):
                t = _txt(td)
                if re.match(r'^(where|حيث)\b', t, re.I): td['class'] = (td.get('class') or []) + ['w']
                elif re.search(r'[=÷√σβα∑Σ]', t) and not re.search(r'[؀-ۿ]', t): td['class'] = (td.get('class') or []) + ['f']
        n += 1
    return n

def fix_cover(soup, lang):
    band = soup.find('div', class_='band')
    if band is None: return False
    q = band.find(class_='q'); sub = band.find(class_='sub')
    if q is None or sub is None: return False
    num = (q.find(string=True, recursive=False) or '').strip()
    yr = _txt(q.find('small')) if q.find('small') else ''
    num = num.translate(IND); yr = yr.translate(IND)
    if num not in AR_ORD or not re.fullmatch(r'\d{4}', yr): return False
    sub.string = ('تقرير المستثمر عن الربع %s %sم' % (AR_ORD[num], yr)) if lang == 'ar' else ('Investor Report Q%s %s' % (num, yr))
    return True

def fix_website(h):
    return re.sub(r'(<br>|<p>)\s*alkhabeer\.com\s*(?=</p>|<br>)', r'\1www.alkhabeer.com', h)

def apply(html, lang, fund, donor=None):
    global C_MKT
    if MARK in html: return html, {}
    rep = {}
    acc = FUND_ACC.get(fund, '#3B7DD8'); C_MKT = acc
    cls = 're' if fund == 'reit' else 'cm'
    html = fix_website(html)
    soup = BeautifulSoup(html, 'html.parser')
    if fund == 'reit': rep['demote'] = demote_reit(soup)
    rep['cover'] = fix_cover(soup, lang)
    rep['nav'] = 0
    for fig in soup.find_all('figure'):
        if fig.find(class_='mleg') and fig.find('svg') and fig.find('svg').find('rect'):
            if fix_nav_chart(fig, lang): rep['nav'] += 1
    rep['pct'] = fix_pct(soup, lang)
    rep['fn'] = fix_footnotes(soup)
    rep['disc'] = fix_disclaimer(soup, lang, donor)
    rep['eq'] = fix_equations(soup)
    rep['ico'] = add_icons(soup, cls, acc, lang)
    out = str(soup)
    out = fix_svg_dates(out, lang)
    if lang == 'en':
        out = re.sub(r'(?<=\d{4})G\b', '', out)
    css = QCSS.replace('ACC', acc) + (QCSS_AR if lang == 'ar' else '') + QCSS_ICO
    if fund == 'reit': css += QCSS_REIT.replace('ACC', acc)
    out = out.replace('</head>', '<style>' + css + '</style>' + MARK + '</head>', 1)
    return out, rep
