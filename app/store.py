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
