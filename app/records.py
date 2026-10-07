"""Historical statements as records: import, AR/EN conflict check, field-level diff for the correction log."""
import os, json, glob, re
import model as M, store

ENG = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'engine'))
PUB = os.path.join(ENG, 'published')
TYPES = ('kv', 'table', 'chart')


def _sections(st):
    b = st['blocks']; h = [i for i, x in enumerate(b) if x['t'] == 'h2']
    out = []
    for k, i in enumerate(h):
        j = h[k + 1] if k + 1 < len(h) else len(b)
        out.append((b[i].get('text', ''), [b[x] for x in range(i + 1, j)]))
    return out


_DIG = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def _reads(v):
    """Possible numeric readings of a cell with their precision (Arabic decimal comma «9,9491» or thousands «2,731,400»)."""
    t = str(v).translate(_DIG).replace('٫', '.').replace('٬', ',')
    t = re.sub(r'(?<=[\d\-]) +(?=[\d\-])', '', t)                       # «12.13 72», «- 0.89», «22.53 -»
    paren = bool(re.search(r'\(\s*[\d.,]+\s*\)', t))
    m2 = re.search(r'\d{1,3}(?:\.\d{3})+\.\d{1,2}(?!\d)', t)               # «3.029.317.96»: dots for thousands, last one decimal
    if m2: g = m2.group(0); i = g.rfind('.'); t = t.replace(g, g[:i].replace('.', '') + g[i:])
    elif re.search(r'\d{1,3}(\.\d{3}){2,}', t): t = t.replace('.', '')    # «1.037.104.071» thousands with dots
    m = re.search(r'-?\d[\d,]*(?:\.\d+)?-?', t)
    if not m: return []
    x = m.group(0); neg = x.startswith('-') or x.endswith('-') or paren; x = x.strip('-')
    out = []
    for y in {x.replace(',', ''), x.replace(',', '.') if x.count(',') == 1 and '.' not in x else None} - {None}:
        try:
            f = float(y); dp = len(y.split('.')[1]) if '.' in y else 0
            out.append((-f if neg else f, dp))
        except ValueError: pass
    return out


def _same(a, b, tol=0.0, exact=False):
    """Equal once rounded to the coarser of the two precisions (plus a tolerance for values measured off a chart)."""
    ra = [(float(a), 0 if float(a).is_integer() else len(repr(float(a)).split('.')[1]))] if isinstance(a, (int, float)) else _reads(a)
    rb = [(float(b), 0 if float(b).is_integer() else len(repr(float(b)).split('.')[1]))] if isinstance(b, (int, float)) else _reads(b)
    for x, px in ra:
        for y, py in rb:
            if abs(x - y) <= (1e-9 if exact else 0.5 * 10 ** -min(px, py) + tol + 1e-9): return True
    return False


def _isnum(v):
    return bool(_reads(v)) and len(re.sub(r'[\d\s.,٫٬%\-+()٠-٩]|ر\.?س\.?|SAR|SR|Days?|يوم|مليون|million', '', str(v), flags=re.I)) <= 2


def _match(xs, ys, tol=0.0):
    """Pair each value with an equal one on the other side (identical values first, then equal after rounding);
    return what is left unpaired on each side."""
    for exact in (True, False):
        ys = list(ys); left = []
        for x in xs:
            k = next((i for i, y in enumerate(ys) if _same(x[1], y[1], tol, exact)), None)
            if k is None: left.append(x)
            else: ys.pop(k)
        xs = left
    return left, ys


CHECK_V = 3   # bump to recompute stored differences after the check changes


def conflicts(A, E):
    """Figures that differ between the Arabic and English versions of the same statement.
    Table values are matched within each block regardless of row order, and chart values within each section regardless
    of which chart comes first; rounding differences are ignored. Performance lines are not compared (read off images)."""
    out = []
    sa, se = _sections(A), _sections(E)
    def cells(b):
        if b['t'] == 'chart': return [((b.get('title') or '').split('\n')[0] + ': ' + str(s.get('group') or s.get('label')), s['value']) for s in b.get('series', [])]
        return [(str(r[0]) + (' · ' + str((b.get('head') or [''] * (k + 1))[k]) if b['t'] == 'table' and len(b.get('head') or []) > k else ''), c)
                for r in b.get('rows', []) for k, c in enumerate(r[1:], 1) if _isnum(c)]
    for (ha, ba), (he, be) in zip(sa, se):
        ta = [b for b in ba if b['t'] in ('kv', 'table')]; te = [b for b in be if b['t'] in ('kv', 'table')]
        for a, e in zip(ta, te):
            if a['t'] != e['t']: break
            xa_, xe_ = cells(a), cells(e)
            la, le = _match(xa_, xe_)
            if a['t'] == 'table' and len(xa_) == len(xe_) and la:
                # same grid in both languages: report the differing cells at their own position
                pos = [(x, y) for x, y in zip(xa_, xe_) if not _same(x[1], y[1])]
                if len(pos) == len(la): la, le = [x for x, _ in pos], [y for _, y in pos]
            for (xa, va), (xe, ve) in zip(la, le):
                out.append({'kind': 'figure', 'section': ha, 'label': xa.strip(' ·:'), 'label_en': xe.strip(' ·:'), 'ar': str(va), 'en': str(ve)})
    # charts: each Arabic chart is paired with the English chart that shares most of its values (the two versions may
    # place the charts in a different order or section), then compared value by value
    ca = [b for h, bs in sa for b in bs if b['t'] == 'chart' and b.get('kind') != 'line']
    ce = [b for h, bs in se for b in bs if b['t'] == 'chart' and b.get('kind') != 'line']
    used = set()
    for a in ca:
        best, score = None, -1
        for j, e in enumerate(ce):
            if j in used: continue
            la, _ = _match(cells(a), cells(e)); sc = len(cells(a)) - len(la) - abs(len(a.get('series', [])) - len(e.get('series', []))) * 0.5
            if sc > score: best, score = j, sc
        if best is None: continue
        used.add(best)
        la, le = _match(cells(a), cells(ce[best]))
        la, le = _match(la, le, tol=0.02)
        for (xa, va), (xe, ve) in zip(la, le):
            out.append({'kind': 'chart', 'section': (a.get('title') or '').split('\n')[0], 'label': xa.strip(' ·:'), 'label_en': xe.strip(' ·:'), 'ar': f'{va:g}', 'en': f'{ve:g}'})
    return out


def is_annex4(st):
    return sum(1 for b in st['blocks'] if b['t'] == 'h2') == 18


def import_history(seed_q=None):
    """Create a 'published' record for every statement in the engine that has none yet. Idempotent."""
    made = 0
    redo = (store.get_conflicts('_meta', 'check') or [0])[0] != CHECK_V
    for fund, F in M.FUNDS.items():
        sd = os.path.join(ENG, F['dir'], 'struct')
        qs = sorted({os.path.basename(p)[:-8] for p in glob.glob(os.path.join(sd, 'q[1-4]-20[0-9][0-9].ar.json'))})
        for q in qs:
            pa, pe = os.path.join(sd, f'{q}.ar.json'), os.path.join(sd, f'{q}.en.json')
            if not os.path.exists(pe) or not os.path.isdir(os.path.join(PUB, fund, q)): continue
            rec = store.get(fund, q)
            A = json.load(open(pa, encoding='utf-8')); E = json.load(open(pe, encoding='utf-8'))
            if redo or store.get_conflicts(fund, q) is None:
                cur = {l: (json.load(open(store.struct_path(fund, q, l), encoding='utf-8')) if os.path.exists(store.struct_path(fund, q, l)) else s)
                       for l, s in (('ar', A), ('en', E))}
                store.set_conflicts(fund, q, conflicts(cur['ar'], cur['en']))
            if rec: continue
            data = {}
            if is_annex4(A):
                try:
                    data = M.extract(A, E, fund)
                    data['perf_points'] = []
                    data['valuation_date'] = '2026-06-29' if (fund == 'gif' and q == 'q2-2026') else M.qend(*M.qparse(q)).isoformat()
                except Exception:
                    data = {}
            for l, s in (('ar', A), ('en', E)):
                json.dump(s, open(store.struct_path(fund, q, l), 'w', encoding='utf-8'), ensure_ascii=False)
            fs = {}
            pd = os.path.join(PUB, fund, q)
            if os.path.isdir(pd):
                for n in sorted(os.listdir(pd)):
                    l = 'ar' if re.search(r'-AR\.(pdf|docx)$', n) else 'en'
                    fs.setdefault(l, {})['pdf' if n.endswith('.pdf') else 'docx'] = n
            store.put(fund, q, data=data, status='published', final_at='منشور', files={'published': fs})
            store.event(fund, q, 'استيراد البيان المنشور من مستندات الصناديق')
            made += 1
    store.set_conflicts('_meta', 'check', [CHECK_V])
    return made


def diff(old, new, lang):
    """Field-level changes between two versions of one statement (for the correction log)."""
    rows = []
    so, sn = _sections(old), _sections(new)
    for (h, bo), (_, bn) in zip(so, sn):
        for a, b in zip(bo, bn):
            if a['t'] != b['t']: continue
            if a['t'] == 'kv':
                for ra, rb in zip(a.get('rows', []), b.get('rows', [])):
                    for k in range(len(ra)):
                        if k < len(rb) and ra[k] != rb[k]:
                            rows.append({'lang': lang, 'section': h, 'label': ra[0] if k else '(اسم البند)', 'before': ra[k], 'after': rb[k]})
            elif a['t'] == 'table':
                for ra, rb in zip(a.get('rows', []), b.get('rows', [])):
                    for k in range(len(ra)):
                        if k < len(rb) and ra[k] != rb[k]:
                            col = (a.get('head') or [])[k] if k < len(a.get('head') or []) else ''
                            rows.append({'lang': lang, 'section': h, 'label': f'{ra[0]} · {col}'.strip(' ·'), 'before': ra[k], 'after': rb[k]})
            elif a['t'] == 'chart':
                for sa, sb in zip(a.get('series', []), b.get('series', [])):
                    for k in ('label', 'value'):
                        if sa.get(k) != sb.get(k):
                            rows.append({'lang': lang, 'section': h, 'label': f"{a.get('title', '')}: {sa.get('label')}", 'before': str(sa.get(k)), 'after': str(sb.get(k))})
                if len(a.get('series', [])) != len(b.get('series', [])):
                    rows.append({'lang': lang, 'section': h, 'label': f"{a.get('title', '')}: عدد البنود", 'before': str(len(a['series'])), 'after': str(len(b['series']))})
            elif a['t'] in ('p', 'note', 'h3'):
                if a.get('text') != b.get('text'):
                    rows.append({'lang': lang, 'section': h, 'label': 'نص', 'before': a.get('text', ''), 'after': b.get('text', '')})
            elif a['t'] == 'ul':
                if a.get('items') != b.get('items'):
                    rows.append({'lang': lang, 'section': h, 'label': 'قائمة', 'before': '\n'.join(a.get('items', [])), 'after': '\n'.join(b.get('items', []))})
    return rows


def dependents(fund, q, n=4):
    """Later statements of the same fund that may carry figures from this one."""
    out, cur = [], q
    have = {r['q']: r for r in store.all_records() if r['fund'] == fund}
    for _ in range(n):
        cur = M.next_q(cur)
        if cur in have and have[cur]['status'] in ('published', 'final', 'corrected'): out.append(cur)
    return out


def qkey(q):
    qn, y = M.qparse(q); return (y, qn)


def load(fund, q, lang, draft=False):
    p = store.draft_struct_path(fund, q, lang) if draft else store.struct_path(fund, q, lang)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def has_draft(fund, q):
    return all(os.path.exists(store.draft_struct_path(fund, q, l)) for l in ('ar', 'en'))


def same_shape(a, b):
    """A correction edits values only: same blocks, same types, same row and series counts."""
    if len(a['blocks']) != len(b['blocks']): return False
    for x, y in zip(a['blocks'], b['blocks']):
        if x['t'] != y['t']: return False
        if x['t'] in ('kv', 'table') and len(x.get('rows', [])) != len(y.get('rows', [])): return False
        if x['t'] == 'chart' and len(x.get('series', [])) != len(y.get('series', [])): return False
    return True
