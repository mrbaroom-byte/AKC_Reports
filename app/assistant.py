"""Internal assistant: answers questions about every statement on the platform and edits the work in progress.

It works only through the tools below, with the permissions of the person asking:
- anyone signed in reads statements, published records, AR/EN differences and history;
- it edits a quarter's data only while that statement is open for entry (new, in progress, draft ready, returned);
  every edit is saved with an undo point, logged in the audit trail as made by the assistant for that person;
- only the approver can have it prepare a correction draft of a published statement; approving stays a human act;
- it never submits, approves, returns, publishes, deletes, or touches users, backups or settings.
"""
import json, sqlite3, datetime, copy, re
import model as M, store, ai, audit as A, records as R

EDITABLE = ('new', 'draft', 'generated', 'returned')
MAX_STEPS = 8


def _c():
    c = sqlite3.connect(store.DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute('create table if not exists assistant_undo(id integer primary key autoincrement, at text, actor text, fund text, q text, data text, used integer default 0)')
    return c


def _q(s):
    s = (s or '').strip().lower().replace(' ', '')
    m = re.match(r'^q([1-4])-?(\d{4})$', s)
    return f'q{m.group(1)}-{m.group(2)}' if m else None


TOOLS = [
    {'name': 'list_statements', 'description': 'Statuses of every fund for a quarter (default: the quarter now due), plus how many published statements exist per fund.',
     'input_schema': {'type': 'object', 'properties': {'quarter': {'type': 'string', 'description': 'e.g. q3-2026'}}}},
    {'name': 'get_statement', 'description': 'The data entered for one fund and quarter (open or final), its status, validation results, and last quarter’s values.',
     'input_schema': {'type': 'object', 'properties': {'fund': {'type': 'string', 'enum': list(M.FUNDS)}, 'quarter': {'type': 'string'}}, 'required': ['fund', 'quarter']}},
    {'name': 'get_published', 'description': 'Text and tables of a published statement in one language, optionally only sections whose title contains a phrase. Blocks carry ids usable in prepare_correction.',
     'input_schema': {'type': 'object', 'properties': {'fund': {'type': 'string', 'enum': list(M.FUNDS)}, 'quarter': {'type': 'string'}, 'lang': {'type': 'string', 'enum': ['ar', 'en']},
                                                       'section': {'type': 'string'}}, 'required': ['fund', 'quarter', 'lang']}},
    {'name': 'get_differences', 'description': 'Figures that differ between the Arabic and English versions of a published statement, and the findings verified against the original PDFs.',
     'input_schema': {'type': 'object', 'properties': {'fund': {'type': 'string', 'enum': list(M.FUNDS)}, 'quarter': {'type': 'string'}}, 'required': ['fund', 'quarter']}},
    {'name': 'get_history', 'description': 'Recent activity on a statement (who saved, issued, submitted, returned, approved, corrected).',
     'input_schema': {'type': 'object', 'properties': {'fund': {'type': 'string', 'enum': list(M.FUNDS)}, 'quarter': {'type': 'string'}}, 'required': ['fund', 'quarter']}},
    {'name': 'update_statement', 'description': 'Change fields of a statement that is open for entry. Field ids as in get_statement data (e.g. nav_unit, top10.3.pct, alloc.0.items.2.pct, ret_fund.0, risk.sd.1, commentary.en). Saves immediately with an undo point.',
     'input_schema': {'type': 'object', 'properties': {'fund': {'type': 'string', 'enum': list(M.FUNDS)}, 'quarter': {'type': 'string'},
                                                       'changes': {'type': 'array', 'items': {'type': 'object', 'properties': {'field': {'type': 'string'}, 'value': {}}, 'required': ['field', 'value']}},
                                                       'reason': {'type': 'string'}}, 'required': ['fund', 'quarter', 'changes', 'reason']}},
    {'name': 'prepare_correction', 'description': 'Approver only: put value changes into the correction draft of a published statement (not approved, nothing published). Each edit names a block id and a cell: for kv/table rows use "rows.<row>.<col>", for text "text", for chart values "series.<i>.value".',
     'input_schema': {'type': 'object', 'properties': {'fund': {'type': 'string', 'enum': list(M.FUNDS)}, 'quarter': {'type': 'string'}, 'lang': {'type': 'string', 'enum': ['ar', 'en']},
                                                       'edits': {'type': 'array', 'items': {'type': 'object', 'properties': {'block': {'type': 'integer'}, 'path': {'type': 'string'}, 'value': {}}, 'required': ['block', 'path', 'value']}},
                                                       'reason': {'type': 'string'}}, 'required': ['fund', 'quarter', 'lang', 'edits', 'reason']}},
]


def _get(o, path):
    for k in path.split('.'):
        o = o[int(k)] if isinstance(o, list) else o[k]
    return o


def _set(o, path, v):
    ks = path.split('.'); last = ks.pop()
    for k in ks: o = o[int(k)] if isinstance(o, list) else o.setdefault(k, {})
    if isinstance(o, list): o[int(last)] = v
    else: o[last] = v


class Session:
    def __init__(self, me, ctx, lang, page=None):
        self.me, self.ctx, self.lang, self.page = me, ctx, lang, page or {}
        self.actions = []

    # ---- tools ----
    def t_list_statements(self, quarter=None):
        q = _q(quarter) or self.ctx['current_q']()
        out = {'quarter': q, 'funds': []}
        recs = store.all_records()
        for f, F in M.FUNDS.items():
            s = store.get(f, q) or {}
            out['funds'].append({'fund': f, 'name_ar': F['ar'], 'name_en': F['en'], 'status': s.get('status', 'new'), 'updated': s.get('updated'),
                                 'published_count': sum(1 for r in recs if r['fund'] == f and r['status'] in ('published', 'corrected'))})
        return out

    def t_get_statement(self, fund, quarter):
        q = _q(quarter)
        if fund not in M.FUNDS or not q: return {'error': 'unknown fund or quarter'}
        s = store.get(fund, q)
        if not s: return {'error': 'no statement for this quarter yet'}
        prev, pq, _ = self.ctx['prev_values'](fund, q)
        v = M.validate(fund, s['data'], prev, q) if prev and s['status'] not in ('published', 'corrected') else []
        pv = {k: prev.get(k) for k in ('nav_unit', 'fund_size', 'units', 'price', 'ter_amount', 'dist_total', 'ret_fund', 'ret_bench', 'top10')} if prev else None
        return {'fund': fund, 'quarter': q, 'status': s['status'], 'data': s['data'], 'validation': v, 'previous_quarter': pq, 'previous_values': pv,
                'notes': (s.get('notes') or '')[-3000:]}

    def t_get_published(self, fund, quarter, lang, section=None):
        q = _q(quarter); st = R.load(fund, q, lang) if q else None
        if not st: return {'error': 'no published statement for this fund and quarter'}
        out, cur, keep = [], '', not section
        for i, b in enumerate(st['blocks']):
            if b['t'] == 'h2':
                cur = b.get('text', ''); keep = not section or section.strip().lower() in cur.lower()
            if keep:
                x = {k: v for k, v in b.items() if k in ('t', 'text', 'rows', 'head', 'items', 'title', 'series', 'caption')}
                x['id'] = i; out.append(x)
        txt = json.dumps(out, ensure_ascii=False)
        return {'fund': fund, 'quarter': q, 'lang': lang, 'blocks': out if len(txt) < 60000 else out[:120], 'truncated': len(txt) >= 60000}

    def t_get_differences(self, fund, quarter):
        q = _q(quarter)
        return {'differences': store.get_conflicts(fund, q) or [], 'verified': [v for v in self.ctx['verified'] if v['fund'] == fund and v['q'] == q]}

    def t_get_history(self, fund, quarter):
        q = _q(quarter); out = {'events': store.events(fund, q, 40)}
        if self.me['role'] == 'admin': out['audit'] = A.query(obj=f'{fund}:{q}', limit=30)[1]
        return out

    def _label(self, fund, q):
        return f"{M.FUNDS[fund][self.lang]} · {M.qlabel(q, self.lang)}"

    def t_update_statement(self, fund, quarter, changes, reason):
        q = _q(quarter)
        if fund not in M.FUNDS or not q: return {'error': 'unknown fund or quarter'}
        s = store.get(fund, q)
        if not s: return {'error': 'open the statement page once first so it exists'}
        if s['status'] not in EDITABLE: return {'error': f'statement is {s["status"]}; it cannot be edited now (only a person can return it for changes)'}
        before = copy.deepcopy(s['data']); d = copy.deepcopy(s['data']); done, bad = [], []
        for ch in changes or []:
            f = str(ch.get('field', '')); v = ch.get('value')
            try:
                old = _get(d, f)
            except (KeyError, IndexError, ValueError, TypeError):
                bad.append(f); continue
            if isinstance(old, (int, float)) or old is None and not f.startswith(('commentary', 'rating', 'dist_entitle')) and not f.endswith(('.ar', '.en', '.date')):
                n = v if isinstance(v, (int, float)) else M.to_float(str(v))
                if n is None and v not in (None, ''): bad.append(f); continue
                v = n
            _set(d, f, v); done.append({'field': f, 'before': old, 'after': v})
        if not done: return {'error': 'nothing changed', 'invalid_fields': bad}
        d = self.ctx['clean'](d)
        if not M.FUNDS[fund]['traded']: d['price'] = d.get('nav_unit')
        with _c() as c:
            uid = c.execute('insert into assistant_undo(at,actor,fund,q,data) values(?,?,?,?,?)',
                            (datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), self.me['user'], fund, q, json.dumps(before, ensure_ascii=False))).lastrowid
        store.put(fund, q, data=d, status='draft')
        store.event(fund, q, f"{self.me['name']}: تعديل عبر المساعد ({len(done)} تغيير) — {reason}")
        A.log(self.req, 'assistant.edit', f'{fund}:{q}', via='assistant', reason=reason, changes=A.diff(before, d), undo=uid)
        prev, _, _ = self.ctx['prev_values'](fund, q)
        self.actions.append({'kind': 'edit', 'fund': fund, 'q': q, 'n': len(done), 'undo': uid, 'label': self._label(fund, q)})
        return {'saved': done, 'invalid_fields': bad, 'undo_id': uid, 'validation': M.validate(fund, d, prev, q) if prev else []}

    def t_prepare_correction(self, fund, quarter, lang, edits, reason):
        if self.me['role'] != 'admin': return {'error': 'only the approver can prepare corrections of published statements'}
        q = _q(quarter); s = store.get(fund, q) if q else None
        if not s or s['status'] not in ('published', 'corrected'): return {'error': 'not a published statement'}
        work = {l: (R.load(fund, q, l, True) or R.load(fund, q, l)) for l in ('ar', 'en')}
        st = copy.deepcopy(work[lang]); done, bad = [], []
        for e in edits or []:
            try:
                b = st['blocks'][int(e['block'])]; old = _get(b, e['path'])
                v = e['value']
                if isinstance(old, (int, float)): v = float(v) if isinstance(v, (int, float)) else M.to_float(str(v))
                _set(b, e['path'], v); done.append({'block': e['block'], 'path': e['path'], 'before': old, 'after': v})
            except Exception:
                bad.append(e)
        if not done: return {'error': 'nothing changed', 'invalid': bad}
        work[lang] = st
        if not R.same_shape(R.load(fund, q, lang), st): return {'error': 'a correction changes values only'}
        for l in ('ar', 'en'):
            json.dump(work[l], open(store.draft_struct_path(fund, q, l), 'w', encoding='utf-8'), ensure_ascii=False)
        store.event(fund, q, f"{self.me['name']}: تعديل مسودة التصحيح عبر المساعد ({len(done)} تغيير) — {reason}")
        A.log(self.req, 'assistant.correction_draft', f'{fund}:{q}', via='assistant', reason=reason, lang=lang, edits=done)
        self.actions.append({'kind': 'correction', 'fund': fund, 'q': q, 'n': len(done), 'label': self._label(fund, q)})
        return {'saved_to_correction_draft': done, 'invalid': bad, 'next': 'the approver previews and approves the correction on the statement page'}

    # ---- loop ----
    def system(self):
        role = 'approver (admin)' if self.me['role'] == 'admin' else 'data entry'
        pg = self.page
        where = f"The user is on the page of {pg.get('fund')} {pg.get('q')}." if pg.get('fund') else 'The user is on an overview page.'
        return f"""You are the internal assistant of Alkhabeer Capital's quarterly statements platform for its capital-markets funds ({', '.join(f'{k}: {v["en"]}' for k, v in M.FUNDS.items())}).
Today is {datetime.date.today().isoformat()}; the quarter now due is {self.ctx['current_q']()}. The user is {self.me['name']} ({role}). {where}
Answer in {'Arabic (formal Modern Standard Arabic)' if self.lang == 'ar' else 'English'}; be short and specific; give figures with their source (statement, quarter, section).
Use the tools to read before answering; never guess a figure. Statements are CMA quarterly statements (Annex 4) issued in Arabic and English.
Edits: only when the user asks for a change. Before update_statement, be sure of the field and value; after it, say exactly what changed and that it can be undone. You cannot submit, approve, return, publish or delete anything, and you do not change users, backups or settings — say so if asked.
Each language is its own source: do not translate a published statement's content unless the user explicitly asks for a translation suggestion."""

    def run(self, history, req):
        self.req = req
        msgs = [m for m in history if m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str) and m['content'].strip()][-16:]
        tools = TOOLS if self.me['role'] == 'admin' else [t for t in TOOLS if t['name'] != 'prepare_correction']
        used = []
        for step in range(MAX_STEPS):
            r = ai.call(msgs, system=self.system(), tools=tools, max_tokens=3000, actor=self.me['user'], feature='assistant',
                        obj=f"{self.page.get('fund', '')}:{self.page.get('q', '')}".strip(':'))
            blocks = r.get('content', [])
            calls = [b for b in blocks if b.get('type') == 'tool_use']
            if not calls:
                return {'text': ai.text_of(r), 'actions': self.actions, 'tools': used}
            msgs.append({'role': 'assistant', 'content': blocks}); results = []
            for b in calls:
                fn = getattr(self, 't_' + b['name'], None); used.append(b['name'])
                try: out = fn(**(b.get('input') or {})) if fn else {'error': 'unknown tool'}
                except TypeError as e: out = {'error': f'bad arguments: {e}'}
                except Exception as e: out = {'error': str(e)[:300]}
                results.append({'type': 'tool_result', 'tool_use_id': b['id'], 'content': json.dumps(out, ensure_ascii=False, default=str)[:60000]})
            msgs.append({'role': 'user', 'content': results})
        return {'text': 'توقفت قبل إكمال الطلب لكثرة الخطوات. جرّب طلبًا أصغر.' if self.lang == 'ar' else 'I stopped before finishing: too many steps. Try a smaller request.',
                'actions': self.actions, 'tools': used}


def undo(uid, me, req):
    with _c() as c:
        r = c.execute('select * from assistant_undo where id=?', (uid,)).fetchone()
        if not r: return {'error': 'not found'}
        if r['used']: return {'error': 'already undone'}
        s = store.get(r['fund'], r['q'])
        if not s or s['status'] not in EDITABLE: return {'error': 'statement is no longer open for entry'}
        if me['role'] != 'admin' and r['actor'] != me['user']: return {'error': 'only the person who asked, or the approver, can undo'}
        before = s['data']; data = json.loads(r['data'])
        store.put(r['fund'], r['q'], data=data, status='draft')
        c.execute('update assistant_undo set used=1 where id=?', (uid,))
    store.event(r['fund'], r['q'], f"{me['name']}: تراجع عن تعديل المساعد")
    A.log(req, 'assistant.undo', f"{r['fund']}:{r['q']}", undo=uid, changes=A.diff(before, data))
    return {'ok': True, 'fund': r['fund'], 'q': r['q']}
