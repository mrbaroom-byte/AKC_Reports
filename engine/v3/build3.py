# v3: fund-document HTML -> editable Word that matches the PDF.
#  * Arabic paragraphs are right-to-left with logical (start) alignment. Word mirrors jc="right" in a bidi
#    paragraph to the LEFT, which is what made the v2 Word files look left-aligned; we never write it.
#  * Arial everywhere (styles, theme, complex-script slots): installed on Windows, macOS, iOS and Android.
#  * Cover, back cover and original signed pages are full-bleed page images in zero-margin sections.
#  * Running header (fund · document) and page-number footer as in the PDF.
#  * Every block of the HTML main flow becomes native text, a native table, or a picture of the element;
#    a missing picture is an error, never a silent skip.
import sys, os, re, json, asyncio, zipfile, shutil
from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.shared import Pt, Mm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import ooxml_order

NAVY = RGBColor(0x12, 0x28, 0x4B); BLUE = RGBColor(0x3B, 0x7D, 0xD8); BRONZE = RGBColor(0x9A, 0x6A, 0x45)
GREY = RGBColor(0x5A, 0x64, 0x78); INK = RGBColor(0x0E, 0x1E, 0x3A)
FONT = 'Arial'
TEXT_BLOCKS = {'p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'nav'}

class MissingPicture(Exception): pass

# ---------- low-level helpers ----------
def el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items(): e.set(qn(k), str(v))
    return e

def ppr(p): return p._p.get_or_add_pPr()

def set_par(p, rtl, align=None, before=0, after=4, line=1.25, ind_start=None, hanging=None, keep_next=False):
    pr = ppr(p)
    if keep_next: pr.append(el('w:keepNext'))
    if rtl: pr.append(el('w:bidi', **{'w:val': '1'}))
    pf = p.paragraph_format
    pf.space_before = Pt(before); pf.space_after = Pt(after); pf.line_spacing = line
    if ind_start is not None:
        ind = el('w:ind', **{'w:left': int(ind_start)})
        if hanging: ind.set(qn('w:hanging'), str(int(hanging)))
        pr.append(ind)  # in a bidi paragraph w:left is the leading (right) side
    if align == 'center': p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == 'end':  # trailing edge: physical left in Arabic, right in English
        pr.append(el('w:jc', **{'w:val': 'left' if rtl else 'right'}))
    # 'start' (default): no jc at all -> right in Arabic, left in English

def fonts(rPr):
    for old in rPr.findall(qn('w:rFonts')): rPr.remove(old)
    rPr.insert(0, el('w:rFonts', **{'w:ascii': FONT, 'w:hAnsi': FONT, 'w:cs': FONT, 'w:eastAsia': FONT}))

def run(p, text, rtl, size=10, bold=False, color=None, italic=False):
    r = p.add_run(text); rPr = r._r.get_or_add_rPr(); fonts(rPr)
    r.font.size = Pt(size); rPr.append(el('w:szCs', **{'w:val': int(size * 2)}))
    if bold: r.bold = True; rPr.append(el('w:bCs'))
    if italic: r.italic = True
    if color is not None: r.font.color.rgb = color
    if rtl: rPr.append(el('w:rtl'))
    return r

_ICO_CACHE = {}
def heading_icon(p, e):
    """Bank icon placed before a heading (inline SVG in the HTML) -> inline PNG run at the start of the paragraph."""
    sv = e.find('svg', class_='ico')
    if sv is None: return 0
    import cairosvg, hashlib
    src = str(sv); src = re.sub(r'\swidth="[^"]*"|\sheight="[^"]*"', '', src, count=2)
    if 'xmlns=' not in src: src = src.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    src = src.replace('viewbox=', 'viewBox=').replace('<svg', '<svg width="96" height="96"', 1)
    key = hashlib.md5(src.encode()).hexdigest()
    if key not in _ICO_CACHE:
        fn = '/tmp/ico_%s.png' % key; cairosvg.svg2png(bytestring=src.encode(), write_to=fn, output_width=96, output_height=96); _ICO_CACHE[key] = fn
    r = p.add_run(); r.add_picture(_ICO_CACHE[key], width=Mm(4.6), height=Mm(4.6))
    rp = r._r.get_or_add_rPr(); pos = OxmlElement('w:position'); pos.set(qn('w:val'), '-4'); rp.append(pos)
    sp = p.add_run('\u00a0\u00a0')
    sv.decompose()
    return 1

def add_runs(p, node0, rtl, size=10, bold=False, color=None):
    def walk(node, b, c):
        if isinstance(node, NavigableString):
            t = re.sub(r'\s+', ' ', str(node))
            if t: run(p, t, rtl, size, b, c)
            return
        if not isinstance(node, Tag): return
        if node.name == 'br': p.add_run().add_break(); return
        if node.name in ('svg', 'style', 'script'): return
        nb = b or node.name in ('b', 'strong') or (node.name == 'span' and 'n' in (node.get('class') or []))
        nc = c
        if node.name == 'span' and 'n' in (node.get('class') or []): nc = ACCENT[0]
        # numbers/phones isolated LTR in Arabic stay LTR
        if node.name in ('bdi', 'bdo') and node.get('dir') == 'ltr' and rtl:
            t = re.sub(r'\s+', ' ', node.get_text())
            if t: run(p, '‎' + t + '‎', False, size, nb, nc)  # LTR run framed by LRM marks
            return
        for ch in node.children: walk(ch, nb, nc)
        if node.name == 'span' and 'n' in (node.get('class') or []) and node.get_text(strip=True):
            run(p, '\u00a0\u00a0', rtl, size, nb, nc)  # gap between a heading number and its title
    walk(node0, bold, color)
    trs = [r for r in p.runs if r._r.find(qn('w:drawing')) is None and r.text.strip()]
    if trs:
        trs[0].text = trs[0].text.lstrip(); trs[-1].text = trs[-1].text.rstrip()

ACCENT = [BLUE]

def para(doc, node, rtl, size=10, bold=False, color=None, after=4, align=None, line=1.3, keep_next=False):
    p = doc.add_paragraph(); set_par(p, rtl, align, after=after, line=line, keep_next=keep_next)
    add_runs(p, node, rtl, size, bold, INK if color is None else color)
    return p

def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr(); tcPr.append(el('w:shd', **{'w:val': 'clear', 'w:color': 'auto', 'w:fill': hexcolor}))

def cell_margins(t, mm=1.6):
    tblPr = t._tbl.tblPr; mar = el('w:tblCellMar')
    for side in ('top', 'bottom'): mar.append(el('w:' + side, **{'w:w': int(mm * 30), 'w:type': 'dxa'}))
    for side in ('left', 'right'): mar.append(el('w:' + side, **{'w:w': int(mm * 57), 'w:type': 'dxa'}))
    tblPr.append(mar)

def borders(t, color='DCE3EE', inside=True):
    tblPr = t._tbl.tblPr; b = el('w:tblBorders')
    for side in ('top', 'bottom') + (('insideH',) if inside else ()):
        b.append(el('w:' + side, **{'w:val': 'single', 'w:sz': 4, 'w:space': 0, 'w:color': color}))
    for side in ('left', 'right', 'insideV'):
        b.append(el('w:' + side, **{'w:val': 'nil'}))
    tblPr.append(b)

def table_base(t, rtl):
    tblPr = t._tbl.tblPr
    for old in tblPr.findall(qn('w:tblW')): tblPr.remove(old)
    tblPr.append(el('w:tblW', **{'w:w': 5000, 'w:type': 'pct'}))
    if rtl: tblPr.append(el('w:bidiVisual'))
    borders(t); cell_margins(t)

def html_table(doc, tbl, rtl):
    rows = tbl.find_all('tr')
    if not rows: return
    ncol = max(sum(int(c.get('colspan', 1)) for c in r.find_all(['td', 'th'])) for r in rows)
    t = doc.add_table(rows=0, cols=ncol); table_base(t, rtl)
    for r in rows:
        cells = r.find_all(['td', 'th']); row = t.add_row().cells; ci = 0
        head = r.parent.name == 'thead' or (cells and all(c.name == 'th' for c in cells))
        for c in cells:
            span = int(c.get('colspan', 1))
            if ci >= ncol: break
            cell = row[ci]
            if span > 1 and ci + span - 1 < ncol: cell = cell.merge(row[ci + span - 1])
            p = cell.paragraphs[0]; set_par(p, rtl, after=0, line=1.1)
            add_runs(p, c, rtl, 8.5 if ncol < 7 else (7.5 if ncol < 9 else 7), bold=head, color=RGBColor(255, 255, 255) if head else INK)
            if head: shade(cell, '12284B')
            ct = c.get_text(' ', strip=True)
            if ncol >= 7 and len(ct) <= 16 and re.fullmatch(r'[\d٠-٩.,،٫٬%\s\-–()+/]+', ct or 'x'):
                cell._tc.get_or_add_tcPr().append(el('w:noWrap'))
            ci += span
    if ncol >= 9:  # wide tables: share the width by content so figures fit on one line
        import math
        lens = [1] * ncol
        for r in rows:
            ci = 0
            for c in r.find_all(['td', 'th']):
                sp = int(c.get('colspan', 1))
                if sp == 1 and ci < ncol:
                    for w in (c.get_text(' ', strip=True).split() or ['']):
                        num = re.fullmatch(r'[\d٠-٩.,،٫٬%\-–()+/]+', w) is not None
                        lens[ci] = max(lens[ci], len(w) * (1.2 if num else 0.95))
                ci += sp
        tot = int(176 / 25.4 * 1440); wts = [x + 1.5 for x in lens]; sw = sum(wts)
        ws = [int(tot * w / sw) for w in wts]
        grid = t._tbl.tblGrid
        for gc, w in zip(grid.findall(qn('w:gridCol')), ws): gc.set(qn('w:w'), str(w))
        for row in t.rows:
            for tc in row._tr.findall(qn('w:tc')):
                pass
        for row in t._tbl.findall(qn('w:tr')):
            ci = 0
            for tc in row.findall(qn('w:tc')):
                pr = tc.get_or_add_tcPr(); span = 1
                gs = pr.find(qn('w:gridSpan'))
                if gs is not None: span = int(gs.get(qn('w:val')))
                for old in pr.findall(qn('w:tcW')): pr.remove(old)
                pr.insert(0, el('w:tcW', **{'w:w': sum(ws[ci:ci + span]), 'w:type': 'dxa'}))
                ci += span
        tblPr = t._tbl.tblPr; tblPr.append(el('w:tblLayout', **{'w:type': 'fixed'}))
    trh = t.rows[0]._tr.get_or_add_trPr(); trh.append(el('w:tblHeader'))
    sp = doc.add_paragraph(); set_par(sp, rtl, after=2)

def facts(doc, node, rtl):
    # captions/headings/notes that sit inside the facts block (e.g. «للحصول على مزيد من المعلومات»)
    for k in node.children:
        if not isinstance(k, Tag): continue
        kc = ' '.join(k.get('class') or [])
        if kc.startswith('fg') or kc.startswith('fc') or not k.get_text(strip=True): continue
        if 'note' in kc: continue
        para(doc, k, rtl, size=10.5, bold=True, color=NAVY, after=3, keep_next=True)
    t = doc.add_table(rows=0, cols=2); table_base(t, rtl)
    for fc in node.select('.fc'):
        lab = fc.find('span'); val = fc.find('b')
        row = t.add_row().cells; row[0].width = Mm(55); row[1].width = Mm(121)
        for cell, n, b, colr in ((row[0], lab, False, GREY), (row[1], val, True, INK)):
            p = cell.paragraphs[0]; set_par(p, rtl, after=0, line=1.15)
            if n is not None: add_runs(p, n, rtl, 9, b, colr)
        shade(row[0], 'F3F6FB')
    for k in node.children:
        if isinstance(k, Tag) and 'note' in ' '.join(k.get('class') or []): para(doc, k, rtl, size=8.5, color=GREY)
    sp = doc.add_paragraph(); set_par(sp, rtl, after=2)

AR = re.compile('[\u0600-\u06FF]')
def grid(doc, L, rtl):
    """Text blocks drawn as cards in the PDF (KPI tiles, feature cards, about rows) as a native Word table."""
    k = max(1, L['k'])
    t = doc.add_table(rows=0, cols=k); table_base(t, rtl)
    for r in L['rows']:
        row = t.add_row(); row._tr.get_or_add_trPr().append(el('w:cantSplit')); cells = row.cells
        if len(r) < k:
            # a short row (caption, last odd card): spread its cells evenly
            span = k // len(r); targets = []
            for i in range(len(r)):
                a = i * span; b = k - 1 if i == len(r) - 1 else a + span - 1
                targets.append(cells[a].merge(cells[b]) if b > a else cells[a])
        else: targets = cells
        for cell, c in zip(targets, r):
            first = True
            for ln in c['lines']:
                p = cell.paragraphs[0] if first else cell.add_paragraph(); first = False
                set_par(p, rtl, 'center' if ln.get('al') == 'center' else None, after=1, line=1.15)
                sz = max(7, min(22, round(ln['s'] * 0.75 * 2) / 2))
                col = RGBColor.from_string(ln['c']) if ln.get('c') else INK
                txt = ln['t']
                if rtl and not AR.search(txt): run(p, '\u200e' + txt + '\u200e', False, sz, ln['w'] >= 600, col)
                else: run(p, txt, rtl, sz, ln['w'] >= 600, col)
            if c.get('bg') and c['bg'] not in ('FFFFFF',): shade(cell, c['bg'])
    sp = doc.add_paragraph(); set_par(sp, rtl, after=2)

def toc(doc, rtl, entries):
    # TOC field whose cached result already lists the headings with page numbers (filled in after a layout pass),
    # so the contents page reads like the PDF before anyone presses F9; Word can still refresh it.
    tabpos = int(176 / 25.4 * 1440)
    def tabs(q):
        tb = el('w:tabs'); tb.append(el('w:tab', **{'w:val': 'right', 'w:leader': 'dot', 'w:pos': tabpos})); ppr(q).append(tb)
    p = doc.add_paragraph(); set_par(p, rtl, after=3); tabs(p)
    r = p.add_run()
    r._r.append(el('w:fldChar', **{'w:fldCharType': 'begin'}))
    it = el('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = ' TOC \\o "1-2" \\h \\z \\u '; r._r.append(it)
    r._r.append(el('w:fldChar', **{'w:fldCharType': 'separate'}))
    for i, (lvl, text) in enumerate(entries):
        q = p if i == 0 else doc.add_paragraph()
        if i: set_par(q, rtl, after=3, ind_start=0 if lvl == 1 else 360); tabs(q)
        run(q, text, rtl, 10 if lvl == 1 else 9.5, bold=(lvl == 1), color=NAVY if lvl == 1 else INK)
        run(q, '\t', rtl, 10 if lvl == 1 else 9.5, color=GREY)
        run(q, '\u27e6PG%d\u27e7' % i, False, 10 if lvl == 1 else 9.5, bold=(lvl == 1), color=NAVY if lvl == 1 else INK)
    q = doc.paragraphs[-1]; r2 = q.add_run(); r2._r.append(el('w:fldChar', **{'w:fldCharType': 'end'}))

def lo_pdf(docx_path):
    import subprocess, tempfile
    d = tempfile.mkdtemp(prefix='lo3_')
    subprocess.run(['soffice', '-env:UserInstallation=file://' + d + '/u', '--headless', '--convert-to', 'pdf', '--outdir', d, docx_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    out = os.path.join(d, os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
    return out if os.path.exists(out) else None

def fill_toc_pages(docx_path, levels, toc_idx):
    """levels: outline levels of every Heading paragraph in document order; toc_idx: positions that are TOC entries."""
    import pymupdf
    pdf = lo_pdf(docx_path); pages = {}
    if pdf:
        out = [e for e in pymupdf.open(pdf).get_toc(simple=True)]
        if len(out) == len(levels):
            k = 0
            for pos, (lvl, title, pg) in enumerate(out):
                if pos in toc_idx: pages[toc_idx[pos]] = pg
    tmp = docx_path + '.t'
    with zipfile.ZipFile(docx_path) as zi, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            b = zi.read(it.filename)
            if it.filename == 'word/document.xml':
                s = b.decode('utf-8')
                s = re.sub('\u27e6PG(\\d+)\u27e7', lambda m: str(pages.get(int(m.group(1)), '')), s)
                b = s.encode('utf-8')
            zo.writestr(it, b)
    shutil.move(tmp, docx_path)
    return len(pages), pdf

def slim(path, q=86):
    from PIL import Image
    if os.path.getsize(path) < 300000 and path.endswith('.jpg'): return path
    im = Image.open(path).convert('RGB'); j = os.path.splitext(path)[0] + '.j.jpg'; im.save(j, quality=q, optimize=True); return j

def image(doc, path, rtl, width_mm=176, max_h_mm=226):
    from PIL import Image
    path = slim(path)
    w, h = Image.open(path).size
    wmm = min(width_mm, w / 2 / 96 * 25.4)          # shots are 2x: natural CSS size
    if wmm * h / w > max_h_mm: wmm = max_h_mm * w / h
    p = doc.add_paragraph(); set_par(p, rtl, 'center', after=4, line=1.0)
    p.add_run().add_picture(path, width=Mm(wmm))

ANCHOR = ('<wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
          'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
          'distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" behindDoc="1" locked="1" layoutInCell="1" allowOverlap="1">'
          '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>'
          '<wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>'
          '<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
          '<wp:docPr id="{id}" name="Page {id}"/><wp:cNvGraphicFramePr/>'
          '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
          '<pic:nvPicPr><pic:cNvPr id="{id}" name="page{id}.jpg"/><pic:cNvPicPr/></pic:nvPicPr>'
          '<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
          '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
          '</pic:pic></a:graphicData></a:graphic></wp:anchor>')
_pid = [9000]

def full_page(doc, path, rtl, first=False, alt=''):
    """A zero-margin section whose only content is a page-size picture behind the text layer."""
    if first: sec = doc.sections[0]
    else: sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.page_width = Mm(210); sec.page_height = Mm(297)
    for m in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'): setattr(sec, m, Mm(0))
    sec.header_distance = Mm(0); sec.footer_distance = Mm(0)
    sec.different_first_page_header_footer = False
    blank_hf(sec)
    p = doc.add_paragraph(); set_par(p, rtl, after=0, line=1.0)
    rid, _ = p.part.get_or_add_image(slim(path, 88))
    _pid[0] += 1
    xml = ANCHOR.format(cx=int(Mm(210)), cy=int(Mm(297)), id=_pid[0], rid=rid)
    r = p.add_run(); d = OxmlElement('w:drawing'); d.append(parse_xml(xml)); r._r.append(d)
    if alt:
        dp = d.find('.//' + qn('wp:docPr')); dp.set('descr', alt)
    return sec

BLEED = ('<wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
          'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
          'distT="0" distB="{gap}" distL="0" distR="0" simplePos="0" relativeHeight="2" behindDoc="0" locked="1" layoutInCell="1" allowOverlap="0">'
          '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>'
          '<wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>'
          '<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapTopAndBottom/>'
          '<wp:docPr id="{id}" name="Banner {id}"/><wp:cNvGraphicFramePr/>'
          '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
          '<pic:nvPicPr><pic:cNvPr id="{id}" name="banner{id}.jpg"/><pic:cNvPicPr/></pic:nvPicPr>'
          '<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
          '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
          '</pic:pic></a:graphicData></a:graphic></wp:anchor>')

def bleed_ok(soup, x):
    e = soup.find(attrs={'data-wx': x})
    return e is not None and 'band' in (e.get('class') or [])

def bleed_top(doc, path, rtl):
    """Opening banner of a statement/notice: edge to edge at the top of page 1, text flows below it."""
    from PIL import Image
    path = slim(path, 88); w, h = Image.open(path).size
    sec = doc.sections[-1]; sec.different_first_page_header_footer = True
    fh = sec.first_page_header; fh.is_linked_to_previous = False
    for q in fh.paragraphs: q.text = ''
    ff = sec.first_page_footer; ff.is_linked_to_previous = False
    src = sec.footer.paragraphs[0]._p; dst = ff.paragraphs[0]._p
    import copy; dst.getparent().replace(dst, copy.deepcopy(src))
    cx = int(Mm(210)); cy = int(cx * h / w)
    p = doc.add_paragraph(); set_par(p, rtl, after=0, line=1.0)
    rid, _ = p.part.get_or_add_image(path); _pid[0] += 1
    xml = BLEED.format(cx=cx, cy=cy, id=_pid[0], rid=rid, gap=int(Mm(6)))
    r = p.add_run(); d = OxmlElement('w:drawing'); d.append(parse_xml(xml)); r._r.append(d)

def _is_break_par(e):
    if e.tag != qn('w:p'): return False
    rs = e.findall(qn('w:r'))
    if not rs or e.find('.//' + qn('w:t')) is not None or e.find('.//' + qn('w:drawing')) is not None: return False
    brs = e.findall('.//' + qn('w:br'))
    return bool(brs) and all(b.get(qn('w:type')) == 'page' for b in brs) and e.find('.//' + qn('w:sectPr')) is None

def tidy_breaks(doc):
    """No blank pages: a forced break becomes 'page break before' on the next paragraph (never lands as an
    empty line at the top of a page); repeated breaks collapse to one; the bookkeeping paragraphs of full-page
    sections are made 1pt high so they never spill onto an extra page."""
    body = doc.element.body
    kids = list(body); pending = False
    for k, e in enumerate(kids):
        if _is_break_par(e):
            body.remove(e); pending = True; continue
        if not pending: continue
        pending = False
        prev = e.getprevious()
        opens_page = prev is not None and prev.find('.//' + qn('w:sectPr')) is not None
        if opens_page or e.find('.//' + qn('w:sectPr')) is not None: continue  # a section break already starts a page
        if e.tag == qn('w:p'):
            pr = e.find(qn('w:pPr'))
            if pr is None: pr = el('w:pPr'); e.insert(0, pr)
            if pr.find(qn('w:pageBreakBefore')) is None: pr.insert(0, el('w:pageBreakBefore'))
        else:  # a table: keep one explicit break in front of it
            bp = el('w:p'); r = el('w:r'); r.append(el('w:br', **{'w:type': 'page'})); bp.append(r); e.addprevious(bp)
    # tiny bookkeeping paragraphs on full-page sections (anchor holder and section-end paragraph)
    for e in body.iter(qn('w:p')):
        has_anchor = e.find('.//' + qn('wp:anchor')) is not None and e.find('.//' + qn('w:t')) is None
        is_sect_end = e.find('.//' + qn('w:sectPr')) is not None and e.find('.//' + qn('w:t')) is None and e.find('.//' + qn('w:drawing')) is None
        if not (has_anchor or is_sect_end): continue
        pr = e.find(qn('w:pPr'))
        if pr is None: pr = el('w:pPr'); e.insert(0, pr)
        for old in pr.findall(qn('w:spacing')): pr.remove(old)
        pr.append(el('w:spacing', **{'w:before': 0, 'w:after': 0, 'w:line': 20, 'w:lineRule': 'exact'}))
        rp = pr.find(qn('w:rPr'))
        if rp is None: rp = el('w:rPr'); pr.append(rp)
        rp.append(el('w:sz', **{'w:val': 2})); rp.append(el('w:szCs', **{'w:val': 2}))
        for r in e.findall(qn('w:r')):
            rr = r.find(qn('w:rPr'))
            if rr is None: rr = el('w:rPr'); r.insert(0, rr)
            rr.append(el('w:sz', **{'w:val': 2}))

def blank_hf(sec):
    for hf in (sec.header, sec.footer):
        hf.is_linked_to_previous = False
        for p in hf.paragraphs: p.text = ''

def body_section(doc, rtl, header_text, accent_hex, sec=None):
    if sec is None: sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.page_width = Mm(210); sec.page_height = Mm(297)
    sec.left_margin = sec.right_margin = Mm(17); sec.top_margin = Mm(22); sec.bottom_margin = Mm(20)
    sec.header_distance = Mm(10); sec.footer_distance = Mm(9)
    h = sec.header; h.is_linked_to_previous = False
    hp = h.paragraphs[0]; hp.text = ''; set_par(hp, rtl, after=0, line=1.0)
    run(hp, header_text, rtl, 7.5, color=GREY)
    pb = ppr(hp); bdr = el('w:pBdr'); bdr.append(el('w:bottom', **{'w:val': 'single', 'w:sz': 4, 'w:space': 4, 'w:color': 'DCE3EE'})); pb.append(bdr)
    f = sec.footer; f.is_linked_to_previous = False
    fp = f.paragraphs[0]; fp.text = ''; set_par(fp, rtl, after=0, line=1.0)
    run(fp, ('الخبير المالية · alkhabeer.com' if rtl else 'Alkhabeer Capital · alkhabeer.com') + '      ', rtl, 7.5, color=GREY)
    r = fp.add_run(); rPr = r._r.get_or_add_rPr(); fonts(rPr); r.font.size = Pt(7.5); r.font.color.rgb = GREY
    r._r.append(el('w:fldChar', **{'w:fldCharType': 'begin'}))
    it = el('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = ' PAGE '; r._r.append(it)
    r._r.append(el('w:fldChar', **{'w:fldCharType': 'separate'})); t = el('w:t'); t.text = '1'; r._r.append(t)
    r._r.append(el('w:fldChar', **{'w:fldCharType': 'end'}))
    return sec

def styles(doc, rtl, accent):
    st = doc.styles
    for name in ('Normal', 'Heading 1', 'Heading 2', 'Heading 3', 'Title', 'List Paragraph'):
        try: s = st[name]
        except KeyError: continue
        rPr = s.element.get_or_add_rPr(); fonts(rPr)
        if rtl:
            rPr.append(el('w:rtl'))
            pPr = s.element.get_or_add_pPr(); pPr.append(el('w:bidi', **{'w:val': '1'}))
    st['Normal'].font.size = Pt(10)
    for hn, sz, col in (('Heading 1', 18, NAVY), ('Heading 2', 13, NAVY), ('Heading 3', 11, NAVY)):
        hs = st[hn]; hs.font.size = Pt(sz); hs.font.color.rgb = col; hs.font.bold = True
        hs.paragraph_format.space_before = Pt(10 if hn != 'Heading 1' else 0); hs.paragraph_format.space_after = Pt(5)
        hs.paragraph_format.keep_with_next = True
    # document default (docDefaults) complex-script font and direction
    dd = doc.styles.element.find(qn('w:docDefaults'))
    if dd is not None:
        rpd = dd.find(qn('w:rPrDefault')); r = rpd.find(qn('w:rPr')) if rpd is not None else None
        if r is not None: fonts(r)

THEME_FONT = re.compile(r'(<a:(?:latin|cs|ea) typeface=")[^"]*(")')

DOCPR = [0]
def patch_package(path, rtl):
    DOCPR[0] = 0
    """Theme fonts -> Arial; Arabic proofing language; ask Word to refresh the TOC page numbers on open."""
    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            b = zi.read(it.filename)
            if it.filename.startswith('word/theme/'):
                s = b.decode('utf-8')
                s = re.sub(r'(<a:majorFont>.*?</a:majorFont>)', lambda m: THEME_FONT.sub(r'\1' + FONT + r'\2', m.group(1)), s, flags=re.S)
                s = re.sub(r'(<a:minorFont>.*?</a:minorFont>)', lambda m: THEME_FONT.sub(r'\1' + FONT + r'\2', m.group(1)), s, flags=re.S)
                s = re.sub(r'(<a:font script="[^"]*" typeface=")[^"]*(")', r'\1' + FONT + r'\2', s)
                b = s.encode('utf-8')
            elif it.filename == 'word/settings.xml':
                s = b.decode('utf-8')
                if rtl and 'w:themeFontLang' in s:
                    s = re.sub(r'<w:themeFontLang [^>]*/>', '<w:themeFontLang w:val="en-US" w:bidi="ar-SA"/>', s)
                b = s.encode('utf-8')
            elif it.filename == 'word/styles.xml':
                s = b.decode('utf-8')
                s = re.sub(r'w:(ascii|hAnsi|cs|eastAsia)="(?:Courier|Courier New|Calibri|Cambria|Times New Roman)"', r'w:\1="Arial"', s)
                if rtl: s = s.replace('<w:lang w:val="en-US" w:eastAsia="en-US" w:bidi="ar-SA"/>', '<w:lang w:val="ar-SA" w:eastAsia="en-US" w:bidi="ar-SA"/>')
                b = s.encode('utf-8')
            if it.filename == 'word/stylesWithEffects.xml':
                s = b.decode('utf-8')
                s = re.sub(r'w:(ascii|hAnsi|cs|eastAsia)="[^"]*"', r'w:\1="Arial"', s)
                s = re.sub(r'w:(asciiTheme|hAnsiTheme|cstheme|eastAsiaTheme)="[^"]*"', '', s)
                b = s.encode('utf-8')
            elif it.filename == 'word/fontTable.xml':
                s = b.decode('utf-8')
                s = re.sub(r'<w:font w:name="(?!Arial")[^"]*">.*?</w:font>', '', s, flags=re.S)
                b = s.encode('utf-8')
            elif it.filename == 'word/numbering.xml':
                s = b.decode('utf-8')
                s = re.sub(r'w:(ascii|hAnsi|cs|eastAsia)="[^"]*"', r'w:\1="Arial"', s)
                s = re.sub(r'w:lvlText w:val="[\uf000-\uf0ff]"', 'w:lvlText w:val="\u2022"', s)
                b = s.encode('utf-8')
            if it.filename.startswith('word/') and it.filename.endswith('.xml') and re.match(r'word/(document|header\d*|footer\d*)\.xml$', it.filename):
                s = b.decode('utf-8')
                def nid(m):
                    DOCPR[0] += 1; return m.group(1) + str(DOCPR[0]) + '"'
                s = re.sub(r'(<wp:docPr id=")\d+"', nid, s)
                b = s.encode('utf-8')
            if it.filename.startswith('word/') and it.filename.endswith('.xml') and ('document' in it.filename or 'header' in it.filename or 'footer' in it.filename or 'styles' in it.filename):
                b = ooxml_order.fix_bytes(b)
            if it.filename == 'word/settings.xml':
                b = re.sub(rb'<w:zoom(?![^>]*w:percent)', b'<w:zoom w:percent="100"', b)
            zo.writestr(it, b)
    shutil.move(tmp, path)

# ---------- screenshots ----------
ANALYZE = r'''(ids)=>{
 const vis=e=>{const c=getComputedStyle(e);return c.display!=='none'&&c.visibility!=='hidden'&&!['STYLE','SCRIPT','TEMPLATE'].includes(e.tagName)};
 const isSvg=e=>e.tagName.toLowerCase()==='svg';
 const kidsOf=e=>[...e.children].filter(k=>vis(k)&&!isSvg(k)&&k.innerText.trim());
 const inl=e=>['inline','inline-block','contents'].includes(getComputedStyle(e).display)||e.tagName==='BR';
 const hasBlock=e=>!!e.querySelector('div,p,li,h1,h2,h3,h4,h5,ul,ol');
 const hex=c=>{const m=c.match(/rgba?\(([^)]+)\)/);if(!m)return null;const v=m[1].split(',').map(x=>parseFloat(x));if(v.length>3&&v[3]<0.2)return null;return v.slice(0,3).map(x=>Math.round(x).toString(16).padStart(2,'0')).join('').toUpperCase()};
 const lines=cell=>{const out=[];
  const take=(el,wmin)=>{const t=el.innerText.replace(/\s+/g,' ').trim();if(!t)return;const cs=getComputedStyle(el);let w=Math.max(+cs.fontWeight,wmin||0);
   el.querySelectorAll('b,strong').forEach(b=>{if(b.innerText.trim()===t)w=Math.max(w,700)});
   let s=parseFloat(cs.fontSize),best=0;[el,...el.querySelectorAll('*')].forEach(x=>{let own='';x.childNodes.forEach(n=>{if(n.nodeType===3)own+=n.textContent});own=own.trim();if(own.length>best){best=own.length;s=parseFloat(getComputedStyle(x).fontSize)}});
   out.push({t,w,s,c:hex(cs.color),al:cs.textAlign})};
  const walk=n=>{const kids=kidsOf(n);
   if(!kids.length||kids.every(inl)){take(n);return}
   for(const ch of n.childNodes){if(ch.nodeType===3&&ch.textContent.trim()){take(n);return}}
   const cs=getComputedStyle(n);
   if(cs.display.includes('flex')&&!cs.flexDirection.startsWith('column')&&kids.every(k=>!hasBlock(k))){
     let w=0;kids.forEach(k=>w=Math.max(w,+getComputedStyle(k).fontWeight));take(n,w);return}
   for(const k of kids){if(inl(k)&&!hasBlock(k))take(k);else walk(k)}};
  walk(cell);return out};
 const horiz=e=>{const k=kidsOf(e);if(k.length<2)return false;const t=k.map(x=>Math.round(x.getBoundingClientRect().top/6));return new Set(t).size<t.length};
 const R={};
 for(const id of ids){const e=document.querySelector('[data-wx="'+id+'"]');R[id]=null;if(!e)continue;
  if(e.matches('.chart,.band,.gal,.gal3,.hero,.pov,.partners,.orig')||e.querySelector('.chart,img,canvas,video,iframe,picture'))continue;
  let big=false;e.querySelectorAll('svg').forEach(v=>{const r=v.getBoundingClientRect();if(r.width>70||r.height>70)big=true});if(big)continue;
  let bgimg=false;e.querySelectorAll('*').forEach(x=>{if(getComputedStyle(x).backgroundImage.includes('url('))bgimg=true});if(bgimg)continue;
  if(!e.innerText.trim())continue;
  // flatten wrappers into rows of cells: a container whose children sit side by side is a grid
  const rows=[];
  const add=(cells)=>{let top=null;for(const k of cells){const t=Math.round(k.getBoundingClientRect().top/6);if(top===null||t!==top){rows.push([]);top=t}rows[rows.length-1].push(k)}};
  const visit=(c,depth)=>{const k=kidsOf(c);
   if(!k.length){add([c]);return}
   if(horiz(c)){add(k);return}
   if(depth<4&&k.some(x=>horiz(x)||kidsOf(x).length===1)){for(const x of k){if(horiz(x))add(kidsOf(x));else if(kidsOf(x).length===1&&depth<3)visit(x,depth+1);else add([x])}return}
   add(k)};
  visit(e,0);
  const kmax=Math.max(...rows.map(r=>r.length));
  if(kmax>6)continue;
  R[id]={k:kmax,rows:rows.map(r=>r.map(x=>({bg:hex(getComputedStyle(x).backgroundColor),lines:lines(x)})))};
 }
 return R}'''

async def shots(html_path, ids, outdir, page_ids):
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={'width': 794, 'height': 1123}, device_scale_factor=2)
        await pg.goto('file://' + html_path, wait_until='networkidle', timeout=240000)
        await pg.evaluate('document.fonts.ready')
        await pg.add_style_tag(content='@page{size:auto} section.cover,section.back{width:210mm!important;height:297mm!important;'
                                       'overflow:hidden;box-shadow:none!important;break-before:auto!important}'
                                       '[data-wx]{break-inside:auto}')
        await pg.wait_for_timeout(600)
        # page breaks the PDF takes (print CSS), so the Word file breaks pages at the same places
        await pg.emulate_media(media='print')
        breaks = await pg.evaluate('''()=>[...document.querySelectorAll('[data-pb]')].filter(e=>{const c=getComputedStyle(e);
            return c.breakBefore==='page'||c.pageBreakBefore==='always'||c.breakBefore==='left'||c.breakBefore==='right'}).map(e=>+e.dataset.pb)''')
        await pg.emulate_media(media='screen')
        await pg.wait_for_timeout(200)
        miss = []
        for i in ids:
            loc = pg.locator('[data-wx="%s"]' % i)
            ok = False
            for attempt in range(3):
                try:
                    await loc.screenshot(path='%s/%s.png' % (outdir, i), timeout=60000, animations='disabled'); ok = True; break
                except Exception as e:
                    await pg.evaluate('(s)=>{const e=document.querySelector(s); if(e){e.style.display="block";e.style.visibility="visible";}}', '[data-wx="%s"]' % i)
                    await pg.wait_for_timeout(300)
            if not ok: miss.append(i)
        layouts = await pg.evaluate(ANALYZE, ids)
        # cover/back at 3x for crisp print
        await b.close()
        if page_ids:
            b = await pw.chromium.launch()
            pg = await b.new_page(viewport={'width': 794, 'height': 1123}, device_scale_factor=3)
            await pg.goto('file://' + html_path, wait_until='networkidle', timeout=240000)
            await pg.evaluate('document.fonts.ready')
            await pg.add_style_tag(content='section.cover,section.back{width:210mm!important;height:297mm!important;overflow:hidden;box-shadow:none!important}')
            await pg.wait_for_timeout(600)
            for i in page_ids:
                try: await pg.locator('[data-wx="%s"]' % i).screenshot(path='%s/%s.png' % (outdir, i), timeout=60000)
                except Exception: miss.append(i)
            await b.close()
        return miss, set(breaks), layouts

# ---------- build ----------
def build(html_path, out_docx, lang, extra=None, fund_label='', doc_label='', accent='3B7DD8'):
    rtl = lang == 'ar'
    ACCENT[0] = RGBColor.from_string(accent.upper())
    src = open(html_path, encoding='utf-8').read()
    s = BeautifulSoup(src, 'html.parser')
    body = s.body; main = body.find('main')
    pics = []; pages = []; n = [0]
    def mark(e, page=False):
        n[0] += 1; e['data-wx'] = 'x%d' % n[0]; (pages if page else pics).append(e['data-wx']); return e['data-wx']
    cover = body.find('section', class_='cover'); back = body.find('section', class_='back')
    if cover: mark(cover, True)
    if back: mark(back, True)
    plan = []
    heads = []
    def walk(container):
        for c in container.children:
            if not isinstance(c, Tag): continue
            cls = ' '.join(c.get('class') or [])
            if c.name in ('style', 'script', 'template'): continue
            if c.name == 'span' and not c.get_text(strip=True) and not c.find('img'): continue
            if c.name in TEXT_BLOCKS:
                if c.find(['img', 'svg']) and c.name in ('p', 'ul', 'ol'): plan.append(('pic', mark(c)))
                else:
                    plan.append(('text', c))
                    if c.name in ('h1', 'h2') and 'tochd' not in cls:
                        heads.append((1 if c.name == 'h1' else 2, re.sub(r'\s+', ' ', c.get_text(' ', strip=True))))
                continue
            first = (cls.split() or [''])[0]
            if c.name == 'div' and first in ('tw', 'facts', 'note'): plan.append(('text', c)); continue
            if c.name == 'div' and first == 'band':
                plan.append(('pic', mark(c))); continue
            if c.name == 'div' and 'orig' in cls:
                img = c.find('img'); plan.append(('orig', img['src'].replace('file://', '') if img else None)); continue
            if c.name == 'figure' and c.find('div', class_='facts', recursive=False):
                for k in c.children:
                    if not isinstance(k, Tag): continue
                    kc = ' '.join(k.get('class') or [])
                    if kc == 'ct': plan.append(('cap', k))
                    elif kc.startswith('facts'): plan.append(('text', k))
                    else: plan.append(('pic', mark(k)))
                continue
            if c.name in ('section', 'article') or (c.name == 'div' and not cls and c.find(list(TEXT_BLOCKS), recursive=False)):
                walk(c); continue  # plain wrapper: keep its content as text
            if not c.get_text(strip=True) and not c.find(['img', 'svg', 'canvas']): continue
            plan.append(('pic', mark(c)))
    walk(main)
    for i, (kind, x) in enumerate(plan):
        e = s.find(attrs={'data-wx': x}) if kind == 'pic' else (x if isinstance(x, Tag) else None)
        if e is not None and not e.has_attr('data-pb'): e['data-pb'] = str(i)
    tmp = html_path[:-5] + '.wx3.html'; open(tmp, 'w', encoding='utf-8').write(str(s))
    outdir = os.path.splitext(out_docx)[0] + '_img'; os.makedirs(outdir, exist_ok=True)
    miss, breaks, layouts = asyncio.run(shots(os.path.abspath(tmp), pics, outdir, pages))
    os.remove(tmp)
    if miss: raise MissingPicture('%s: %d element(s) not captured: %s' % (os.path.basename(out_docx), len(miss), miss[:5]))

    doc = Document()
    styles(doc, rtl, accent)
    header_text = ' · '.join(x for x in (fund_label, doc_label) if x)
    started = False
    if cover:
        full_page(doc, '%s/%s.png' % (outdir, cover['data-wx']), rtl, first=True, alt='Cover')
        started = True
    if started: body_section(doc, rtl, header_text, accent)
    else: body_section(doc, rtl, header_text, accent, sec=doc.sections[0])
    first_body = True
    levels = []; toc_idx = {}; has_toc = False; native = []; npics = 0; ngrid = 0
    need_body = [False]
    for idx, (kind, x) in enumerate(plan):
        if need_body[0] and kind != 'orig':
            body_section(doc, rtl, header_text, accent); need_body[0] = False
        if idx in breaks and not first_body: doc.add_page_break()
        if kind == 'pic':
            L = layouts.get(x)
            if L and any(c['lines'] for r in L['rows'] for c in r):
                grid(doc, L, rtl); ngrid += 1
                native.append(' '.join(ln['t'] for r in L['rows'] for c in r for ln in c['lines']))
            elif idx == 0 and not cover and bleed_ok(s, x):
                bleed_top(doc, '%s/%s.png' % (outdir, x), rtl); npics += 1
            else:
                image(doc, '%s/%s.png' % (outdir, x), rtl); npics += 1
            first_body = False; continue
        if kind == 'orig':
            if x and os.path.exists(x):
                full_page(doc, x, rtl, alt='Original signed page'); need_body[0] = True
            continue
        if kind == 'cap':
            para(doc, x, rtl, size=11, bold=True, color=NAVY, after=3, keep_next=True); continue
        e = x; cls = ' '.join(e.get('class') or [])
        if e.name in ('h1', 'h2', 'h3', 'h4'):
            lvl = {'h1': 1, 'h2': 2, 'h3': 3, 'h4': 3}[e.name]
            if 'brk' in cls and not first_body and idx not in breaks: doc.add_page_break()
            p = doc.add_paragraph(style='Heading %d' % lvl); set_par(p, rtl, after=5, before=0 if lvl == 1 else 8, keep_next=True)
            npics += heading_icon(p, e)
            add_runs(p, e, rtl, {1: 18, 2: 13, 3: 11}[lvl], True, NAVY)
            if lvl in (1, 2) and 'tochd' not in cls: toc_idx[len(levels)] = sum(1 for v in toc_idx.values()) 
            levels.append(lvl)
            if lvl == 1:
                pb = ppr(p); bdr = el('w:pBdr'); bdr.append(el('w:bottom', **{'w:val': 'single', 'w:sz': 12, 'w:space': 4, 'w:color': accent})); pb.append(bdr)
        elif e.name == 'p':
            para(doc, e, rtl)
        elif e.name in ('ul', 'ol'):
            for k, li in enumerate(e.find_all('li', recursive=False), 1):
                p = doc.add_paragraph(); set_par(p, rtl, after=2, ind_start=420, hanging=280)
                run(p, ('%d.' % k if e.name == 'ol' else '•') + '\t', rtl, 10, False, ACCENT[0])
                add_runs(p, li, rtl, 10, False, INK)
        elif e.name == 'nav':
            toc(doc, rtl, heads); doc.add_page_break(); has_toc = True
        elif cls.startswith('tw'):
            ct = e.find(class_='ct')
            if ct: para(doc, ct, rtl, size=10, bold=True, color=NAVY, after=2, keep_next=True)
            for tb in e.find_all('table'): html_table(doc, tb, rtl)
            for nt in e.find_all(class_='note'): para(doc, nt, rtl, size=8.5, color=GREY)
        elif cls.startswith('facts'):
            facts(doc, e, rtl)
        elif cls.startswith('note'):
            para(doc, e, rtl, size=8.5, color=GREY)
        first_body = False
    for xp in (extra or []):
        full_page(doc, xp, rtl, alt='Original signed page')
    if back:
        full_page(doc, '%s/%s.png' % (outdir, back['data-wx']), rtl, alt='Back cover')
    tidy_breaks(doc)
    if rtl:
        for sec in doc.sections: sec._sectPr.append(el('w:bidi'))
    doc.core_properties.author = 'Alkhabeer Capital'; doc.core_properties.title = (s.title.string if s.title else '')
    doc.core_properties.language = 'ar-SA' if rtl else 'en-US'
    doc.save(out_docx)
    patch_package(out_docx, rtl)
    filled = None
    if has_toc: filled = fill_toc_pages(out_docx, levels, toc_idx)[0]
    for kind, x in plan:
        if kind in ('text', 'cap'): native.append(re.sub(r'\s+', ' ', x.get_text(' ', strip=True)))
    return dict(docx=out_docx, grids=ngrid, pics=npics, pages=len(pages) + len(extra or []), native=native, toc=(len(heads), filled))

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3])
