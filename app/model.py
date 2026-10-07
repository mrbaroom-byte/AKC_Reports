"""Quarterly statement data model.

A statement is built from the previous quarter's struct (same fund, same language) plus the new quarter's data.
Sections are located by the order of their h2 headings, which is the same in every fund and both languages
(the CMA Annex 4 layout). Static text stays as it is; dates and quarter names are moved forward; values are
replaced; the fund manager's commentary is replaced whole.
"""
import copy, re, datetime

FUNDS = {
    'dif2030': {'ar': 'صندوق الخبير للدخل المتنوع 2030 المتداول', 'en': 'Alkhabeer Diversified Income Traded Fund 2030',
                'dir': 'i30', 'traded': True, 'symbol': '4702', 'wad': True, 'pe': False, 'si': False,
                'perf': 'price', 'doc_centre': 'dif2030'},
    'income': {'ar': 'صندوق الخبير للدخل المتنوع المتداول', 'en': 'Alkhabeer Diversified Income Traded Fund',
               'dir': 'inc', 'traded': True, 'symbol': '4700', 'wad': True, 'pe': False, 'si': False,
               'perf': 'price', 'doc_centre': 'income'},
    'gif': {'ar': 'صندوق الخبير للنمو والدخل', 'en': 'Alkhabeer Growth and Income Fund',
            'dir': 'gif', 'traded': False, 'symbol': '', 'wad': False, 'pe': True, 'si': True,
            'perf': 'fund_bench', 'doc_centre': 'gif'},
}
S = dict(objective=0, facts=1, defs=2, comment=3, contact=4, price=5, info=6, own=7, disc=8, top10=9,
         dist=10, rating=11, alloc=12, returns=13, risk=14, formulas=15, perf=16, more=17)
RISK = ['sd', 'sharpe', 'te', 'beta', 'alpha', 'ir']
RISK_AR = ['الانحراف المعياري', 'مؤشر شارب', 'خطأ التتبع', 'بيتا', 'ألفا', 'مؤشر المعلومات']

AR_M = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
AR_M_ALT = {'ابريل': 'أبريل', 'اغسطس': 'أغسطس', 'اكتوبر': 'أكتوبر'}
EN_M = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
EN_MS = [m[:3] for m in EN_M]
QORD_AR = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع'}
QORD_EN = {1: 'First', 2: 'Second', 3: 'Third', 4: 'Fourth'}


def qparse(q):
    m = re.match(r'q(\d)-(\d{4})$', q); return int(m.group(1)), int(m.group(2))


def qend(qn, y):
    return datetime.date(y, 3 * qn, {3: 31, 6: 30, 9: 30, 12: 31}[3 * qn])


def qstart(qn, y):
    return datetime.date(y, 3 * qn - 2, 1)


def prev_q(q):
    qn, y = qparse(q)
    return f'q{qn - 1}-{y}' if qn > 1 else f'q4-{y - 1}'


def next_q(q):
    qn, y = qparse(q)
    return f'q{qn + 1}-{y}' if qn < 4 else f'q1-{y + 1}'


def qlabel(q, lang):
    qn, y = qparse(q)
    return f'الربع {QORD_AR[qn]} {y}م' if lang == 'ar' else f'Q{qn} {y}'


# ---------- formatting ----------
def _num(v, dp):
    return f'{v:,.{dp}f}'


def fmt(kind, v, lang, na=None):
    """kind: money, nav, price, units, days, pct, pct3, plain, ratio, text"""
    if v is None or v == '':
        return na if na is not None else ('لا يوجد' if lang == 'ar' else 'N/A')
    if kind == 'text': return str(v)
    v = float(v)
    if kind == 'money': n = _num(v, 0); return f'{n} ر.س.' if lang == 'ar' else f'SAR {n}'
    if kind == 'nav': n = _num(v, 4); return f'{n} ر.س.' if lang == 'ar' else f'SAR {n}'
    if kind == 'price': n = _num(v, 2); return f'{n} ر.س.' if lang == 'ar' else f'SAR {n}'
    if kind == 'units': n = _num(v, 0); return f'{n} وحدة' if lang == 'ar' else f'{n} Units'
    if kind == 'days': n = _num(v, 0); return f'{n} يومًا' if lang == 'ar' else f'{n} days'
    if kind == 'pct': return f'{v:.2f}%'
    if kind == 'pct3': return f'{v:.3f}%'
    if kind == 'ratio': return f'{v:.1f}x'
    if kind == 'plain': return f'{v:.2f}'
    return str(v)


def to_float(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    t = str(s).replace(',', '').replace('٫', '.').strip()
    t = t.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    m = re.search(r'-?\d+(?:\.\d+)?', t)
    if not m: return None
    v = float(m.group(0))
    if re.search(r'\d\s*-\s*$', t) or re.match(r'^\s*%?\s*\d[\d.]*-', t): v = -abs(v)  # «1.16-» / «%7.24-»
    return v


# ---------- dates ----------
def ar_date(d): return f'{d.day} {AR_M[d.month - 1]} {d.year}م'
def en_date(d): return f'{d.day} {EN_M[d.month - 1]} {d.year}'


def shift_dates(text, lang, old_q, new_q, val_old=None, val_new=None):
    """Move every date tied to the old quarter (its end, its start, the same dates in earlier years, the valuation date)
    and the quarter's ordinal to the new quarter."""
    oq, oy = qparse(old_q); nq, ny = qparse(new_q)
    oe, ne = qend(oq, oy), qend(nq, ny); os_, ns = qstart(oq, oy), qstart(nq, ny)
    dy = ny - oy

    def mapdate(d):
        if val_old and d == val_old: return val_new or ne
        for k in range(0, 8):
            if d == oe.replace(year=oe.year - k): return ne.replace(year=ne.year - k)
            if d == os_.replace(year=os_.year - k): return ns.replace(year=ns.year - k)
        return None

    if lang == 'ar':
        for a, b in AR_M_ALT.items(): text = text.replace(a, b)

        def rep(m):
            d = datetime.date(int(m.group(3)), AR_M.index(m.group(2)) + 1, int(m.group(1)))
            n = mapdate(d)
            if not n: return m.group(0)
            return ar_date(n) if m.group(4) else ar_date(n)[:-1]
        text = re.sub(r'(\d{1,2}) (' + '|'.join(AR_M) + r') (\d{4})(م?)', rep, text)
        text = re.sub(r'\b(' + AR_M[oe.month - 1] + r') ' + str(oy) + 'م', AR_M[ne.month - 1] + ' ' + str(ny) + 'م', text)
        text = text.replace('الربع ' + QORD_AR[oq], 'الربع ' + QORD_AR[nq])
    else:
        def rep(m):
            d = datetime.date(int(m.group(3)), EN_M.index(m.group(2)) + 1, int(m.group(1)))
            n = mapdate(d); return en_date(n) if n else m.group(0)
        text = re.sub(r'(\d{1,2}) (' + '|'.join(EN_M) + r') (\d{4})', rep, text)

        def rep2(m):
            d = datetime.date(int(m.group(3)), EN_M.index(m.group(1)) + 1, int(m.group(2)))
            n = mapdate(d); return f'{EN_M[n.month - 1]} {n.day}, {n.year}' if n else m.group(0)
        text = re.sub(r'(' + '|'.join(EN_M) + r') (\d{1,2}), (\d{4})', rep2, text)
        text = re.sub(r'\b' + EN_M[oe.month - 1] + ' ' + str(oy) + r'\b', EN_M[ne.month - 1] + ' ' + str(ny), text)
        text = re.sub(r'\bQ' + str(oq) + r'\b', 'Q' + str(nq), text)
        text = text.replace(QORD_EN[oq] + ' Quarter', QORD_EN[nq] + ' Quarter').replace(QORD_EN[oq].lower() + ' quarter', QORD_EN[nq].lower() + ' quarter')
        text = re.sub(r'\b' + str(oy) + r'\b(?= Q| quarter)', str(ny), text) if dy else text
    if dy: text = text.replace(f'{QORD_AR[nq]} {oy}', f'{QORD_AR[nq]} {ny}').replace(f'Q{nq} {oy}', f'Q{nq} {ny}')
    return text


def _walk_text(obj, f):
    if isinstance(obj, str): return f(obj)
    if isinstance(obj, list): return [_walk_text(x, f) for x in obj]
    if isinstance(obj, dict): return {k: (_walk_text(v, f) if k not in ('t', 'key', 'kind', 'unit', 'p', 'src_file', 'template', 'lang') else v) for k, v in obj.items()}
    return obj


# ---------- struct navigation ----------
def sections(st):
    """List of (h2_index, [block indices]) in order."""
    b = st['blocks']; h = [i for i, x in enumerate(b) if x['t'] == 'h2']
    return [(h[k], list(range(h[k] + 1, h[k + 1] if k + 1 < len(h) else len(b)))) for k in range(len(h))]


def sec_blocks(st, name, t=None):
    secs = sections(st); _, idx = secs[S[name]]
    return [st['blocks'][i] for i in idx if t is None or st['blocks'][i]['t'] == t]


# ---------- read a struct into values (previous quarter / prefill) ----------
def extract(st_ar, st_en, fund):
    F = FUNDS[fund]; d = {}
    fa = sec_blocks(st_ar, 'facts', 'kv')[0]['rows']
    d['nav_unit'] = to_float(fa[2][1]); d['fund_size'] = to_float(fa[3][1])
    d['wad_days'] = to_float(fa[11][1]) if F['wad'] else None
    pr = sec_blocks(st_ar, 'price', 'kv')[0]['rows']
    d['price'] = to_float(pr[0][1]); d['units'] = to_float(pr[3][1]); d['net_assets'] = to_float(pr[4][1])
    d['pe'] = pr[5][1] if F['pe'] else None
    info = sec_blocks(st_ar, 'info', 'table')[0]['rows']
    d['ter_amount'] = to_float(info[0][1]); d['dealing'] = to_float(info[2][1]); d['mgr_invest'] = to_float(info[3][1])
    d['borrowing'] = to_float(info[1][1])
    n = [x['text'] for x in sec_blocks(st_ar, 'info', 'note')]
    d['avg_nav'] = to_float(re.search(r'=\s*([\d,]+)', n[0]).group(1)) if n and re.search(r'=\s*([\d,]+)', n[0]) else None
    own = sec_blocks(st_ar, 'own', 'kv')[0]['rows']; d['own_full'] = to_float(own[0][1]); d['own_use'] = to_float(own[1][1])
    dist = sec_blocks(st_ar, 'dist', 'kv')[0]['rows']
    d['dist_total'] = to_float(dist[0][1]); d['dist_units'] = to_float(dist[1][1]); d['dist_per_unit'] = to_float(dist[2][1])
    d['dist_entitle'] = {'ar': dist[4][1], 'en': sec_blocks(st_en, 'dist', 'kv')[0]['rows'][4][1]}
    ra = sec_blocks(st_ar, 'rating', 'kv')[0]['rows']; re_ = sec_blocks(st_en, 'rating', 'kv')[0]['rows']
    d['rating'] = {'ar': [r[1] for r in ra], 'en': [r[1] for r in re_]}
    ta = sec_blocks(st_ar, 'top10', 'chart')[0]['series']; te = sec_blocks(st_en, 'top10', 'chart')[0]['series']
    d['top10'] = pair_series(ta, te)
    ca = sec_blocks(st_ar, 'alloc', 'chart'); ce = sec_blocks(st_en, 'alloc', 'chart')
    d['alloc'] = []
    for a in ca:
        e = _match_chart(a, ce)
        d['alloc'].append({'title_ar': a.get('title', ''), 'title_en': e.get('title', '') if e else '', 'items': pair_series(a['series'], e['series'] if e else [])})
    rt = sec_blocks(st_ar, 'returns', 'table')[0]
    d['periods_ar'] = rt['head'][1:]; d['periods_en'] = sec_blocks(st_en, 'returns', 'table')[0]['head'][1:]
    d['ret_fund'] = [to_float(x) for x in rt['rows'][0][1:]]; d['ret_bench'] = [to_float(x) for x in rt['rows'][1][1:]]
    rk = sec_blocks(st_ar, 'risk', 'table')[0]['rows']
    d['risk'] = {k: [to_float(x) for x in rk[i][1:]] for i, k in enumerate(RISK)}
    d['risk_pct'] = [('%' in ' '.join(r[1:])) for r in rk]
    pa = sec_blocks(st_ar, 'perf', 'chart')[0]
    d['perf_last'] = pa['series'][-6:]
    d['commentary'] = {'ar': comment_text(st_ar), 'en': comment_text(st_en)}
    return d


def _match_chart(a, ce):
    va = sorted(round(s['value'], 1) for s in a['series'])
    for e in ce:
        if sorted(round(s['value'], 1) for s in e['series']) == va: return e
    return None


def pair_series(sa, se):
    """Pair Arabic and English labels of the same chart: by position when the values line up, otherwise by value."""
    out = []
    if [round(x['value'], 1) for x in sa] == [round(x['value'], 1) for x in se]:
        for a, e in zip(sa, se): out.append({'ar': a['label'], 'en': e['label'], 'pct': a['value']})
        return out
    pool = list(se)
    for a in sa:
        m = min(pool, key=lambda e: abs(e['value'] - a['value'])) if pool else None
        if m: pool.remove(m)
        out.append({'ar': a['label'], 'en': m['label'] if m else '', 'pct': a['value']})
    return out


def comment_text(st):
    out = []
    for b in sec_blocks(st, 'comment'):
        if b['t'] == 'p': out.append(b['text'])
        elif b['t'] == 'h3': out.append('# ' + b['text'])
        elif b['t'] == 'ul': out.append('\n'.join('- ' + i for i in b.get('items', [])))
    return '\n\n'.join(out)


def comment_blocks(text):
    out = []
    for para in re.split(r'\n\s*\n', (text or '').strip()):
        para = para.strip()
        if not para: continue
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        if lines[0].startswith('#'):
            out.append({'t': 'h3', 'text': lines[0].lstrip('#').strip()}); lines = lines[1:]
            if not lines: continue
        if all(l.startswith(('- ', '• ')) for l in lines):
            out.append({'t': 'ul', 'items': [l[2:].strip() for l in lines]})
        else:
            out.append({'t': 'p', 'text': ' '.join(lines)})
    return out


# ---------- derived values ----------
def derive(d, prev):
    r = {}
    nav = d.get('nav_unit'); units = d.get('units')
    r['net_assets'] = round(nav * units) if nav and units else None
    pp = prev.get('price') if prev else None
    cur = d.get('price')
    r['price_change'] = (cur / pp - 1) * 100 if cur and pp else None
    avg = d.get('avg_nav')
    r['ter_pct'] = d['ter_amount'] / avg * 100 if d.get('ter_amount') and avg else None
    r['dealing_pct'] = d['dealing'] / avg * 100 if d.get('dealing') and avg else None
    r['mgr_pct'] = d['mgr_invest'] / r['net_assets'] * 100 if d.get('mgr_invest') and r['net_assets'] else None
    r['borrow_pct'] = d['borrowing'] / d['fund_size'] * 100 if d.get('borrowing') and d.get('fund_size') else None
    r['dist_pct'] = d['dist_total'] / r['net_assets'] * 100 if d.get('dist_total') and r['net_assets'] else None
    r['discount'] = (1 - cur / nav) * 100 if cur and nav else None
    rf, rb = d.get('ret_fund') or [], d.get('ret_bench') or []
    r['spread'] = [(a - b) if a is not None and b is not None else None for a, b in zip(rf, rb)]
    return r


# ---------- build the new struct ----------
def build(fund, lang, prev_st, prev_q, q, d, prev_vals):
    F = FUNDS[fund]; ar = lang == 'ar'
    st = copy.deepcopy(prev_st)
    val_old = _parse_val(prev_vals.get('valuation_date')) if prev_vals else None
    val_new = _parse_val(d.get('valuation_date'))
    if fund == 'gif' and not val_old: val_old = datetime.date(2026, 6, 29) if prev_q == 'q2-2026' else None
    st = _walk_text(st, lambda t: shift_dates(t, lang, prev_q, q, val_old, val_new))
    st['id'] = q
    der = derive(d, prev_vals)
    na = 'لا يوجد' if ar else 'N/A'
    # key facts
    fa = sec_blocks(st, 'facts', 'kv')[0]['rows']
    fa[2][1] = fmt('nav', d.get('nav_unit'), lang); fa[3][1] = fmt('money', d.get('fund_size'), lang)
    if F['wad']: fa[11][1] = fmt('days', d.get('wad_days'), lang, na='- يومًا' if ar else '- days')
    for b in sec_blocks(st, 'facts', 'note'):  # drop one-off lines (e.g. the Q2 2026 cut-off explanation)
        b['text'] = '\n'.join(l for l in b['text'].split('\n') if not re.search(r'تاريخاً للقطع|cut-off', l))
    # prices
    pr = sec_blocks(st, 'price', 'kv')[0]['rows']
    pr[0][1] = fmt('price' if F['traded'] else 'nav', d.get('price'), lang)
    pr[1][1] = fmt('pct', der['price_change'], lang)
    pr[3][1] = fmt('units', d.get('units'), lang); pr[4][1] = fmt('money', der['net_assets'], lang)
    if F['pe']: pr[5][1] = d.get('pe') or pr[5][1]
    for b in sec_blocks(st, 'price', 'note'):
        if F['traded'] and der['discount'] is not None:
            b['text'] = re.sub(r'\d+(?:\.\d+)?%', f"{der['discount']:.0f}%", b['text'], count=1)
            if der['discount'] < 0:
                b['text'] = b['text'].replace('خصماً', 'علاوة').replace('discount', 'premium')
        if not F['traded'] and prev_vals and prev_vals.get('price'):
            b['text'] = re.sub(r'[\d.]+(?= ر\.س| SAR)', f"{prev_vals['price']:.4f}", b['text'], count=1)
    # fund information
    info = sec_blocks(st, 'info', 'table')[0]['rows']

    def money_pct(row, amt, pct, kind='pct'):
        if amt is None: row[1] = row[1] if to_float(row[1]) is None else na; row[2] = row[2] if to_float(row[2]) is None else na
        else: row[1] = fmt('money', amt, lang); row[2] = fmt(kind, pct, lang)
    money_pct(info[0], d.get('ter_amount'), der['ter_pct'])
    money_pct(info[1], d.get('borrowing'), der['borrow_pct'])
    money_pct(info[2], d.get('dealing'), der['dealing_pct'], 'pct3')
    money_pct(info[3], d.get('mgr_invest'), der['mgr_pct'])
    if d.get('dist_total') is not None or to_float(info[4][1]) is not None:
        info[4][1] = fmt('money', d.get('dist_total') or 0, lang); info[4][2] = fmt('pct', der['dist_pct'] or 0, lang)
    for b in sec_blocks(st, 'info', 'note'):
        if d.get('avg_nav'): b['text'] = re.sub(r'[\d,]{5,}', _num(d['avg_nav'], 0), b['text'], count=1)
    # ownership
    own = sec_blocks(st, 'own', 'kv')[0]['rows']
    own[0][1] = f"{d.get('own_full', 100):g}%"; own[1][1] = f"{d.get('own_use', 0):g}%"
    # top ten
    ch = sec_blocks(st, 'top10', 'chart')[0]
    ch['series'] = [{'label': x[lang] or x['ar'], 'value': float(x['pct'])} for x in d.get('top10', []) if x.get('pct') not in (None, '')]
    # distributions
    dist = sec_blocks(st, 'dist', 'kv')[0]['rows']; dna = dist[0][1] if to_float(dist[0][1]) is None else na
    if d.get('dist_total'):
        dist[0][1] = fmt('money', d['dist_total'], lang); dist[1][1] = fmt('units', d.get('dist_units'), lang)
        dist[2][1] = fmt('price', d.get('dist_per_unit'), lang); dist[3][1] = fmt('pct', der['dist_pct'], lang)
        dist[4][1] = (d.get('dist_entitle') or {}).get(lang) or dist[4][1]
    else:
        for r in dist: r[1] = dna
    # ratings
    rt = sec_blocks(st, 'rating', 'kv')[0]['rows']; rv = (d.get('rating') or {}).get(lang)
    if rv:
        for i, r in enumerate(rt[:4]): r[1] = rv[i] if i < len(rv) and rv[i] else r[1]
    # allocation charts
    cs = sec_blocks(st, 'alloc', 'chart')
    for c, a in zip(cs, d.get('alloc', [])):
        c['series'] = [{'label': x[lang] or x['ar'], 'value': float(x['pct'])} for x in a['items'] if x.get('pct') not in (None, '')]
    # returns
    rtb = sec_blocks(st, 'returns', 'table')[0]

    def cells(vals, k='pct'):
        return [fmt(k, v, lang, na='لا ينطبق' if ar else 'N/A') for v in vals]
    n = len(rtb['head']) - 1
    rtb['rows'][0][1:] = cells((d.get('ret_fund') or [None] * n)[:n])
    rtb['rows'][1][1:] = cells((d.get('ret_bench') or [None] * n)[:n])
    rtb['rows'][2][1:] = cells(der['spread'][:n] if der['spread'] else [None] * n)
    rk = sec_blocks(st, 'risk', 'table')[0]
    m = len(rk['head']) - 1
    for i, k in enumerate(RISK):
        vals = (d.get('risk', {}).get(k) or [None] * m)[:m]
        rk['rows'][i][1:] = cells(vals, 'pct' if (prev_vals or {}).get('risk_pct', [False] * 6)[i] else 'plain')
    # performance chart: append the new quarter's points
    pc = sec_blocks(st, 'perf', 'chart')[0]
    pts = d.get('perf_points') or []
    if F['perf'] == 'price':
        for p in pts:
            dt = _parse_val(p.get('date'))
            if not dt or p.get('value') in (None, ''): continue
            pc['series'].append({'label': _perf_label(pc['series'][-1]['label'], dt, lang), 'value': float(p['value'])})
    else:
        fl = 'الصندوق' if ar else 'Fund'; bl = 'المؤشر' if ar else 'Benchmark'
        labels = {s['label'] for s in pc['series']}
        fl = next((x for x in labels if x in ('الصندوق', 'Fund')), fl); bl = next((x for x in labels if x not in (fl,)), bl)
        lastg = pc['series'][-1].get('group', '')
        for p in pts:
            dt = _parse_val(p.get('date'))
            if not dt: continue
            g = ar_date(dt) if ar else f'{EN_MS[dt.month - 1]} {dt.day}, {dt.year}'
            if p.get('fund') not in (None, ''): pc['series'].append({'label': fl, 'value': float(p['fund']), 'group': g})
            if p.get('bench') not in (None, ''): pc['series'].append({'label': bl, 'value': float(p['bench']), 'group': g})
    # commentary
    secs = sections(st); h, idx = secs[S['comment']]
    new = comment_blocks((d.get('commentary') or {}).get(lang, '')) or [{'t': 'p', 'text': 'لا ينطبق.' if ar else 'Not applicable.'}]
    st['blocks'] = st['blocks'][:h + 1] + new + st['blocks'][idx[-1] + 1 if idx else h + 1:]
    # contact: toll-free number when chosen
    if d.get('tollfree'):
        for b in sec_blocks(st, 'contact', 'kv'):
            for r in b['rows']:
                if re.search(r'هاتف|Phone|Telephone', r[0]): r[1] = d['tollfree']
    return st


def _parse_val(s):
    if not s: return None
    if isinstance(s, datetime.date): return s
    try: return datetime.date.fromisoformat(str(s)[:10])
    except Exception: return None


def _perf_label(last, dt, lang):
    if re.match(r'\d{4}-\d{2}-\d{2}$', last): return dt.isoformat()
    if re.match(r'\d{1,2}-[A-Z][a-z]{2}-\d{2}$', last): return f'{dt.day}-{EN_MS[dt.month - 1]}-{str(dt.year)[2:]}'
    if 'م' in last: return ar_date(dt)
    return en_date(dt)


# ---------- validation ----------
def validate(fund, d, prev, q):
    F = FUNDS[fund]; out = []

    def add(level, msg, field=None): out.append({'level': level, 'msg': msg, 'field': field})
    req = [('nav_unit', 'صافي قيمة الوحدة'), ('fund_size', 'حجم الصندوق'), ('units', 'عدد الوحدات القائمة'),
           ('avg_nav', 'متوسط صافي الأصول'), ('ter_amount', 'الأتعاب والمصروفات'), ('price', 'سعر الوحدة' if F['traded'] else 'صافي قيمة الوحدة في نهاية الربع')]
    for k, n in req:
        if d.get(k) in (None, ''): add('block', f'الحقل «{n}» فارغ.', k)
    if not (d.get('commentary') or {}).get('ar', '').strip(): add('block', 'تعليق مدير الصندوق بالعربية فارغ.', 'commentary.ar')
    if not (d.get('commentary') or {}).get('en', '').strip(): add('block', 'تعليق مدير الصندوق بالإنجليزية فارغ.', 'commentary.en')
    t10 = [x for x in d.get('top10', []) if x.get('pct') not in (None, '')]
    if len(t10) != 10: add('warn', f'أكبر الاستثمارات: {len(t10)} بندًا بدل 10.', 'top10')
    for x in t10:
        if not x.get('ar') or not x.get('en'): add('block', 'أكبر الاستثمارات: بند بلا اسم عربي أو إنجليزي.', 'top10'); break
    for k, a in enumerate(d.get('alloc', [])):
        t = re.sub(r'\*+', '', a['title_ar']).strip()
        s = sum(float(x['pct']) for x in a['items'] if x.get('pct') not in (None, ''))
        if a['items'] and abs(s - 100) > 0.5: add('block', f'«{t}»: المجموع {s:.1f}% لا 100%.', f'alloc.{k}')
        for x in a['items']:
            if x.get('pct') not in (None, '') and (not x.get('ar') or not x.get('en')): add('block', f'«{t}»: بند بلا اسم في إحدى اللغتين.', f'alloc.{k}'); break
    der = derive(d, prev)
    if d.get('fund_size') and der['net_assets'] and der['net_assets'] > d['fund_size'] * 1.001:
        add('warn', 'صافي الأصول المحسوب أكبر من حجم الصندوق (إجمالي الأصول).')
    qn, _ = qparse(q)
    rf, rb = d.get('ret_fund') or [], d.get('ret_bench') or []
    if qn == 1:
        for nm, arr in (('الصندوق', rf), ('المؤشر', rb)):
            if len(arr) > 1 and arr[0] is not None and arr[1] is not None and abs(arr[0] - arr[1]) > 0.005:
                add('block', f'في الربع الأول يجب أن يساوي عائد «منذ بداية السنة» عائد الأشهر الثلاثة ({nm}).', 'ret_fund')
    if prev:
        for k, n in (('nav_unit', 'صافي قيمة الوحدة'), ('units', 'عدد الوحدات')):
            if d.get(k) and prev.get(k) and abs(d[k] / prev[k] - 1) > 0.10:
                add('warn', f'«{n}» تغيّر أكثر من 10% عن الربع السابق.', k)
    rk = d.get('risk') or {}
    if F['wad']:
        for i, v in enumerate(rk.get('beta') or []):
            if v is not None and abs(v) > 3: add('warn', f'بيتا {v:g} خارج النطاق المعقول لصندوق دخل.', 'risk.beta'); break
    for i in range(len(RISK)):
        for j in range(i + 1, len(RISK)):
            a, b = rk.get(RISK[i]) or [], rk.get(RISK[j]) or []
            if a and a == b and any(x is not None for x in a): add('warn', f'«{RISK_AR[i]}» و«{RISK_AR[j]}» متطابقان في كل الفترات.', f'risk.{RISK[i]}')
    ca = re.findall(r'-?\d+(?:\.\d+)?(?=\s*%)', (d.get('commentary') or {}).get('ar', ''))
    ce = re.findall(r'-?\d+(?:\.\d+)?(?=\s*%)', (d.get('commentary') or {}).get('en', ''))
    if sorted(ca) != sorted(ce): add('warn', 'النسب المذكورة في التعليق العربي لا تطابق المذكورة في الإنجليزي.', 'commentary.en')
    pts = [p for p in d.get('perf_points') or [] if p.get('value') not in (None, '') or p.get('fund') not in (None, '')]
    if not pts: add('warn', 'لم تُضف نقاط هذا الربع إلى رسم ' + ('سعر السوق.' if F['traded'] else 'الأداء.'), 'perf_points')
    return out


def leftovers(st, prev_q, lang):
    """Old-quarter words still in the new statement (after the date shift), outside the commentary."""
    oq, oy = qparse(prev_q); secs = sections(st); h, idx = secs[S['comment']]
    txt = str([b for i, b in enumerate(st['blocks']) if i not in idx])
    pats = [AR_M[qend(oq, oy).month - 1] + f' {oy}', 'الربع ' + QORD_AR[oq]] if lang == 'ar' else [EN_M[qend(oq, oy).month - 1] + f' {oy}', f'Q{oq} ', QORD_EN[oq] + ' Quarter']
    return [p for p in pats if p in txt]
