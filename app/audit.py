"""Audit trail and request log.

`audit` holds one row per meaningful action (who, when, from where, what, on which statement, the outcome, and the
details — for data changes the field-level before/after). Rows are hash-chained: each row's hash covers the previous
row's hash and its own content, so a changed or deleted row breaks the chain and `verify()` reports where.
`access` holds one row per HTTP request (method, path, status, duration, user) for traffic tracking; it is kept
180 days. The audit trail is never pruned.
"""
import os, json, sqlite3, hashlib, threading, datetime, csv, io, uuid
import store

_lock = threading.Lock()
GENESIS = '0' * 64


def _c():
    c = sqlite3.connect(store.DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute('''create table if not exists audit(id integer primary key autoincrement, at text, actor text, role text, ip text, ua text,
                 action text, object text, outcome text, details text, rid text, prev text, hash text)''')
    c.execute('create index if not exists audit_at on audit(at)')
    c.execute('create index if not exists audit_obj on audit(object)')
    c.execute('''create table if not exists access(id integer primary key autoincrement, at text, method text, path text, status integer,
                 ms integer, actor text, ip text, rid text)''')
    c.execute('create index if not exists access_at on access(at)')
    return c


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')


def _digest(prev, row):
    body = json.dumps([row[k] for k in ('at', 'actor', 'role', 'ip', 'ua', 'action', 'object', 'outcome', 'details', 'rid')], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256((prev + body).encode()).hexdigest()


def client_ip(req):
    if req is None: return '-'
    xf = req.headers.get('x-forwarded-for') if hasattr(req, 'headers') else None
    if xf: return xf.split(',')[0].strip()
    return req.client.host if getattr(req, 'client', None) else '-'


def log(req, action, obj='', outcome='ok', actor=None, **details):
    """Append one audit row. `actor` = {'user','role'} (defaults to the signed-in user on the request)."""
    u = actor or (getattr(req.state, 'user', None) if req is not None and hasattr(req, 'state') else None) or {}
    row = {'at': _now(), 'actor': u.get('user') or details.pop('_actor', '') or 'anonymous', 'role': u.get('role', ''),
           'ip': client_ip(req), 'ua': (req.headers.get('user-agent', '')[:300] if req is not None and hasattr(req, 'headers') else 'system'),
           'action': action, 'object': obj or '', 'outcome': outcome,
           'details': json.dumps(details, ensure_ascii=False, default=str) if details else '',
           'rid': (getattr(req.state, 'rid', '') if req is not None and hasattr(req, 'state') else '')}
    with _lock, _c() as c:
        r = c.execute('select hash from audit order by id desc limit 1').fetchone()
        prev = r['hash'] if r else GENESIS
        row['prev'] = prev; row['hash'] = _digest(prev, row)
        c.execute('insert into audit(at,actor,role,ip,ua,action,object,outcome,details,rid,prev,hash) values(:at,:actor,:role,:ip,:ua,:action,:object,:outcome,:details,:rid,:prev,:hash)', row)


def access(req, status, ms):
    u = getattr(req.state, 'user', None) or {}
    try:
        with _c() as c:
            c.execute('insert into access(at,method,path,status,ms,actor,ip,rid) values(?,?,?,?,?,?,?,?)',
                      (_now(), req.method, req.url.path[:300], status, ms, u.get('user', ''), client_ip(req), getattr(req.state, 'rid', '')))
    except Exception:
        pass


def prune_access(days=180):
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
    with _c() as c: c.execute('delete from access where at < ?', (cut,))


def verify():
    """(True, count) when the chain is intact, else (False, id of the first bad row)."""
    with _c() as c:
        prev, n = GENESIS, 0
        for r in c.execute('select * from audit order by id'):
            d = dict(r)
            if d['prev'] != prev or _digest(prev, d) != d['hash']: return False, d['id']
            prev = d['hash']; n += 1
        return True, n


def query(actor='', action='', obj='', since='', until='', outcome='', limit=100, offset=0):
    w, a = [], []
    if actor: w.append('actor = ?'); a.append(actor)
    if action: w.append('action like ?'); a.append(action + '%')
    if obj: w.append('object like ?'); a.append('%' + obj + '%')
    if outcome: w.append('outcome = ?'); a.append(outcome)
    if since: w.append('at >= ?'); a.append(since)
    if until: w.append('at < ?'); a.append(until)
    where = (' where ' + ' and '.join(w)) if w else ''
    with _c() as c:
        total = c.execute('select count(*) n from audit' + where, a).fetchone()['n']
        rows = [dict(r) for r in c.execute('select * from audit' + where + ' order by id desc limit ? offset ?', a + [limit, offset])]
    for r in rows: r['details'] = json.loads(r['details']) if r['details'] else {}
    return total, rows


def actors():
    with _c() as c: return [r['actor'] for r in c.execute('select distinct actor from audit order by actor')]


def export_csv(**f):
    total, rows = query(limit=1000000, **f)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(['id', 'at_utc', 'actor', 'role', 'ip', 'user_agent', 'action', 'object', 'outcome', 'details', 'request_id', 'hash'])
    for r in reversed(rows):
        w.writerow([r['id'], r['at'], r['actor'], r['role'], r['ip'], r['ua'], r['action'], r['object'], r['outcome'], json.dumps(r['details'], ensure_ascii=False), r['rid'], r['hash']])
    return '﻿' + buf.getvalue()


def stats():
    with _c() as c:
        day = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
        return {'total': c.execute('select count(*) n from audit').fetchone()['n'],
                'day': c.execute('select count(*) n from audit where at >= ?', (day,)).fetchone()['n'],
                'denied': c.execute("select count(*) n from audit where outcome != 'ok' and at >= ?", (day,)).fetchone()['n'],
                'requests': c.execute('select count(*) n from access where at >= ?', (day,)).fetchone()['n']}


def diff(old, new, path='', out=None, cap=300):
    """Field-level changes between two data dicts: [{'f': 'top10.3.pct', 'b': 4.1, 'a': 4.3}, …]."""
    out = [] if out is None else out
    if len(out) >= cap: return out
    if isinstance(old, dict) or isinstance(new, dict):
        old = old if isinstance(old, dict) else {}; new = new if isinstance(new, dict) else {}
        for k in sorted(set(old) | set(new), key=str): diff(old.get(k), new.get(k), f'{path}.{k}' if path else str(k), out, cap)
    elif isinstance(old, list) or isinstance(new, list):
        old = old if isinstance(old, list) else []; new = new if isinstance(new, list) else []
        for i in range(max(len(old), len(new))): diff(old[i] if i < len(old) else None, new[i] if i < len(new) else None, f'{path}.{i}', out, cap)
    elif old != new and not (old in (None, '') and new in (None, '')):
        out.append({'f': path, 'b': old, 'a': new})
    return out


def new_rid():
    return uuid.uuid4().hex[:16]
