"""The quarterly statement's approval route, as Product Development set it (7 October 2026).

FACO enters the figures first; the fund managers (CMD) build on them and issue the drafts; Corporate Communications
proofs the Arabic and translates the English; Product Development finalises the English and issues the final versions
in both languages; Business Development and Compliance review the final versions; the Deputy CEO, then the Fund Board,
approve them; Compliance publishes; then Product Development uploads to Tadawul and Corporate Communications to the
website, in parallel. Product Development follows every step and can return the statement.

Each statement keeps its stage, the review sign-offs and a history of every hand-over in table `wf`; comments live in
table `comments`. The platform administrator can act at any stage (every action is in the audit log under their name).
"""
import json, sqlite3, threading
import store

# role → (Arabic, English)
ROLES = {
    'admin': ('مدير المنصة', 'Platform administrator'),
    'editor': ('مُدخل البيانات', 'Data entry'),
    'faco': ('الإدارة المالية وعمليات الصناديق', 'FACO'),
    'cmd': ('إدارة أسواق المال', 'Capital Markets (CMD)'),
    'pdd': ('تطوير المنتجات', 'Product Development'),
    'bdd': ('تطوير الأعمال', 'Business Development'),
    'compliance': ('الالتزام', 'Compliance'),
    'ccd': ('الاتصال المؤسسي', 'Corporate Communications'),
    'dceo': ('نائب الرئيس التنفيذي', 'Deputy CEO'),
    'board': ('أمانة مجلس إدارة الصندوق', 'Fund Board secretary'),
}
DEPARTMENTS = [r for r in ROLES if r != 'admin']

# stage key, Arabic, English, roles that act on it
STAGES = [
    ('faco', 'أرقام FACO', 'FACO figures', ('faco', 'editor')),
    ('cmd', 'محتوى إدارة أسواق المال', 'Fund managers (CMD)', ('cmd', 'editor')),
    ('ccd', 'التدقيق اللغوي والترجمة', 'Proofing and translation', ('ccd',)),
    ('english', 'إصدار النسخ النهائية', 'Final versions issued', ('pdd',)),
    ('review', 'مراجعة تطوير الأعمال والالتزام', 'BDD and Compliance review', ('bdd', 'compliance')),
    ('dceo', 'اعتماد نائب الرئيس التنفيذي', 'DCEO approval', ('dceo',)),
    ('board', 'اعتماد مجلس إدارة الصندوق', 'Fund Board approval', ('board',)),
    ('publish', 'النشر', 'Publishing', ('compliance',)),
    ('upload', 'الرفع على تداول والموقع', 'Tadawul and website upload', ('pdd', 'ccd')),
    ('done', 'مكتمل', 'Complete', ()),
]
ORDER = [s[0] for s in STAGES]
STAGE = {s[0]: s for s in STAGES}
REVIEWERS = ('bdd', 'compliance')
UPLOADS = {'pdd': 'tadawul', 'ccd': 'website'}   # after publishing: PDD uploads to Tadawul, CCD to the website, in parallel
EDIT_STAGES = ('faco', 'cmd', 'ccd', 'english')     # stages in which someone may change the data
GEN_STAGES = ('faco', 'cmd', 'ccd', 'english')      # stages in which drafts can be (re)issued

_lock = threading.Lock()


def _c():
    c = sqlite3.connect(store.DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute('create table if not exists wf(sid text primary key, stage text, signoffs text, dirty integer, history text)')
    c.execute('''create table if not exists comments(id integer primary key autoincrement, sid text, at text, user text, name text, role text,
                 stage text, section text, body text, resolved_by text, resolved_at text)''')
    return c


def _initial(status):
    if status in ('submitted',): return 'ccd'
    if status in ('final',): return 'review'
    if status in ('published', 'corrected'): return 'done'
    return 'faco'


def get(fund, q, status='new'):
    sid = f'{fund}:{q}'
    with _lock, _c() as c:
        r = c.execute('select * from wf where sid=?', (sid,)).fetchone()
        if not r:
            st = _initial(status)
            c.execute('insert into wf(sid,stage,signoffs,dirty,history) values(?,?,?,?,?)', (sid, st, '{}', 0, '[]'))
            return {'sid': sid, 'stage': st, 'signoffs': {}, 'dirty': False, 'history': []}
        return {'sid': sid, 'stage': r['stage'], 'signoffs': json.loads(r['signoffs'] or '{}'), 'dirty': bool(r['dirty']), 'history': json.loads(r['history'] or '[]')}


def _put(w):
    with _lock, _c() as c:
        c.execute('update wf set stage=?, signoffs=?, dirty=?, history=? where sid=?',
                  (w['stage'], json.dumps(w['signoffs'], ensure_ascii=False), 1 if w['dirty'] else 0, json.dumps(w['history'][-200:], ensure_ascii=False), w['sid']))


def record(w, me, action, to=None, note=''):
    w['history'].append({'at': store.now(), 'user': me['user'], 'name': me['name'], 'role': me['role'], 'from': w['stage'], 'to': to or w['stage'],
                         'action': action, 'note': note})
    if to: w['stage'] = to
    _put(w)
    return w


def set_dirty(fund, q, dirty=True):
    w = get(fund, q); w['dirty'] = dirty; _put(w)


def acts(role, stage):
    """Whether this role may act at this stage (the administrator always may; Product Development follows every step)."""
    if role == 'admin': return True
    return role in STAGE[stage][3]


def can_return(role, stage):
    return stage in ('cmd', 'ccd', 'english', 'review', 'dceo', 'board') and (role in ('admin', 'pdd') or acts(role, stage))


# which tab of the editor a field belongs to: the same split as the editor's TAB()
CMD_PREFIX = ('commentary', 'top10', 'alloc', 'ret_', 'risk', 'own_', 'rating', 'price', 'perf_points', 'tollfree')


def owner(path):
    k = path.split('.')[0]
    if k == 'pe' or k.startswith(CMD_PREFIX): return 'cmd'
    return 'faco'


def may_edit(role, stage, path):
    """May this role change this field (dotted path) at this stage?"""
    if stage not in EDIT_STAGES: return False
    if role == 'admin': return True
    if stage in ('faco', 'cmd'):
        if role in ('editor', 'pdd'): return True
        if role == 'faco': return owner(path) == 'faco'
        if role == 'cmd': return stage == 'cmd' and owner(path) == 'cmd'
        return False
    if stage == 'ccd':
        return role == 'ccd' and (path.startswith('commentary') or path.endswith('.en') or path.endswith('.title_en'))
    if stage == 'english':
        return role == 'pdd' and (path in ('commentary.en',) or path.startswith('commentary_mt') or path.endswith('.en') or path.endswith('.title_en'))
    return False


def can_edit_any(role, stage):
    if stage not in EDIT_STAGES: return False
    if role == 'admin': return True
    return {'faco': ('faco', 'editor', 'pdd'), 'cmd': ('faco', 'cmd', 'editor', 'pdd'), 'ccd': ('ccd',), 'english': ('pdd',)}[stage].__contains__(role)


def stage_label(stage, lang='ar'):
    s = STAGE.get(stage)
    return (s[1] if lang == 'ar' else s[2]) if s else stage


def role_label(role, lang='ar'):
    r = ROLES.get(role)
    return (r[0] if lang == 'ar' else r[1]) if r else role


def view(fund, q, status, role, lang='ar'):
    """What the editor shows: the route with the current stage, the sign-offs and the history."""
    w = get(fund, q, status)
    i = ORDER.index(w['stage']) if w['stage'] in ORDER else 0
    return {'stage': w['stage'], 'index': i, 'dirty': w['dirty'], 'signoffs': w['signoffs'],
            'stages': [{'key': k, 'label': ar if lang == 'ar' else en, 'roles': [role_label(r, lang) for r in rs]} for k, ar, en, rs in STAGES],
            'acts': acts(role, w['stage']), 'can_return': can_return(role, w['stage']), 'edit': can_edit_any(role, w['stage']),
            'history': w['history'][-40:][::-1]}


# ---------- comments ----------

def comments(fund, q):
    with _lock, _c() as c:
        return [dict(r) for r in c.execute('select * from comments where sid=? order by id desc', (f'{fund}:{q}',))]


def add_comment(fund, q, me, stage, section, body):
    with _lock, _c() as c:
        return c.execute('insert into comments(sid,at,user,name,role,stage,section,body) values(?,?,?,?,?,?,?,?)',
                         (f'{fund}:{q}', store.now(), me['user'], me['name'], me['role'], stage, section or '', body)).lastrowid


def resolve_comment(cid, me, fund, q):
    with _lock, _c() as c:
        r = c.execute('select * from comments where id=? and sid=?', (cid, f'{fund}:{q}')).fetchone()
        if not r: return None
        c.execute('update comments set resolved_by=?, resolved_at=? where id=?', (me['name'], store.now(), cid))
        return dict(r)


def open_comments(fund, q):
    return sum(1 for x in comments(fund, q) if not x['resolved_at'])
