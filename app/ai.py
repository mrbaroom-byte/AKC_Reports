"""Claude through the Anthropic Messages API, with usage accounting and a monthly soft cap.

The key is read from ANTHROPIC_API_KEY and never logged or returned. AI_MODEL picks the model; AI_MONTHLY_CAP_USD sets
a soft cap (estimated from token counts with AI_PRICE_IN / AI_PRICE_OUT, US$ per million tokens) after which calls are
refused until the next month. The hard limit is the one set in the Anthropic Console.
AI_MOCK=1 answers locally with canned replies (for tests without network access).
"""
import os, json, time, sqlite3, datetime, threading, urllib.request, urllib.error, base64
import store

URL = 'https://api.anthropic.com/v1/messages'
MODEL = os.environ.get('AI_MODEL', 'claude-sonnet-5-5')
PRICE_IN = float(os.environ.get('AI_PRICE_IN', '3'))
PRICE_OUT = float(os.environ.get('AI_PRICE_OUT', '15'))
_lock = threading.Lock()
STATUS = {'checked': None, 'ok': None, 'detail': ''}


class AIError(Exception):
    pass


def key():
    return (os.environ.get('ANTHROPIC_API_KEY') or '').strip()


def configured():
    return bool(key()) or os.environ.get('AI_MOCK') == '1'


def cap():
    try: return float(os.environ.get('AI_MONTHLY_CAP_USD', '0') or 0)
    except ValueError: return 0.0


def _c():
    c = sqlite3.connect(store.DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute('''create table if not exists ai_usage(id integer primary key autoincrement, at text, actor text, feature text, model text,
                 tin integer, tout integer, usd real, ms integer, ok integer, obj text)''')
    return c


def month_usd():
    m = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')
    with _c() as c:
        r = c.execute("select coalesce(sum(usd),0) s from ai_usage where at like ?", (m + '%',)).fetchone()
        return round(r['s'], 4)


def usage_summary():
    m = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')
    with _c() as c:
        rows = [dict(r) for r in c.execute("select feature, count(*) n, sum(tin) tin, sum(tout) tout, round(sum(usd),4) usd from ai_usage where at like ? group by feature", (m + '%',))]
    return {'month': m, 'usd': month_usd(), 'cap': cap(), 'by_feature': rows, 'model': MODEL, 'configured': configured()}


def _record(actor, feature, tin, tout, ms, ok, obj=''):
    usd = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6
    with _lock, _c() as c:
        c.execute('insert into ai_usage(at,actor,feature,model,tin,tout,usd,ms,ok,obj) values(?,?,?,?,?,?,?,?,?,?)',
                  (datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), actor, feature, MODEL, tin, tout, usd, ms, 1 if ok else 0, obj))
    return usd


def call(messages, system='', tools=None, tool_choice=None, max_tokens=4096, actor='', feature='', obj='', temperature=None):
    """One Messages API call. Returns the response dict. Raises AIError with a message fit for the user."""
    if not configured(): raise AIError('الذكاء الاصطناعي غير مُفعَّل: لم يُضبط مفتاح الواجهة.')
    if cap() and month_usd() >= cap(): raise AIError('بلغ استهلاك هذا الشهر السقف المحدد للذكاء الاصطناعي.')
    if os.environ.get('AI_MOCK') == '1':
        import ai_mock
        r = ai_mock.reply(messages, system, tools, tool_choice)
        _record(actor, feature, r['usage']['input_tokens'], r['usage']['output_tokens'], 5, True, obj)
        return r
    body = {'model': MODEL, 'max_tokens': max_tokens, 'messages': messages}
    if temperature is not None: body['temperature'] = temperature   # newer models reject it; leave unset by default
    if system: body['system'] = system
    if tools: body['tools'] = tools
    if tool_choice: body['tool_choice'] = tool_choice
    data = json.dumps(body).encode()
    t0 = time.time(); last = None
    for attempt in range(3):
        req = urllib.request.Request(URL, data=data, method='POST', headers={'x-api-key': key(), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out = json.loads(r.read())
            u = out.get('usage', {})
            _record(actor, feature, u.get('input_tokens', 0), u.get('output_tokens', 0), int((time.time() - t0) * 1000), True, obj)
            return out
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:500]; last = f'{e.code}: {msg}'
            if e.code in (429, 500, 502, 503, 529): time.sleep(2 * (attempt + 1)); continue
            break
        except Exception as e:
            last = str(e)[:300]; time.sleep(2 * (attempt + 1))
    _record(actor, feature, 0, 0, int((time.time() - t0) * 1000), False, obj)
    raise AIError('تعذّر الاتصال بخدمة الذكاء الاصطناعي. ' + (last or ''))


def text_of(resp):
    return ''.join(b.get('text', '') for b in resp.get('content', []) if b.get('type') == 'text').strip()


def tool_input(resp, name):
    for b in resp.get('content', []):
        if b.get('type') == 'tool_use' and b.get('name') == name: return b.get('input') or {}
    return None


def image_block(png_bytes, media='image/png'):
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': media, 'data': base64.b64encode(png_bytes).decode()}}


def selfcheck():
    """A tiny call at start-up so /health can say whether the key works (the key itself is never shown)."""
    STATUS['checked'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    if not configured(): STATUS.update(ok=False, detail='not configured'); return
    try:
        r = call([{'role': 'user', 'content': 'Reply with the single word: ok'}], max_tokens=5, actor='system', feature='selfcheck')
        STATUS.update(ok=True, detail=f'model {r.get("model", MODEL)}')
    except AIError as e:
        STATUS.update(ok=False, detail=str(e)[-200:])
