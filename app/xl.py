"""Excel intake: one workbook per fund and quarter, a sheet per source (FACO, Capital Markets, Tadawul).

Column A of every input row holds a hidden key (e.g. `nav_unit`, `top10.3`, `ret.1`) so the file can be read back
whatever the sources do to the layout around it. Reading never saves: it returns the merged data and the list of
changes for the person to accept in the editor.
"""
import io, copy, datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
import model as M

NAVY, BLUE, PAPER, INPUT = '12284B', '2E6DB0', 'F3F6FA', 'FFF4D6'
FONT = 'Arial'

FACO = [('valuation_date', 'تاريخ التقويم (YYYY-MM-DD)', 'Valuation date'),
        ('nav_unit', 'صافي قيمة الوحدة (ر.س.)', 'NAV per unit (SAR)'),
        ('fund_size', 'حجم الصندوق: إجمالي الأصول (ر.س.)', 'Fund size: total assets (SAR)'),
        ('units', 'عدد الوحدات القائمة', 'Units outstanding'),
        ('avg_nav', 'متوسط صافي الأصول خلال الربع (ر.س.)', 'Average NAV in the quarter (SAR)'),
        ('ter_amount', 'الأتعاب والمصروفات الإجمالية (ر.س.)', 'Total fees and expenses (SAR)'),
        ('borrowing', 'الاقتراض (ر.س.)', 'Borrowing (SAR)'),
        ('dealing', 'مصاريف التعامل (ر.س.)', 'Dealing expenses (SAR)'),
        ('mgr_invest', 'استثمار مدير الصندوق (ر.س.)', "Fund manager's investment (SAR)"),
        ('wad_days', 'عدد أيام المتوسط المرجح', 'Weighted average days'),
        ('dist_total', 'إجمالي التوزيعات خلال الربع (ر.س.)', 'Total distributions in the quarter (SAR)'),
        ('dist_units', 'عدد الوحدات المستحقة للتوزيع', 'Units entitled to the distribution'),
        ('dist_per_unit', 'التوزيع لكل وحدة (ر.س.)', 'Distribution per unit (SAR)')]
LABEL = {k: a for k, a, _ in FACO}
LABEL.update(price='سعر الوحدة في السوق نهاية الربع (ر.س.)', pe='مكرر الربحية', own_full='ملكية تامة %', own_use='حق منفعة %',
             **{'commentary.ar': 'تعليق مدير الصندوق (عربي)', 'commentary.en': 'Fund manager commentary (English)'})
NUM = {'nav_unit', 'fund_size', 'units', 'avg_nav', 'ter_amount', 'borrowing', 'dealing', 'mgr_invest', 'wad_days',
       'dist_total', 'dist_units', 'dist_per_unit', 'price', 'own_full', 'own_use'}

thin = Side(style='thin', color='DDE3ED')


def _hdr(ws, row, cells):
    for i, v in enumerate(cells, 2):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(name=FONT, bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor=NAVY)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)


def _title(ws, row, text):
    c = ws.cell(row=row, column=2, value=text); c.font = Font(name=FONT, bold=True, size=12, color=NAVY)
    return row + 1


def _in(c, fmt=None):
    c.fill = PatternFill('solid', fgColor=INPUT); c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    c.font = Font(name=FONT); c.alignment = Alignment(vertical='center', wrap_text=True)
    if fmt: c.number_format = fmt


def _ro(c, fmt=None):
    c.font = Font(name=FONT, color='5B667C'); c.alignment = Alignment(vertical='center', wrap_text=True)
    if fmt: c.number_format = fmt


def _key(ws, row, key):
    ws.cell(row=row, column=1, value=key).font = Font(name=FONT, color='FFFFFF', size=8)


def _sheet(wb, title, intro):
    ws = wb.create_sheet(title); ws.sheet_view.rightToLeft = True
    ws.column_dimensions['A'].hidden = True
    for col, w in zip('BCDEFGH', (46, 30, 22, 22, 22, 22, 22)): ws.column_dimensions[col].width = w
    c = ws.cell(row=1, column=2, value=intro); c.font = Font(name=FONT, size=10, color='5B667C'); c.alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=6); ws.row_dimensions[1].height = 42
    return ws


def build(fund, q, data, prev):
    F = M.FUNDS[fund]; ql = M.qlabel(q, 'ar'); pql = M.qlabel(M.prev_q(q), 'ar')
    data = data or {}; prev = prev or {}
    wb = Workbook(); wb.remove(wb.active)
    note = f'{F["ar"]} · {ql}. اكتب في الخانات الصفراء فقط، ولا تغيّر ترتيب الصفوف. عمود «{pql}» للمقارنة.'

    # ---- FACO ----
    ws = _sheet(wb, 'FACO', note + ' المصدر: إدارة عمليات الصناديق والحفظ.')
    r = 3; _hdr(ws, r, ['البند', 'Item', pql, ql]); r += 1
    for k, ar, en in FACO:
        if k == 'wad_days' and not F['wad']: continue
        _key(ws, r, k); ws.cell(row=r, column=2, value=ar).font = Font(name=FONT); _ro(ws.cell(row=r, column=3, value=en))
        _ro(ws.cell(row=r, column=4, value=prev.get(k)), '#,##0.####')
        c = ws.cell(row=r, column=5, value=data.get(k)); _in(c, '#,##0.####' if k in NUM else None); r += 1

    # ---- Capital Markets ----
    ws = _sheet(wb, 'أسواق المال', note + ' المصدر: إدارة أسواق المال.')
    r = 3; r = _title(ws, r, 'الملكية')
    for k in ('own_full', 'own_use'):
        _key(ws, r, k); ws.cell(row=r, column=2, value=LABEL[k]).font = Font(name=FONT)
        _ro(ws.cell(row=r, column=4, value=prev.get(k))); _in(ws.cell(row=r, column=5, value=data.get(k)), '0.00'); r += 1
    r += 1; r = _title(ws, r, 'أكبر عشرة استثمارات (% من الأصول)')
    _hdr(ws, r, ['الاسم بالعربية', 'Name in English', f'{pql} %', f'{ql} %']); r += 1
    top = data.get('top10') or []; ptop = {x['ar']: x.get('pct') for x in prev.get('top10', [])}
    for i in range(max(10, len(top))):
        x = top[i] if i < len(top) else {'ar': '', 'en': '', 'pct': None}
        _key(ws, r, f'top10.{i}'); _in(ws.cell(row=r, column=2, value=x.get('ar'))); _in(ws.cell(row=r, column=3, value=x.get('en')))
        _ro(ws.cell(row=r, column=4, value=ptop.get(x.get('ar'))), '0.00'); _in(ws.cell(row=r, column=5, value=x.get('pct')), '0.00'); r += 1
    for g, a in enumerate(data.get('alloc') or []):
        r += 1; _key(ws, r, f'alloc.{g}'); _in(ws.cell(row=r, column=2, value=a.get('title_ar'))); _in(ws.cell(row=r, column=3, value=a.get('title_en')))
        ws.cell(row=r, column=4, value='← عنوان الرسم').font = Font(name=FONT, color='5B667C'); r += 1
        _hdr(ws, r, ['البند بالعربية', 'Item in English', f'{pql} %', f'{ql} %']); r += 1
        pal = {}
        for pa in prev.get('alloc', []):
            if pa.get('title_ar') == a.get('title_ar'): pal = {x['ar']: x.get('pct') for x in pa['items']}
        items = a.get('items') or []
        for i in range(len(items) + 2):
            x = items[i] if i < len(items) else {'ar': '', 'en': '', 'pct': None}
            _key(ws, r, f'alloc.{g}.{i}'); _in(ws.cell(row=r, column=2, value=x.get('ar'))); _in(ws.cell(row=r, column=3, value=x.get('en')))
            _ro(ws.cell(row=r, column=4, value=pal.get(x.get('ar'))), '0.00'); _in(ws.cell(row=r, column=5, value=x.get('pct')), '0.00'); r += 1
    per = [M.shift_dates(x, 'ar', M.prev_q(q), q).replace('*', '').strip() for x in (prev.get('periods_ar') or [])]
    r += 1; r = _title(ws, r, 'العوائد (%)')
    _hdr(ws, r, ['الفترة', f'الصندوق {pql}', f'الصندوق {ql}', f'المؤشر {pql}', f'المؤشر {ql}']); r += 1
    rf, rb = data.get('ret_fund') or [], data.get('ret_bench') or []
    for i, p in enumerate(per):
        _key(ws, r, f'ret.{i}'); ws.cell(row=r, column=2, value=p).font = Font(name=FONT)
        _ro(ws.cell(row=r, column=3, value=(prev.get('ret_fund') or [None] * 9)[i] if i < len(prev.get('ret_fund') or []) else None), '0.00')
        _in(ws.cell(row=r, column=4, value=rf[i] if i < len(rf) else None), '0.00')
        _ro(ws.cell(row=r, column=5, value=(prev.get('ret_bench') or [None] * 9)[i] if i < len(prev.get('ret_bench') or []) else None), '0.00')
        _in(ws.cell(row=r, column=6, value=rb[i] if i < len(rb) else None), '0.00'); r += 1
    r += 1; r = _title(ws, r, 'الأداء والمخاطر')
    _hdr(ws, r, ['المعيار'] + list(per)); r += 1
    risk = data.get('risk') or {}
    for k, name in zip(M.RISK, M.RISK_AR):
        if k not in (prev.get('risk') or {}): continue
        _key(ws, r, f'risk.{k}'); ws.cell(row=r, column=2, value=name).font = Font(name=FONT)
        vals = risk.get(k) or []
        for j in range(len(per)): _in(ws.cell(row=r, column=3 + j, value=vals[j] if j < len(vals) else None), '0.00')
        r += 1
    rat = data.get('rating') or {}
    if rat.get('ar'):
        r += 1; r = _title(ws, r, 'التصنيف الائتماني')
        _hdr(ws, r, ['بالعربية', 'In English']); r += 1
        for i, v in enumerate(rat.get('ar')):
            _key(ws, r, f'rating.{i}'); _in(ws.cell(row=r, column=2, value=v)); _in(ws.cell(row=r, column=3, value=(rat.get('en') or [''] * 99)[i] if i < len(rat.get('en') or []) else '')); r += 1
    r += 1; r = _title(ws, r, 'تعليق مدير الصندوق')
    for lang in ('ar', 'en'):
        k = f'commentary.{lang}'; _key(ws, r, k); ws.cell(row=r, column=2, value=LABEL[k]).font = Font(name=FONT, bold=True)
        c = ws.cell(row=r, column=3, value=(data.get('commentary') or {}).get(lang) or ''); _in(c)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=7); ws.row_dimensions[r].height = 220; r += 1
    ws.cell(row=r, column=3, value='سطر يبدأ بـ # عنوان، وسطر يبدأ بـ - بند في قائمة، وسطر فارغ بين الفقرات.').font = Font(name=FONT, size=9, color='5B667C')

    # ---- Tadawul ----
    ws = _sheet(wb, 'تداول', note + ' المصدر: تداول السعودية.')
    r = 3; _hdr(ws, r, ['البند', '', pql, ql]); r += 1
    if F['traded']:
        _key(ws, r, 'price'); ws.cell(row=r, column=2, value=LABEL['price']).font = Font(name=FONT)
        _ro(ws.cell(row=r, column=4, value=prev.get('price'))); _in(ws.cell(row=r, column=5, value=data.get('price')), '0.00##'); r += 1
    if F['pe']:
        _key(ws, r, 'pe'); ws.cell(row=r, column=2, value=LABEL['pe']).font = Font(name=FONT)
        _ro(ws.cell(row=r, column=4, value=prev.get('pe'))); _in(ws.cell(row=r, column=5, value=data.get('pe'))); r += 1
    r += 1; r = _title(ws, r, 'نقاط رسم الأداء (نهاية كل شهر)')
    cols = ['التاريخ (YYYY-MM-DD)'] + (['سعر الوحدة'] if F['perf'] == 'price' else ['أداء الصندوق %', 'أداء المؤشر %'])
    _hdr(ws, r, cols); r += 1
    for i, p in enumerate(data.get('perf_points') or []):
        _key(ws, r, f'perf.{i}'); _in(ws.cell(row=r, column=2, value=p.get('date')))
        if F['perf'] == 'price': _in(ws.cell(row=r, column=3, value=p.get('value')), '0.00##')
        else: _in(ws.cell(row=r, column=3, value=p.get('fund')), '0.00'); _in(ws.cell(row=r, column=4, value=p.get('bench')), '0.00')
        r += 1
    meta = wb.create_sheet('_meta'); meta['A1'] = 'akc-quarterly'; meta['A2'] = fund; meta['A3'] = q; meta.sheet_state = 'hidden'
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


class WrongFile(Exception):
    pass


def _v(x):
    if isinstance(x, datetime.datetime): return x.date().isoformat()
    if isinstance(x, datetime.date): return x.isoformat()
    if isinstance(x, str): x = x.strip(); return x or None
    return x


def _num(x):
    x = _v(x)
    if x is None: return None
    return float(x) if isinstance(x, (int, float)) else M.to_float(x)


def parse(blob, fund, q, data):
    """Returns (merged data, changes, problems). Empty cells leave the current value as it is."""
    wb = load_workbook(io.BytesIO(blob), data_only=True)
    probs = []
    if '_meta' in wb.sheetnames:
        m = wb['_meta']
        if m['A2'].value and (m['A2'].value != fund or m['A3'].value != q):
            F = M.FUNDS.get(m['A2'].value, {})
            raise WrongFile(f'هذا الملف معدّ لـ{F.get("ar", m["A2"].value)} · {M.qlabel(m["A3"].value, "ar") if M.re.match(r"q[1-4]-[0-9]{4}$", str(m["A3"].value)) else m["A3"].value}، لا لهذا البيان.')
    d = copy.deepcopy(data or {}); ch = []

    def put(label, before, after):
        if after is None or after == before: return False
        ch.append({'label': label, 'before': before, 'after': after}); return True

    top, alloc = {}, {}
    for ws in wb.worksheets:
        if ws.title == '_meta': continue
        for row in ws.iter_rows(min_row=1):
            k = row[0].value
            if not isinstance(k, str) or not k: continue
            cells = [_v(c.value) for c in row[1:8]] + [None] * 8
            if k in LABEL or k in NUM:
                val = cells[3] if not k.startswith('commentary') else cells[1]
                if k.startswith('commentary.'):
                    lang = k.split('.')[1]; cur = (d.get('commentary') or {}).get(lang)
                    if val is not None and put(LABEL[k], cur, val): d.setdefault('commentary', {})[lang] = val
                    continue
                if k in NUM:
                    n = _num(val)
                    if val is not None and n is None: probs.append(f'{LABEL.get(k, k)}: «{val}» ليس رقمًا.'); continue
                    if put(LABEL.get(k, k), d.get(k), n): d[k] = n
                else:
                    if put(LABEL.get(k, k), d.get(k), val): d[k] = val
            elif k.startswith('top10.'):
                top[int(k.split('.')[1])] = (cells[0], cells[1], _num(cells[3]))
            elif k.startswith('alloc.'):
                p = k.split('.')
                if len(p) == 2: alloc.setdefault(int(p[1]), {'title': (cells[0], cells[1]), 'items': {}})['title'] = (cells[0], cells[1])
                else: alloc.setdefault(int(p[1]), {'title': None, 'items': {}})['items'][int(p[2])] = (cells[0], cells[1], _num(cells[3]))
            elif k.startswith('ret.'):
                i = int(k.split('.')[1]); per = (d.get('ret_fund') or [])
                for key, col, lab in (('ret_fund', 2, 'عائد الصندوق'), ('ret_bench', 4, 'عائد المؤشر')):
                    lst = d.setdefault(key, []); lst += [None] * (i + 1 - len(lst)); n = _num(cells[col])
                    if put(f'{lab} · {cells[0]}', lst[i], n): lst[i] = n
            elif k.startswith('risk.'):
                rk = k.split('.')[1]; lst = d.setdefault('risk', {}).setdefault(rk, [])
                name = dict(zip(M.RISK, M.RISK_AR)).get(rk, rk)
                for j in range(6):
                    n = _num(cells[1 + j])
                    if n is None: continue
                    lst += [None] * (j + 1 - len(lst))
                    if put(f'{name} · العمود {j + 1}', lst[j], n): lst[j] = n
            elif k.startswith('rating.'):
                i = int(k.split('.')[1]); rat = d.setdefault('rating', {'ar': [], 'en': []})
                for lang, col in (('ar', 0), ('en', 1)):
                    lst = rat.setdefault(lang, []); lst += [''] * (i + 1 - len(lst))
                    if put(f'التصنيف ' + ('بالعربية' if lang == 'ar' else 'بالإنجليزية') + f' {i + 1}', lst[i], cells[col]): lst[i] = cells[col]
            elif k.startswith('perf.'):
                i = int(k.split('.')[1]); pts = d.setdefault('perf_points', [])
                while len(pts) <= i: pts.append({'date': None, 'value': None, 'fund': None, 'bench': None})
                if put(f'نقطة الأداء {i + 1}: التاريخ', pts[i].get('date'), cells[0]): pts[i]['date'] = cells[0]
                cols = (('value', 1),) if M.FUNDS[fund]['perf'] == 'price' else (('fund', 1), ('bench', 2))
                for key, col in cols:
                    n = _num(cells[col])
                    if put(f'نقطة الأداء {i + 1}: ' + {'value': 'سعر الوحدة', 'fund': 'أداء الصندوق', 'bench': 'أداء المؤشر'}[key], pts[i].get(key), n): pts[i][key] = n
    if top:
        new = []
        for i in sorted(top):
            ar, en, pct = top[i]
            if ar or en or pct is not None: new.append({'ar': ar or '', 'en': en or '', 'pct': pct})
        old = d.get('top10') or []
        if [(x.get('ar'), x.get('en'), x.get('pct')) for x in old] != [(x['ar'], x['en'], x['pct']) for x in new]:
            for i, x in enumerate(new):
                o = old[i] if i < len(old) else {}
                put(f'أكبر عشرة استثمارات {i + 1}: {x["ar"]}', f'{o.get("ar", "")} {o.get("pct") if o.get("pct") is not None else ""}'.strip(), f'{x["ar"]} {x["pct"] if x["pct"] is not None else ""}'.strip())
            d['top10'] = new
    for g, a in sorted(alloc.items()):
        cur = (d.get('alloc') or [])
        if g >= len(cur): continue
        if a['title'] and a['title'][0]:
            if put('عنوان رسم التوزيع', cur[g].get('title_ar'), a['title'][0]): cur[g]['title_ar'] = a['title'][0]
            if a['title'][1] and put('Allocation chart title', cur[g].get('title_en'), a['title'][1]): cur[g]['title_en'] = a['title'][1]
        new = [{'ar': ar or '', 'en': en or '', 'pct': pct} for i, (ar, en, pct) in sorted(a['items'].items()) if ar or en or pct is not None]
        old = cur[g].get('items') or []
        if [(x.get('ar'), x.get('pct')) for x in old] != [(x['ar'], x['pct']) for x in new]:
            for i, x in enumerate(new):
                o = old[i] if i < len(old) else {}
                put(f'{cur[g].get("title_ar", "التوزيع")}: {x["ar"]}', o.get('pct'), x['pct'])
            cur[g]['items'] = new
    return d, ch, probs
