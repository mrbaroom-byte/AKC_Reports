"""E-mail alerts for the statement cycle.

Sent when a statement is submitted for approval (to the approvers), returned for changes and given final approval (to
the data-entry users). Each message is in Arabic with an English summary underneath.

Delivery, whichever is configured (checked in this order):
  Microsoft 365 (Graph)  M365_TENANT_ID, M365_CLIENT_ID, M365_CLIENT_SECRET, MAIL_FROM (the mailbox that sends);
         the app registration needs the Mail.Send application permission, ideally limited to that one mailbox
  SMTP   SMTP_HOST, SMTP_PORT (587 STARTTLS, 465 SSL), SMTP_USER, SMTP_PASSWORD, MAIL_FROM
  Resend RESEND_API_KEY, MAIL_FROM (the sending domain must be verified in Resend)
  MAIL_MOCK=1 writes the messages to DATA_DIR/outbox/ instead (local tests only).
Approver addresses are kept in the app's settings (Users page); data-entry users' addresses on their accounts.
Every send is written to the audit log; credentials are never logged or shown.
"""
import os, json, ssl, smtplib, threading, urllib.request, urllib.error, datetime, re, html as H
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
import store, audit as A, model as M

EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$')


def provider():
    if os.environ.get('MAIL_MOCK') == '1': return 'mock'
    if os.environ.get('M365_CLIENT_ID') and os.environ.get('M365_TENANT_ID'): return 'm365'
    if os.environ.get('SMTP_HOST'): return 'smtp'
    if os.environ.get('RESEND_API_KEY'): return 'resend'
    return None


def sender():
    return os.environ.get('MAIL_FROM') or os.environ.get('SMTP_USER') or 'reports@localhost'


def status():
    p = provider()
    return {'configured': bool(p), 'provider': p, 'from': sender() if p else None}


def emails(text):
    """Valid addresses from free text (comma, semicolon, space or newline separated), without duplicates."""
    out = []
    for x in re.split(r'[\s,;،]+', text or ''):
        x = x.strip().lower()
        if x and EMAIL_RE.match(x) and x not in out: out.append(x)
    return out


def approvers():
    return store.setting('approver_emails', []) or []


def editors():
    return [u['email'] for u in store.users() if u.get('active') and u.get('email')]


def app_url(req=None):
    u = os.environ.get('APP_URL')
    if u: return u.rstrip('/')
    if req is not None:
        proto = req.headers.get('x-forwarded-proto') or req.url.scheme
        return f"{proto}://{req.headers.get('x-forwarded-host') or req.headers.get('host')}"
    return ''


# ---------- message ----------

def _page(ar_title, ar_lines, en_title, en_lines, link, ar_btn, en_btn):
    e = H.escape
    p_ar = ''.join(f'<p style="margin:0 0 12px">{x}</p>' for x in ar_lines)
    p_en = ''.join(f'<p style="margin:0 0 8px">{x}</p>' for x in en_lines)
    btn = lambda t: (f'<a href="{e(link)}" style="display:inline-block;background:#12284B;color:#ffffff;text-decoration:none;font-weight:600;'
                     f'padding:11px 22px;border-radius:8px">{e(t)}</a>') if link else ''
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#F5F7FB;font-family:Tahoma,Arial,sans-serif;color:#1C2B45">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F5F7FB;padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #E1E6EF;border-radius:12px;overflow:hidden">
<tr><td style="background:#12284B;color:#ffffff;padding:16px 24px;font-size:14px;font-weight:600" dir="rtl">الخبير المالية · البيانات الربعية</td></tr>
<tr><td style="padding:24px 24px 8px;font-size:15px;line-height:1.8" dir="rtl" align="right">
<h1 style="font-size:19px;margin:0 0 14px;color:#12284B">{e(ar_title)}</h1>{p_ar}<p style="margin:18px 0 6px">{btn(ar_btn)}</p></td></tr>
<tr><td style="padding:8px 24px 22px;font-size:13px;line-height:1.6;color:#5A6478;border-top:1px solid #E1E6EF" dir="ltr" align="left">
<p style="margin:14px 0 8px;font-weight:600;color:#3A4458">{e(en_title)}</p>{p_en}</td></tr>
</table>
<p style="font-size:11.5px;color:#9AA3B5;margin:14px 0 0" dir="rtl">رسالة آلية من منصة البيانات الربعية. لا تردّ عليها.</p>
</td></tr></table></body></html>'''


def compose(kind, fund, q, by='', note='', link='', findings=None, by_en=''):
    """(subject, html, text) for one alert."""
    e = H.escape
    by_en = by_en or ('The approver' if kind in ('returned', 'final') else 'A data-entry user')
    F = M.FUNDS[fund]; fa, fe = F['ar'], F['en']; qa, qe = M.qlabel(q, 'ar'), M.qlabel(q, 'en')
    note_ar = [f'ملاحظة المعتمِد: «{e(note)}»'] if note else []
    note_en = [f'Approver’s note: “{e(note)}”'] if note else []
    if kind == 'submitted':
        f = ([f'المقارنة بالربع السابق: {findings} ملاحظة تحتاج مراجعة قبل الاعتماد.'] if findings else ['المقارنة بالربع السابق: لا ملاحظات.']) if findings is not None else []
        fe_ = ([f'Comparison with last quarter: {findings} finding(s) to review.'] if findings else ['Comparison with last quarter: no findings.']) if findings is not None else []
        subj = f'بانتظار اعتمادك: {fa} — {qa}'
        ar = (f'بانتظار اعتمادك: {fa}', [f'رفع {e(by)} مسودة البيان الربعي ل{e(fa)} عن {e(qa)} للاعتماد.'] + f)
        en = (f'Awaiting your approval: {fe}, {qe}', [f'{e(by_en)} submitted the {e(qe)} quarterly statement of {e(fe)} for approval.'] + fe_)
        btn = ('مراجعة البيان', 'Review the statement')
    elif kind == 'returned':
        subj = f'أُعيد للتعديل: {fa} — {qa}'
        ar = (f'أُعيد للتعديل: {fa}', [f'أعاد {e(by)} البيان الربعي ل{e(fa)} عن {e(qa)} للتعديل.'] + note_ar)
        en = (f'Returned for changes: {fe}, {qe}', [f'{e(by_en)} returned the {e(qe)} quarterly statement of {e(fe)} for changes.'] + note_en)
        btn = ('فتح البيان', 'Open the statement')
    elif kind == 'final':
        subj = f'اعتُمد: {fa} — {qa}'
        ar = (f'اعتُمد البيان: {fa}', [f'اعتمد {e(by)} النسخة النهائية من البيان الربعي ل{e(fa)} عن {e(qa)}، والملفات العربية والإنجليزية جاهزة.'])
        en = (f'Approved: {fe}, {qe}', [f'{e(by_en)} approved the final {e(qe)} quarterly statement of {e(fe)}. The Arabic and English files are ready.'])
        btn = ('تنزيل الملفات', 'Download the files')
    else:   # test
        subj = 'رسالة تجريبية من منصة البيانات الربعية'
        ar = ('رسالة تجريبية', ['وصلتك هذه الرسالة لأن تنبيهات البريد مفعّلة في منصة البيانات الربعية.'])
        en = ('Test message', ['You received this because e-mail alerts are set up on the quarterly statements platform.'])
        btn = ('فتح المنصة', 'Open the platform')
    html_ = _page(ar[0], ar[1], en[0], en[1], link, *btn)
    strip = lambda s: re.sub('<[^>]+>', '', H.unescape(s))
    text = '\n'.join([ar[0], *map(strip, ar[1]), link, '', en[0], *map(strip, en[1])])
    return subj, html_, text


# ---------- delivery ----------

def _smtp(to, subj, html_, text):
    m = EmailMessage(); m['Subject'] = subj; m['From'] = formataddr(('الخبير المالية · البيانات الربعية', sender())); m['To'] = ', '.join(to)
    m['Message-ID'] = make_msgid(domain=sender().split('@')[-1]); m.set_content(text); m.add_alternative(html_, subtype='html')
    host, port = os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', '587'))
    ctx = ssl.create_default_context()
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
    else:
        s = smtplib.SMTP(host, port, timeout=30); s.starttls(context=ctx)
    try:
        if os.environ.get('SMTP_USER'): s.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
        s.send_message(m)
    finally:
        try: s.quit()
        except Exception: pass


_TOKEN = {'v': None, 'exp': 0}


def _m365(to, subj, html_, text):
    import time, urllib.parse
    if not _TOKEN['v'] or _TOKEN['exp'] < time.time() + 60:
        body = urllib.parse.urlencode({'client_id': os.environ['M365_CLIENT_ID'], 'client_secret': os.environ.get('M365_CLIENT_SECRET', ''),
                                       'scope': 'https://graph.microsoft.com/.default', 'grant_type': 'client_credentials'}).encode()
        r = urllib.request.Request(f"https://login.microsoftonline.com/{os.environ['M365_TENANT_ID']}/oauth2/v2.0/token", data=body, method='POST')
        try:
            with urllib.request.urlopen(r, timeout=30) as x: t = json.loads(x.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'token {e.code}: ' + e.read().decode('utf-8', 'replace')[:300])
        _TOKEN.update(v=t['access_token'], exp=time.time() + int(t.get('expires_in', 3600)))
    msg = {'message': {'subject': subj, 'body': {'contentType': 'HTML', 'content': html_},
                       'toRecipients': [{'emailAddress': {'address': a}} for a in to]}, 'saveToSentItems': True}
    r = urllib.request.Request(f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(sender())}/sendMail", data=json.dumps(msg).encode(), method='POST',
                               headers={'Authorization': 'Bearer ' + _TOKEN['v'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=30) as x: x.read()
    except urllib.error.HTTPError as e:
        if e.code == 401: _TOKEN['v'] = None
        raise RuntimeError(f'{e.code}: ' + e.read().decode('utf-8', 'replace')[:300])


def _resend(to, subj, html_, text):
    body = json.dumps({'from': f'Alkhabeer Reports <{sender()}>', 'to': to, 'subject': subj, 'html': html_, 'text': text}).encode()
    r = urllib.request.Request('https://api.resend.com/emails', data=body, method='POST',
                               headers={'Authorization': 'Bearer ' + os.environ['RESEND_API_KEY'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=30) as x: x.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{e.code}: ' + e.read().decode('utf-8', 'replace')[:300])


def _mock(to, subj, html_, text):
    d = os.path.join(store.DATA, 'outbox'); os.makedirs(d, exist_ok=True)
    n = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    json.dump({'to': to, 'subject': subj, 'text': text}, open(os.path.join(d, n + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    open(os.path.join(d, n + '.html'), 'w', encoding='utf-8').write(html_)


def _deliver(kind, obj, to, subj, html_, text, actor):
    p = provider(); last = None
    for attempt in range(3):
        try:
            {'m365': _m365, 'smtp': _smtp, 'resend': _resend, 'mock': _mock}[p](to, subj, html_, text)
            A.log(None, 'mail.sent', obj, 'ok', actor=actor, event=kind, to=to, provider=p); return True
        except Exception as e:
            last = str(e)[:300]
            if attempt < 2: threading.Event().wait(3 * (attempt + 1))
    A.log(None, 'mail.sent', obj, 'failed', actor=actor, event=kind, to=to, provider=p, error=last)
    return False


def notify(kind, fund, q, actor, by='', note='', base='', findings=None, exclude=None, to=None, wait=False, by_en=''):
    """Send one alert in the background. `actor` = {'user','role'} for the audit row. Returns the recipients."""
    if not provider(): return []
    if to is None: to = approvers() if kind == 'submitted' else editors()
    to = [x for x in dict.fromkeys(to) if x and x != (exclude or '').lower()]
    if not to: return []
    link = f'{base}/s/{fund}/{q}' if base and fund else base
    subj, html_, text = compose(kind, fund, q, by, note, link, findings, by_en) if fund else compose('test', 'income', 'q1-2026', link=base)
    t = threading.Thread(target=_deliver, args=(kind, f'{fund}:{q}' if fund else 'mail', to, subj, html_, text, actor), daemon=True)
    t.start()
    if wait: t.join(60)
    return to
