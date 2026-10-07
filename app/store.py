"""Storage: one SQLite file and an output folder on the Railway volume (DATA_DIR, default ./data)."""
import os, json, sqlite3, datetime, threading
DATA = os.path.abspath(os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data')))
os.makedirs(DATA, exist_ok=True)
DB = os.path.join(DATA, 'app.db')
_lock = threading.Lock()


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y-%m-%d %H:%M')


def _c():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.execute('''create table if not exists statements(id text primary key, fund text, q text, data text, status text,
                 notes text, updated text, generated text, files text, final_at text, log text)''')
    c.execute('''create table if not exists events(id integer primary key autoincrement, sid text, at text, what text)''')
    return c


def get(fund, q):
    with _lock, _c() as c:
        r = c.execute('select * from statements where id=?', (f'{fund}:{q}',)).fetchone()
        if not r: return None
        d = dict(r)
        for k in ('data', 'files', 'log'): d[k] = json.loads(d[k]) if d.get(k) else ({} if k != 'log' else [])
        return d


def put(fund, q, **kw):
    cur = get(fund, q) or {'id': f'{fund}:{q}', 'fund': fund, 'q': q, 'data': {}, 'status': 'new', 'notes': '', 'files': {}, 'log': []}
    cur.update(kw); cur['updated'] = now()
    row = dict(cur)
    for k in ('data', 'files', 'log'): row[k] = json.dumps(row.get(k) or ({} if k != 'log' else []), ensure_ascii=False)
    with _lock, _c() as c:
        c.execute('''insert or replace into statements(id,fund,q,data,status,notes,updated,generated,files,final_at,log)
                     values(:id,:fund,:q,:data,:status,:notes,:updated,:generated,:files,:final_at,:log)''',
                  {k: row.get(k) for k in ('id', 'fund', 'q', 'data', 'status', 'notes', 'updated', 'generated', 'files', 'final_at', 'log')})
    return cur


def event(fund, q, what):
    with _lock, _c() as c:
        c.execute('insert into events(sid,at,what) values(?,?,?)', (f'{fund}:{q}', now(), what))


def events(fund, q, n=30):
    with _lock, _c() as c:
        return [dict(r) for r in c.execute('select at,what from events where sid=? order by id desc limit ?', (f'{fund}:{q}', n))]


def struct_path(fund, q, lang):
    d = os.path.join(DATA, 'structs', fund); os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{q}.{lang}.json')


def out_dir(fund, q):
    d = os.path.join(DATA, 'out', fund, q); os.makedirs(d, exist_ok=True); return d


# ---------- users (editors; the admin signs in with ADMIN_PASSWORD) ----------
import hashlib as _h, secrets as _s


def _users_c():
    c = _c()
    c.execute('''create table if not exists users(username text primary key, name text, role text, salt text, hash text,
                 active integer, created text, last_login text)''')
    if 'email' not in [r[1] for r in c.execute('pragma table_info(users)')]: c.execute('alter table users add column email text')
    return c


def _hash(pw, salt):
    return _h.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()


def users():
    with _lock, _users_c() as c:
        return [dict(r) for r in c.execute('select username,name,role,active,created,last_login,email from users order by created')]


def create_user(username, name, role='editor'):
    """Returns a one-time password shown to the admin only once."""
    pw = '-'.join(_s.token_hex(2) for _ in range(3)).upper()
    salt = _s.token_hex(16)
    with _lock, _users_c() as c:
        c.execute('''insert into users(username,name,role,salt,hash,active,created,last_login) values(?,?,?,?,?,1,?,NULL)
                     on conflict(username) do update set name=excluded.name, role=excluded.role, salt=excluded.salt, hash=excluded.hash, active=1''',
                  (username, name, role, salt, _hash(pw, salt), now()))
    return pw


def set_role(username, role):
    with _lock, _users_c() as c:
        c.execute('update users set role=? where username=?', (role, username))


def set_email(username, email):
    with _lock, _users_c() as c:
        c.execute('update users set email=? where username=?', (email or None, username))


def setting(k, default=None):
    with _lock, _c() as c:
        c.execute('create table if not exists settings(k text primary key, v text)')
        r = c.execute('select v from settings where k=?', (k,)).fetchone()
        return json.loads(r['v']) if r else default


def set_setting(k, v):
    with _lock, _c() as c:
        c.execute('create table if not exists settings(k text primary key, v text)')
        c.execute('insert or replace into settings(k,v) values(?,?)', (k, json.dumps(v, ensure_ascii=False)))


def set_active(username, active):
    with _lock, _users_c() as c:
        c.execute('update users set active=? where username=?', (1 if active else 0, username))


def check_user(username, pw):
    pw = (pw or '').strip().upper()
    with _lock, _users_c() as c:
        r = c.execute('select * from users where username=? and active=1', (username,)).fetchone()
        if not r: return None
        if not _s.compare_digest(_hash(pw, r['salt']), r['hash']): return None
        c.execute('update users set last_login=? where username=?', (now(), username))
        return dict(r)


# ---------- historical records: AR/EN conflicts and the correction log ----------
def _rec_c():
    c = _c()
    c.execute('create table if not exists conflicts(sid text primary key, items text, at text)')
    c.execute('''create table if not exists corrections(id integer primary key autoincrement, sid text, at text, by text,
                 lang text, section text, label text, before text, after text, reason text)''')
    return c


def set_conflicts(fund, q, items):
    with _lock, _rec_c() as c:
        c.execute('insert or replace into conflicts values(?,?,?)', (f'{fund}:{q}', json.dumps(items, ensure_ascii=False), now()))


def get_conflicts(fund, q):
    with _lock, _rec_c() as c:
        r = c.execute('select items from conflicts where sid=?', (f'{fund}:{q}',)).fetchone()
        return json.loads(r['items']) if r else None


def add_corrections(fund, q, by, reason, rows):
    with _lock, _rec_c() as c:
        for r in rows:
            c.execute('insert into corrections(sid,at,by,lang,section,label,before,after,reason) values(?,?,?,?,?,?,?,?,?)',
                      (f'{fund}:{q}', now(), by, r['lang'], r['section'], r['label'], r['before'], r['after'], reason))


def corrections(fund, q):
    with _lock, _rec_c() as c:
        return [dict(r) for r in c.execute('select at,by,lang,section,label,before,after,reason from corrections where sid=? order by id desc', (f'{fund}:{q}',))]


def correction_counts():
    with _lock, _rec_c() as c:
        return {r['sid']: r['n'] for r in c.execute('select sid, count(*) n from corrections group by sid')}


def draft_struct_path(fund, q, lang):
    d = os.path.join(DATA, 'structs', fund, 'draft'); os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{q}.{lang}.json')


def orig_struct_path(fund, q, lang):
    d = os.path.join(DATA, 'structs', fund, 'original'); os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{q}.{lang}.json')


def all_records():
    with _lock, _c() as c:
        return [dict(r) for r in c.execute('select id,fund,q,status,updated,final_at from statements')]


def delete(fund, q):
    """Remove a statement row and its events (used to clear test data; a backup is taken first by the caller)."""
    with _lock, _c() as c:
        c.execute('delete from statements where id=?', (f'{fund}:{q}',))
        c.execute('delete from events where sid=?', (f'{fund}:{q}',))
