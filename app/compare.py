"""Review pack for a generated statement, built right after the drafts (or the final version) are produced.

- Page by page, the new PDF against the previous quarter's statement (its final version here, else the published one):
  both pages as images and the new page with the changed areas outlined, so a reviewer sees at a glance that only the
  figures moved and the layout held.
- Layout checks on the new PDF: page count against last quarter, text running past the bottom margin, near-empty pages.
- Figures that differ between the Arabic and English drafts (the same check used on published statements).
- Field-level changes against the previous quarter.
The pack is written to <output dir>/cmp/ and read by the comparison page.
"""
import os, json, glob, difflib, unicodedata
import pymupdf
from PIL import Image, ImageDraw
import store, records as R, pipeline as P, model as M

ZOOM = 1.4          # 72 dpi × 1.4 ≈ 100 dpi: sharp enough to read figures, light enough to load a dozen pages
MARGIN_PT = 18      # text closer than this to the bottom edge of a page is reported as running off the page


def previous_pdf(fund, q, lang):
    """The previous quarter's statement as a PDF: its final version in this system, else the published file."""
    pq = M.prev_q(q); s = store.get(fund, pq) or {}
    f = ((s.get('files') or {}).get('final') or {}).get(lang) or {}
    if f.get('pdf'):
        p = os.path.join(store.out_dir(fund, pq), 'final', f['pdf'])
        if os.path.isfile(p): return pq, p
    d = os.path.join(R.PUB, fund, pq)
    p = os.path.join(d, P.fname(fund, pq, lang) + '.pdf')
    if os.path.isfile(p): return pq, p
    c = sorted(glob.glob(os.path.join(d, f'*-{lang.upper()}.pdf')))
    return pq, (c[0] if c else None)


def _img(page, path):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), alpha=False)
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    img.save(path, 'WEBP', quality=82, method=4)
    return img


def _words(doc):
    """Every word of a PDF in reading order, with its page and box (points)."""
    out = []
    for i, pg in enumerate(doc):
        for w in pg.get_text('words'):
            t = unicodedata.normalize('NFKC', w[4]).strip()
            if t: out.append((i, w[0], w[1], w[2], w[3], t))
    return out


def _merge(rects):
    """Join boxes of neighbouring words on the same line into one box per changed phrase."""
    rects = sorted(rects, key=lambda r: (round(r[1] / 4), r[0])); out = []
    for r in rects:
        if out:
            o = out[-1]
            if abs(o[1] - r[1]) < 4 and abs(o[3] - r[3]) < 4 and (r[0] - o[2] < 14 and o[0] - r[2] < 14):
                out[-1] = (min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3])); continue
        out.append(r)
    return out


def text_changes(old, new):
    """What changed in the new PDF against the old one, matched by content rather than position, so text that only
    moved (because a paragraph grew or shrank) is not reported. Returns per new page: boxes of changed words and the
    before → after phrases."""
    wo, wn = _words(old), _words(new)
    sm = difflib.SequenceMatcher(None, [w[5] for w in wo], [w[5] for w in wn], autojunk=False)
    pages = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal': continue
        before = ' '.join(w[5] for w in wo[i1:i2]); after = ' '.join(w[5] for w in wn[j1:j2])
        if j1 < j2:
            pg = wn[j1][0]
            P_ = pages.setdefault(pg, {'rects': [], 'items': []})
            P_['rects'] += [w[1:5] for w in wn[j1:j2]]
        else:   # removed text: shown on the page where the following text now sits
            pg = wn[min(j1, len(wn) - 1)][0] if wn else 0
            P_ = pages.setdefault(pg, {'rects': [], 'items': []})
        P_['items'].append({'op': op, 'before': before[:400], 'after': after[:400]})
    for P_ in pages.values(): P_['rects'] = _merge(P_['rects'])
    return pages


def _overlay(img, boxes, path):
    base = Image.blend(img, Image.new('RGB', img.size, (255, 255, 255)), 0.35)
    dr = ImageDraw.Draw(base, 'RGBA')
    for r in boxes:
        x0, y0, x1, y1 = (v * ZOOM for v in r)
        dr.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill=(59, 125, 216, 40), outline=(46, 109, 176, 255), width=2)
    base.save(path, 'WEBP', quality=82, method=4)


def _layout(doc):
    """Pages whose text runs into the bottom margin, and pages with almost no text (a sign that content spilled over)."""
    over, empty = [], []
    for i, pg in enumerate(doc):
        h = pg.rect.height; words = pg.get_text('words')
        if any(w[3] > h - MARGIN_PT and w[4].strip() for w in words): over.append(i + 1)
        if len(words) < 8 and i not in (0, len(doc) - 1): empty.append(i + 1)
    return over, empty


def build(fund, q, kind, od, files, structs, prev_structs):
    """Write the review pack for one generated version and return its summary."""
    cd = os.path.join(od, 'cmp'); os.makedirs(cd, exist_ok=True)
    for x in glob.glob(os.path.join(cd, '*')): os.remove(x)   # nothing stale from an earlier run
    rep = {'fund': fund, 'q': q, 'kind': kind, 'built': store.now(), 'langs': {}, 'pairs': [], 'changes': []}
    for lang in ('ar', 'en'):
        f = (files.get(lang) or {}).get('pdf')
        if not f: continue
        new = pymupdf.open(os.path.join(od, f))
        pq, prev = previous_pdf(fund, q, lang)
        old = pymupdf.open(prev) if prev else None
        over, empty = _layout(new)
        L = {'pages': len(new), 'prev_pages': len(old) if old else None, 'prev_q': pq, 'prev_found': bool(old),
             'overflow': over, 'empty': empty, 'page': []}
        tc = text_changes(old, new) if old else {}
        for i in range(len(new)):
            a = _img(new[i], os.path.join(cd, f'{lang}-n{i + 1}.webp'))
            row = {'n': i + 1, 'new': f'cmp/{lang}-n{i + 1}.webp', 'w': a.width, 'h': a.height}
            if old and i < len(old):
                _img(old[i], os.path.join(cd, f'{lang}-o{i + 1}.webp')); row['old'] = f'cmp/{lang}-o{i + 1}.webp'
            if old:
                ch = tc.get(i, {'rects': [], 'items': []})
                _overlay(a, ch['rects'], os.path.join(cd, f'{lang}-d{i + 1}.webp'))
                row.update(diff=f'cmp/{lang}-d{i + 1}.webp', areas=len(ch['rects']), items=ch['items'][:60])
            L['page'].append(row)
        rep['langs'][lang] = L
        if prev_structs and prev_structs.get(lang) and structs.get(lang):
            try: rep['changes'] += R.diff(prev_structs[lang], structs[lang], lang)[:400]
            except Exception: pass
    if structs.get('ar') and structs.get('en'):
        try: rep['pairs'] = R.conflicts(structs['ar'], structs['en'])
        except Exception: rep['pairs'] = []
    rep['issues'] = issues(rep)
    json.dump(rep, open(os.path.join(cd, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return rep


def issues(rep):
    """Short findings for the editor and the approver, in both languages."""
    out = []
    def add(level, ar, en): out.append({'level': level, 'ar': ar, 'en': en})
    for lang, L in rep['langs'].items():
        na, ne = ('العربية', 'Arabic') if lang == 'ar' else ('الإنجليزية', 'English')
        if L['prev_found'] and L['pages'] != L['prev_pages']:
            add('warn', f"النسخة {na} في {L['pages']} صفحات، وكانت في الربع السابق {L['prev_pages']}.",
                f"The {ne} version has {L['pages']} pages; last quarter it had {L['prev_pages']}.")
        for n in L['overflow']:
            add('warn', f'النسخة {na}، صفحة {n}: نص يتجاوز الهامش السفلي.', f'{ne} version, page {n}: text runs into the bottom margin.')
        for n in L['empty']:
            add('warn', f'النسخة {na}، صفحة {n}: الصفحة شبه فارغة.', f'{ne} version, page {n}: the page is almost empty.')
        if not L['prev_found']:
            add('info', f'لا توجد نسخة {na} من الربع السابق للمقارنة.', f'No {ne} statement from last quarter to compare with.')
    if rep['pairs']:
        add('warn', f"{len(rep['pairs'])} رقم يختلف بين النسختين العربية والإنجليزية.", f"{len(rep['pairs'])} figure(s) differ between the Arabic and English versions.")
    return out


def summary(fund, q):
    """Counts shown beside the generated files."""
    out = {}
    for kind in ('draft', 'final'):
        r = load(fund, q, kind)
        if r: out[kind] = {'warn': sum(1 for i in r['issues'] if i['level'] == 'warn'), 'pairs': len(r['pairs']), 'built': r['built']}
    return out


def load(fund, q, kind):
    base = store.out_dir(fund, q) if kind == 'draft' else os.path.join(store.out_dir(fund, q), kind)
    p = os.path.join(base, 'cmp', 'report.json')
    return json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else None
