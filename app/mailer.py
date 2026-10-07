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

import email_kit as K

DISCLAIMER_AR = ('صدرت هذه الرسالة آليًا من منصة البيانات الربعية، وهي نظام تجريبي في مرحلة التطوير، '
                 'ومخصّصة للاستخدام الداخلي في شركة الخبير المالية فقط. لا تُعدّ مستندًا رسميًا، ولا يُردّ عليها.')
DISCLAIMER_EN = ('Sent automatically by the quarterly statements platform, a pilot system under development, '
                 'for internal use at Alkhabeer Capital only. It is not an official document; please do not reply.')


def _facts(rows):
    """Two-column fact table: label · value."""
    tr = ''.join(f'<tr><td style="padding:7px 0;border-bottom:1px solid {K.LINE};font-family:{K.FONT};font-size:13px;color:{K.MUTED};width:34%;vertical-align:top">{K.e(k)}</td>'
                 f'<td style="padding:7px 0;border-bottom:1px solid {K.LINE};font-family:{K.FONT};font-size:15px;color:{K.INK};font-weight:bold;line-height:1.6">{v}</td></tr>' for k, v in rows)
    return K._box(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{tr}</table>', None, '8px 18px')


def _quote(label, text):
    return K.note(K.e(text), label)


def _english(title, lines):
    """English summary: its own white box, left to right."""
    body = ''.join(f'<p style="margin:0 0 6px 0;font-family:{K.FONT};font-size:13px;color:{K.MUTED};line-height:1.7">{x}</p>' for x in lines)
    return (f'<tr><td style="padding:0 0 10px 0" dir="ltr" align="left"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{K.WHITE}" style="background-color:{K.WHITE};border:1px solid {K.LINE};border-radius:12px"><tr><td dir="ltr" style="padding:12px 16px;text-align:left;font-family:{K.FONT}">'
            f'<div style="font-size:11px;font-weight:bold;color:{K.SOFT};letter-spacing:.4px;padding-bottom:4px">ENGLISH SUMMARY</div>'
            f'<div style="font-size:14px;font-weight:bold;color:{K.INK};padding-bottom:4px">{K.e(title)}</div>{body}</td></tr></table></td></tr>')


def _disclaimer():
    return (f'<tr><td style="padding:4px 0 0 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#EEF1F6" style="background-color:#EEF1F6;border-radius:10px"><tr>'
            f'<td style="padding:12px 16px;font-family:{K.FONT};font-size:12px;color:#4A5670;line-height:1.8"><b>إخلاء مسؤولية:</b> {K.e(DISCLAIMER_AR)}'
            f'<div dir="ltr" style="text-align:left;padding-top:6px;color:{K.SOFT}">{K.e(DISCLAIMER_EN)}</div></td></tr></table></td></tr>')


def compose(kind, fund, q, by='', note='', link='', findings=None, by_en='', at=''):
    """(subject, html, text) for one alert, in the Alkhabeer «ضوء» e-mail design."""
    e = K.e
    by_en = by_en or ('The approver' if kind in ('returned', 'final') else 'A data-entry user')
    F = M.FUNDS[fund]; fa, fe = F['ar'], F['en']; qa, qe = M.qlabel(q, 'ar'), M.qlabel(q, 'en')
    at = at or store.now()
    facts = [('الصندوق', e(fa)), ('الفترة', e(qa))]
    extra = []
    if kind == 'submitted':
        title, sub = 'بيان بانتظار اعتمادك', 'رُفعت مسودة البيان الربعي للاعتماد. راجعها واعتمدها أو أعدها للتعديل.'
        facts += [('رفعه', e(by)), ('وقت الرفع', K.ltr(at))]
        if findings is not None:
            facts.append(('المقارنة بالربع السابق', f'{K.ltr(findings)} ملاحظة تحتاج مراجعة' if findings else 'لا ملاحظات'))
        btn = 'مراجعة البيان'; subj = f'بانتظار اعتمادك: {fa} — {qa}'
        en = (f'Awaiting your approval — {fe}, {qe}', [f'{e(by_en)} submitted the {e(qe)} quarterly statement for approval.'])
    elif kind == 'returned':
        title, sub = 'أُعيد البيان للتعديل', 'أعاد المعتمِد البيان للتعديل. عدّل ما يلزم، ثم أصدر المسودة وارفعها مرة أخرى.'
        facts += [('أعاده', e(by)), ('الوقت', K.ltr(at))]
        if note: extra.append(_quote('ملاحظة المعتمِد', note))
        btn = 'فتح البيان'; subj = f'أُعيد للتعديل: {fa} — {qa}'
        en = (f'Returned for changes — {fe}, {qe}', [f'{e(by_en)} returned the {e(qe)} quarterly statement for changes.'] + ([f'Note: “{e(note)}”'] if note else []))
    elif kind == 'final':
        title, sub = 'اعتُمد البيان', 'اعتُمدت النسخة النهائية، والملفات العربية والإنجليزية جاهزة للتنزيل.'
        facts += [('اعتمده', e(by)), ('وقت الاعتماد', K.ltr(at))]
        btn = 'تنزيل الملفات'; subj = f'اعتُمد: {fa} — {qa}'
        en = (f'Approved — {fe}, {qe}', [f'{e(by_en)} approved the final {e(qe)} quarterly statement. The Arabic and English files are ready.'])
    else:   # test
        title, sub = 'رسالة تجريبية', 'وصلتك هذه الرسالة لأن تنبيهات البريد مفعّلة في منصة البيانات الربعية.'
        facts = [('المرسِل', K.ltr(sender())), ('الوقت', K.ltr(at))]
        btn = 'فتح المنصة'; subj = 'رسالة تجريبية من منصة البيانات الربعية'
        en = ('Test message', ['You received this because e-mail alerts are set up on the quarterly statements platform.'])
    rows = [K.masthead(title, kicker='الخبير المالية · منصة البيانات الربعية', subtitle=e(sub), cta=(btn, link) if link else None),
            K.gap(12), _facts(facts), *extra, _english(*en), _disclaimer(),
            K.footer('رسالة آلية من منصة البيانات الربعية')]
    html_ = K.shell(f'{title} — {fa if kind != "test" else ""} {qa if kind != "test" else ""}'.strip(' —'), rows)
    strip = lambda x: __import__('re').sub('<[^>]+>', '', H.unescape(x)).replace('\u2066', '').replace('\u2069', '')
    text = '\n'.join([title, sub, ''] + [f'{k}: {strip(v)}' for k, v in facts] + ([f'ملاحظة المعتمِد: {note}'] if kind == 'returned' and note else [])
                     + ['', link, '', en[0], *map(strip, en[1]), '', 'إخلاء مسؤولية: ' + DISCLAIMER_AR, DISCLAIMER_EN])
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
