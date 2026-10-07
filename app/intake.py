"""Any file in, proposed field values out.

`read(name, blob)` turns PDF, Word, Excel/CSV, images, e-mail (.eml/.msg) and ZIP files into text and page images.
`propose(fund, q, data, prev, files)` asks Claude to map what the files say onto the statement's fields and returns
proposals, each with the file, the place in it and the words it came from. Nothing is written: the person accepts
proposals in the editor and saves.
"""
import io, os, re, csv, json, zipfile, email, email.policy, mimetypes
import model as M, ai, xl

MAX_TEXT = 90000          # characters of text sent per request
MAX_IMAGES = 12           # page images / pictures per request


def _pdf(name, blob, out):
    import pymupdf
    d = pymupdf.open(stream=blob, filetype='pdf')
    for i, pg in enumerate(d):
        t = pg.get_text('text').strip()
        if len(t) >= 60:
            out['text'].append(f'### {name} · page {i + 1}\n{t}')
        if len(t) < 60 or (pg.get_images() and len(t) < 400):
            if len(out['images']) < MAX_IMAGES:
                out['images'].append((f'{name} · page {i + 1}', pg.get_pixmap(dpi=110).tobytes('png')))


def _docx(name, blob, out):
    import docx
    d = docx.Document(io.BytesIO(blob)); lines = []
    for p in d.paragraphs:
        if p.text.strip(): lines.append(p.text.strip())
    for ti, t in enumerate(d.tables):
        lines.append(f'[table {ti + 1}]')
        for r in t.rows: lines.append('\t'.join(c.text.strip() for c in r.cells))
    out['text'].append(f'### {name}\n' + '\n'.join(lines))


def _xlsx(name, blob, out):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(blob), data_only=True, read_only=True)
    for ws in wb.worksheets:
        if ws.title == '_meta': continue
        rows = []
        for r in ws.iter_rows(values_only=True):
            if any(v not in (None, '') for v in r):
                rows.append('\t'.join('' if v is None else str(v) for v in r))
            if len(rows) > 400: break
        out['text'].append(f'### {name} · sheet «{ws.title}» (cells, tab-separated, one row per line)\n' + '\n'.join(rows))


def _eml(name, blob, out, depth):
    msg = email.message_from_bytes(blob, policy=email.policy.default)
    head = f"From: {msg.get('from', '')}\nTo: {msg.get('to', '')}\nDate: {msg.get('date', '')}\nSubject: {msg.get('subject', '')}"
    body = msg.get_body(preferencelist=('plain', 'html'))
    txt = body.get_content() if body else ''
    if body is not None and body.get_content_type() == 'text/html': txt = re.sub(r'<[^>]+>', ' ', txt)
    out['text'].append(f'### {name} (e-mail)\n{head}\n\n{txt.strip()[:20000]}')
    for part in msg.iter_attachments():
        fn = part.get_filename() or 'attachment'
        _any(f'{name} › {fn}', part.get_payload(decode=True) or b'', out, depth + 1)


def _msg(name, blob, out, depth):
    try:
        import extract_msg
    except ImportError:
        out['skipped'].append(f'{name}: ملفات Outlook ‎.msg غير مدعومة على الخادم؛ احفظ الرسالة بصيغة ‎.eml أو أرسل مرفقاتها.'); return
    m = extract_msg.Message(io.BytesIO(blob))
    out['text'].append(f'### {name} (e-mail)\nFrom: {m.sender}\nDate: {m.date}\nSubject: {m.subject}\n\n{(m.body or "")[:20000]}')
    for a in m.attachments:
        _any(f'{name} › {a.longFilename or a.shortFilename}', a.data or b'', out, depth + 1)


def _any(name, blob, out, depth=0):
    if depth > 3 or not blob: return
    ext = os.path.splitext(name.lower())[1]
    try:
        if ext == '.pdf' or blob[:4] == b'%PDF': _pdf(name, blob, out)
        elif ext in ('.docx',): _docx(name, blob, out)
        elif ext in ('.xlsx', '.xlsm'): _xlsx(name, blob, out)
        elif ext in ('.csv', '.txt', '.tsv', '.md'):
            out['text'].append(f'### {name}\n' + blob.decode('utf-8-sig', 'replace')[:40000])
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
            if len(out['images']) < MAX_IMAGES:
                out['images'].append((name, blob, mimetypes.guess_type(name)[0] or 'image/png'))
        elif ext == '.eml': _eml(name, blob, out, depth)
        elif ext == '.msg': _msg(name, blob, out, depth)
        elif ext == '.zip':
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                for n in z.namelist()[:40]:
                    if not n.endswith('/'): _any(f'{name} › {n}', z.read(n), out, depth + 1)
        else:
            out['skipped'].append(f'{name}: صيغة غير مدعومة ({ext or "بلا امتداد"}).')
    except Exception as e:
        out['skipped'].append(f'{name}: تعذّرت قراءته ({str(e)[:120]}).')


def read(files):
    """files: [(name, bytes)] → {'text': [...], 'images': [(label, bytes[, media])], 'skipped': [...], 'templates': [(name, bytes)]}"""
    out = {'text': [], 'images': [], 'skipped': [], 'templates': []}
    for name, blob in files:
        if name.lower().endswith(('.xlsx', '.xlsm')):
            try:
                from openpyxl import load_workbook
                if '_meta' in load_workbook(io.BytesIO(blob), read_only=True).sheetnames:
                    out['templates'].append((name, blob)); continue
            except Exception:
                pass
        _any(name, blob, out)
    return out


# ---------- the statement's fields, described for the model ----------
def fields(fund, data, prev):
    F = M.FUNDS[fund]; f = []
    for k, ar, en in xl.FACO:
        if k == 'wad_days' and not F['wad']: continue
        f.append({'field': k, 'label': f'{ar} / {en}', 'type': 'date' if k == 'valuation_date' else 'number', 'current': data.get(k), 'previous_quarter': prev.get(k)})
    if F['traded']: f.append({'field': 'price', 'label': 'سعر الوحدة في السوق نهاية الربع / market price at quarter end (SAR)', 'type': 'number', 'current': data.get('price'), 'previous_quarter': prev.get('price')})
    if F['pe']: f.append({'field': 'pe', 'label': 'مكرر الربحية / P/E', 'type': 'text', 'current': data.get('pe'), 'previous_quarter': prev.get('pe')})
    for k, lab in (('own_full', 'ملكية تامة % / full ownership %'), ('own_use', 'حق منفعة % / usufruct %')):
        f.append({'field': k, 'label': lab, 'type': 'number', 'current': data.get(k)})
    for i, x in enumerate(data.get('top10') or []):
        f.append({'field': f'top10.{i}.pct', 'label': f'أكبر عشرة استثمارات: {x.get("ar")} / {x.get("en")} (% of assets)', 'type': 'number', 'current': x.get('pct')})
    for g, a in enumerate(data.get('alloc') or []):
        for i, x in enumerate(a.get('items') or []):
            f.append({'field': f'alloc.{g}.items.{i}.pct', 'label': f'{a.get("title_ar")} / {a.get("title_en")}: {x.get("ar")} / {x.get("en")} (%)', 'type': 'number', 'current': x.get('pct')})
    for i, p in enumerate(prev.get('periods_en') or prev.get('periods_ar') or []):
        f.append({'field': f'ret_fund.{i}', 'label': f'Fund return % · {p}', 'type': 'number', 'current': (data.get('ret_fund') or [None] * 9)[i] if i < len(data.get('ret_fund') or []) else None})
        f.append({'field': f'ret_bench.{i}', 'label': f'Benchmark return % · {p}', 'type': 'number', 'current': (data.get('ret_bench') or [None] * 9)[i] if i < len(data.get('ret_bench') or []) else None})
        for k, name in zip(M.RISK, ('standard deviation', 'Sharpe ratio', 'tracking error', 'beta', 'alpha', 'information ratio')):
            if k in (prev.get('risk') or {}): f.append({'field': f'risk.{k}.{i}', 'label': f'{name} · {p}', 'type': 'number', 'current': ((data.get('risk') or {}).get(k) or [None] * 9)[i] if i < len((data.get('risk') or {}).get(k) or []) else None})
    for i, p in enumerate(data.get('perf_points') or []):
        if F['perf'] == 'price': f.append({'field': f'perf_points.{i}.value', 'label': f'month-end unit price on {p.get("date")}', 'type': 'number', 'current': p.get('value')})
        else:
            f.append({'field': f'perf_points.{i}.fund', 'label': f'cumulative fund return % on {p.get("date")}', 'type': 'number', 'current': p.get('fund')})
            f.append({'field': f'perf_points.{i}.bench', 'label': f'cumulative benchmark return % on {p.get("date")}', 'type': 'number', 'current': p.get('bench')})
    f.append({'field': 'commentary.ar', 'label': 'تعليق مدير الصندوق بالعربية (النص كاملًا كما ورد)', 'type': 'text', 'current': (data.get('commentary') or {}).get('ar')})
    f.append({'field': 'commentary.en', 'label': 'Fund manager commentary in English (full text as given)', 'type': 'text', 'current': (data.get('commentary') or {}).get('en')})
    return f


TOOL = {'name': 'propose_values', 'description': 'Report the statement field values found in the files.',
        'input_schema': {'type': 'object', 'properties': {
            'proposals': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'field': {'type': 'string', 'description': 'exact field id from the list'},
                'value': {'type': ['number', 'string'], 'description': 'number without separators or %, date as YYYY-MM-DD, text as written'},
                'file': {'type': 'string'}, 'location': {'type': 'string', 'description': 'page, sheet and cell, or table and row'},
                'quote': {'type': 'string', 'description': 'the exact words or cell content the value was read from'},
                'confidence': {'type': 'number', 'description': '0 to 1'},
                'note': {'type': 'string', 'description': 'unit conversion, rounding, or a doubt; empty if none'}},
                'required': ['field', 'value', 'file', 'location', 'quote', 'confidence']}},
            'conflicts': {'type': 'array', 'items': {'type': 'object', 'properties': {'field': {'type': 'string'}, 'values': {'type': 'array', 'items': {'type': 'string'}}, 'where': {'type': 'string'}}}},
            'not_found': {'type': 'array', 'items': {'type': 'string'}, 'description': 'field ids the files do not give'},
            'summary': {'type': 'string', 'description': 'one or two sentences about what the files contain, in the language named in the instructions'}},
            'required': ['proposals', 'summary']}}

SYSTEM = """You read source files sent to Alkhabeer Capital for a fund's quarterly statement (CMA Annex 4) and map their figures onto the statement's fields.
Rules:
- Propose a value only when the files state it for the right fund and the right quarter end. Never compute, estimate or infer a figure that is not written, except converting units (e.g. thousands to SAR, 0.0425 to 4.25 %) — say so in note.
- Use the exact field ids given. Percent fields take the number of percent (4.25 for 4.25 %). Dates are YYYY-MM-DD.
- Quote the words or cell you read from, and say where (page, sheet and cell, table and row).
- If two files or two places give different values for one field, list it in conflicts and do not propose it.
- Commentary fields take the full text exactly as written in that language; never translate one language into the other.
- Top-ten and allocation items are matched by name; if the names in the files differ from the current names, mention it in note.
Report through the propose_values tool only."""


def _coerce(f, v):
    if f['type'] == 'number':
        if isinstance(v, (int, float)): return float(v)
        n = M.to_float(str(v)); return n
    if f['type'] == 'date':
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(v)); return m.group(0) if m else None
    return str(v)


def propose(fund, q, data, prev, content, actor='', ui='ar'):
    F = M.FUNDS[fund]; fl = fields(fund, data, prev); by = {f['field']: f for f in fl}
    ql = M.qlabel(q, 'en'); end = M.qend(*M.qparse(q)).isoformat()
    text = '\n\n'.join(content['text'])
    if len(text) > MAX_TEXT: text = text[:MAX_TEXT] + '\n[… truncated]'
    blocks = [{'type': 'text', 'text': f'Fund: {F["en"]} ({F["ar"]}). Statement: {ql}, quarter end {end}.\n\nFields (id, label, type, current value, previous quarter):\n'
               + json.dumps(fl, ensure_ascii=False) + '\n\nFiles:\n' + (text or '(no text — see the page images)')}]
    for im in content['images'][:MAX_IMAGES]:
        blocks.append({'type': 'text', 'text': f'Image: {im[0]}'}); blocks.append(ai.image_block(im[1], im[2] if len(im) > 2 else 'image/png'))
    r = ai.call([{'role': 'user', 'content': blocks}], system=SYSTEM + ('\nWrite the summary and notes in ' + ('Arabic.' if ui == 'ar' else 'English.')), tools=[TOOL], tool_choice={'type': 'tool', 'name': 'propose_values'},
                max_tokens=8000, actor=actor, feature='intake', obj=f'{fund}:{q}')
    out = ai.tool_input(r, 'propose_values') or {'proposals': [], 'summary': ''}
    props, rejected = [], []
    for p in out.get('proposals') or []:
        f = by.get(p.get('field'))
        if not f: rejected.append(p.get('field')); continue
        v = _coerce(f, p.get('value'))
        if v is None: rejected.append(p.get('field')); continue
        if f['type'] == 'number' and isinstance(f['current'], (int, float)) and abs(f['current'] - v) < 1e-9: continue
        if f['type'] != 'number' and (f['current'] or '') == v: continue
        props.append({'field': f['field'], 'label': f['label'], 'current': f['current'], 'value': v, 'previous': f.get('previous_quarter'),
                      'file': p.get('file', ''), 'location': p.get('location', ''), 'quote': (p.get('quote') or '')[:400],
                      'confidence': max(0.0, min(1.0, float(p.get('confidence') or 0))), 'note': p.get('note') or ''})
    props.sort(key=lambda x: -x['confidence'])
    return {'proposals': props, 'conflicts': out.get('conflicts') or [], 'not_found': out.get('not_found') or [],
            'summary': out.get('summary') or '', 'rejected': rejected}
