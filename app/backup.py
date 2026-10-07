"""Backups of everything the platform holds that cannot be rebuilt: the database, the structs (including the
published originals kept before a correction), the issued final and corrected files, and uploaded sources.

A backup is one zip under DATA/backups. One is taken each day, one before every final approval or correction,
and the admin can download a fresh one at any time. The last 30 daily backups are kept; event backups are kept 90 days.
"""
import os, io, zipfile, sqlite3, datetime, threading, time, glob
import store

DIR = os.path.join(store.DATA, 'backups'); os.makedirs(DIR, exist_ok=True)
KEEP_DAILY, KEEP_EVENT_DAYS = 30, 90
_lock = threading.Lock()


def _stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y%m%d-%H%M%S')


def _db_copy():
    """A consistent copy of the live database (SQLite online backup), as bytes."""
    tmp = os.path.join(DIR, '.snapshot.db')
    src = sqlite3.connect(store.DB); dst = sqlite3.connect(tmp)
    with dst: src.backup(dst)
    src.close(); dst.close()
    b = open(tmp, 'rb').read(); os.remove(tmp); return b


def _files():
    """Paths (relative to DATA) worth keeping: structs, final/corrected outputs, uploaded sources."""
    out = []
    for p in glob.glob(os.path.join(store.DATA, 'structs', '**', '*.json'), recursive=True): out.append(p)
    for kind in ('final', 'corrected'):
        for p in glob.glob(os.path.join(store.DATA, 'out', '*', '*', kind, '**', '*'), recursive=True):
            if os.path.isfile(p) and p.endswith(('.pdf', '.docx')): out.append(p)
    for p in glob.glob(os.path.join(store.DATA, 'uploads', '**', '*'), recursive=True):
        if os.path.isfile(p): out.append(p)
    return out


def make_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('app.db', _db_copy())
        for p in _files(): z.write(p, os.path.relpath(p, store.DATA))
        z.writestr('README.txt', 'Alkhabeer quarterly statements backup ' + _stamp() + '\nRestore: stop the service, replace DATA_DIR contents with this archive, start the service.\n')
    return buf.getvalue()


def take(kind='daily', note=''):
    """Write a backup zip; returns its file name."""
    with _lock:
        name = f'{kind}-{_stamp()}' + (f'-{note}' if note else '') + '.zip'
        b = make_bytes(); p = os.path.join(DIR, name)
        open(p + '.part', 'wb').write(b); os.replace(p + '.part', p)
        prune()
        return name


def prune():
    daily = sorted(glob.glob(os.path.join(DIR, 'daily-*.zip')))
    for p in daily[:-KEEP_DAILY]: os.remove(p)
    cut = time.time() - KEEP_EVENT_DAYS * 86400
    for p in glob.glob(os.path.join(DIR, 'event-*.zip')):
        if os.path.getmtime(p) < cut: os.remove(p)


def listing():
    out = []
    for p in sorted(glob.glob(os.path.join(DIR, '*.zip')), reverse=True):
        st = os.stat(p)
        out.append({'name': os.path.basename(p), 'size': st.st_size,
                    'at': datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y-%m-%d %H:%M')})
    return out


def _today_done():
    d = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y%m%d')
    return bool(glob.glob(os.path.join(DIR, f'daily-{d}-*.zip')))


def _loop():
    while True:
        try:
            if not _today_done(): take('daily')
        except Exception as e:
            print('backup failed:', e)
        time.sleep(3600)


def start():
    threading.Thread(target=_loop, daemon=True, name='daily-backup').start()
