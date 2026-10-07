"""Alkhabeer email kit — one design for every email sent for Abdulrahman Baroom.

Why this exists: the Gmail send tool strips the CSS `background:` shorthand, <head>, <style>
and box-shadow. White text on a stripped background turns invisible. Every coloured surface here
uses BOTH the bgcolor attribute and `background-color:`; everything is inline; no <style>.

Usage (python3):
    from alkhabeer_email import *
    html = shell(preheader, [masthead(...), section("...", "today"), card(...), footer()])
    # always send a plain-text `body` too, written by hand in MSA
"""
import html as _h

# ---- tokens (Alkhabeer «ضوء»): navy, light blue, silver, paper. Never green or red. ----
NAVY, NAVY2, NIGHT = "#12284B", "#1B3763", "#071A3A"
BLUE, BLUE_D = "#3B7DD8", "#2E6DB0"
PAPER, WHITE, LINE = "#F5F7FB", "#FFFFFF", "#DCE2EE"
INK, MUTED, SOFT = "#0E1B33", "#5B6885", "#8A94A8"
ON_NAVY, ON_NAVY2 = "#C9D6EE", "#93A6C9"
TONES = {  # urgency / category: (stripe, pill text, pill bg, label)
    "today": ("#B7791F", "#7A4E0E", "#FBF1DF", "اليوم"),
    "week":  (BLUE,      "#1F4F93", "#E6EEFB", "هذا الأسبوع"),
    "info":  ("#9AA5B9", "#4A5670", "#EEF1F6", "للعلم"),
    "done":  (NAVY,      NAVY,      "#E6EBF4", "أُنجز"),
}
FONT = "Tahoma,'Segoe UI',Arial,sans-serif"
MONO = "Menlo,Consolas,'Courier New',monospace"

def e(s): return _h.escape(str(s), quote=True)
def ltr(s): return f'<span dir="ltr">\u2066{e(s)}\u2069</span>'  # phones, licences, IDs, figures: LRI…PDI isolate survives any client

def _bg(c): return f'bgcolor="{c}" style="background-color:{c};'

def shell(preheader, rows, dir="rtl", width=620):
    """Outer frame. rows = list of <tr>…</tr> strings."""
    al = "right" if dir == "rtl" else "left"
    return (f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{e(preheader)}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" {_bg(PAPER)}"><tr><td align="center" style="padding:20px 10px" dir="{dir}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:{width}px;text-align:{al}" dir="{dir}">'
            + "".join(rows) + '</table></td></tr></table>')

def button(label, url, kind="primary", dir="rtl"):
    """kind: primary (blue), navy, ghost (white with navy border). Always readable even if bg is lost."""
    arrow = " ←" if dir == "rtl" else " →"
    if kind == "ghost":
        bg, fg, bd = WHITE, NAVY, NAVY
    elif kind == "navy":
        bg, fg, bd = NAVY, WHITE, NAVY
    else:
        bg, fg, bd = BLUE, WHITE, BLUE
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="display:inline-table"><tr>'
            f'<td {_bg(bg)}border:1px solid {bd};border-radius:8px">'
            f'<a href="{e(url)}" style="display:inline-block;padding:10px 18px;font-family:{FONT};font-size:14px;font-weight:bold;color:{fg};text-decoration:none;background-color:{bg};border-radius:8px">{e(label)}{arrow}</a>'
            f'</td></tr></table>')

def masthead(title, kicker="الخبير المالية · الخدمات المؤسسية", subtitle="", stats=None, cta=None, note=""):
    """Navy band. stats = [(value, label)] up to 4. cta = (label, url)."""
    h = (f'<tr><td {_bg(NAVY)}border-radius:14px;padding:22px 22px 18px 22px;font-family:{FONT}">'
         f'<div style="font-size:12px;color:{ON_NAVY};font-weight:bold;letter-spacing:.2px">{e(kicker)}</div>'
         f'<div style="font-size:26px;font-weight:bold;color:{WHITE};line-height:1.35;padding-top:4px">{e(title)}</div>')
    if subtitle: h += f'<div style="font-size:14px;color:{ON_NAVY};padding-top:4px;line-height:1.7">{subtitle}</div>'
    if stats:
        w = int(100 / len(stats))
        h += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:14px"><tr>'
        for v, lab in stats:
            h += (f'<td width="{w}%" style="padding:3px" valign="top"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
                  f'<td {_bg(NAVY2)}border-radius:10px;padding:10px 12px;font-family:{FONT}">'
                  f'<div dir="ltr" style="font-size:20px;font-weight:bold;color:{WHITE};font-family:{MONO};text-align:right">{e(v)}</div>'
                  f'<div style="font-size:11px;color:{ON_NAVY};line-height:1.5">{e(lab)}</div></td></tr></table></td>')
        h += '</tr></table>'
    if cta: h += f'<div style="padding-top:16px">{button(cta[0], cta[1])}</div>'
    if note: h += f'<div style="font-size:12px;color:{ON_NAVY2};padding-top:10px;line-height:1.7">{e(note)}</div>'
    return h + '</td></tr>'

def gap(px=14): return f'<tr><td style="height:{px}px;font-size:0;line-height:0">&nbsp;</td></tr>'

def section(label, tone="info"):
    c = TONES.get(tone, TONES["info"])[1] if tone != "info" else NAVY
    return f'<tr><td style="font-family:{FONT};font-size:13px;font-weight:bold;color:{c};padding:16px 4px 8px 4px">{e(label)}</td></tr>'

def _box(inner, stripe=None, pad="14px 16px"):
    s = (f'<td width="4" {_bg(stripe)}font-size:0;line-height:0">&nbsp;</td>' if stripe else '')
    return (f'<tr><td style="padding:0 0 10px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" {_bg(WHITE)}border:1px solid {LINE};border-radius:12px;border-collapse:separate"><tr>'
            f'{s}<td style="padding:{pad};font-family:{FONT}">{inner}</td></tr></table></td></tr>')

def card(title, detail, tone="today", tag=None, owner=None, btn=None):
    """Decision/item card. btn = (label, url). detail may contain ltr() spans (pre-escaped HTML)."""
    stripe, pt, pb, lab = TONES.get(tone, TONES["info"])
    inner = (f'<span style="display:inline-block;background-color:{pb};color:{pt};font-size:11px;font-weight:bold;padding:2px 10px;border-radius:10px">{e(tag or lab)}</span>'
             f'<div style="font-size:16px;font-weight:bold;color:{INK};line-height:1.5;padding:6px 0 4px 0">{e(title)}</div>'
             f'<div style="font-size:14px;color:{MUTED};line-height:1.8">{detail}</div>')
    if owner or btn:
        inner += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:10px"><tr>'
        inner += f'<td style="font-family:{FONT};font-size:12px;color:{MUTED}">{"المسؤول: <b style=\"color:"+INK+"\">"+e(owner)+"</b>" if owner else ""}</td>'
        if btn: inner += f'<td align="left" style="text-align:left">{button(btn[0], btn[1], "navy" if tone == "today" else "ghost")}</td>'
        inner += '</tr></table>'
    return _box(inner, stripe)

def bullets(items, title=None):
    li = "".join(f'<tr><td valign="top" style="width:14px;color:{BLUE};font-family:{FONT};font-size:14px;line-height:1.8">•</td><td style="font-family:{FONT};font-size:14px;color:{INK};line-height:1.8">{x}</td></tr>' for x in items)
    head = f'<div style="font-size:13px;font-weight:bold;color:{NAVY};padding-bottom:4px">{e(title)}</div>' if title else ""
    return _box(head + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{li}</table>')

def note(text_html, label="ملاحظة"):
    """Light-blue callout, e.g. forwarding instructions («احذف هذا الإطار قبل التحويل»)."""
    return (f'<tr><td style="padding:0 0 12px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" {_bg("#E6EEFB")}border-radius:10px"><tr>'
            f'<td width="4" {_bg(NAVY)}font-size:0;line-height:0">&nbsp;</td>'
            f'<td style="padding:10px 14px;font-family:{FONT};font-size:13px;color:{NAVY};line-height:1.8"><b>{e(label)}</b><br>{text_html}</td></tr></table></td></tr>')

def letter(paragraphs_html, signature=("عبدالرحمن باروم", "مدير إدارة خدمات الشركات", "شركة الخبير المالية")):
    """Formal letter body: white sheet, generous line height, signature block. paragraphs_html = list of HTML strings."""
    body = "".join(p if p.lstrip().startswith("<table") else f'<p style="margin:0 0 12px 0;font-family:{FONT};font-size:15px;color:{INK};line-height:1.9">{p}</p>' for p in paragraphs_html)  # pass answer_form(...) as its own item, never inside a <p>
    sig = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:8px"><tr><td width="3" {_bg(BLUE)}font-size:0">&nbsp;</td>'
           f'<td style="padding:2px 12px;font-family:{FONT};font-size:14px;color:{INK};line-height:1.7"><b>{e(signature[0])}</b><br><span style="color:{MUTED}">{e(signature[1])}<br>{e(signature[2])}</span></td></tr></table>')
    return _box(body + sig, None, "22px 24px")

def answer_form(lines):
    """Reply template inside a letter: list of strings, shown as a light ruled block."""
    rows = "".join(f'<tr><td style="padding:6px 0;border-bottom:1px solid {LINE};font-family:{FONT};font-size:14px;color:{INK};line-height:1.7">{x}</td></tr>' for x in lines)
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" {_bg(PAPER)}border-radius:8px;margin:4px 0 12px 0"><tr><td style="padding:8px 14px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table></td></tr></table>'

def footer(text="أعدّه Claude لعبدالرحمن باروم", sub=""):
    return (f'<tr><td style="font-family:{FONT};font-size:12px;color:{SOFT};text-align:center;padding:14px 8px;line-height:1.7">'
            f'{e(sub)+"<br>" if sub else ""}الخبير المالية · ترخيص هيئة السوق المالية {ltr("07074-37")}<br>{e(text)}</td></tr>')

def letterhead(kind_label="مراسلة رسمية"):
    """Slim navy band for formal letters (no counters)."""
    return (f'<tr><td {_bg(NAVY)}border-radius:12px;padding:14px 22px;font-family:{FONT}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td style="font-size:17px;font-weight:bold;color:{WHITE};white-space:nowrap">الخبير المالية<div dir="ltr" style="font-size:11px;color:{ON_NAVY};font-weight:normal;text-align:right">Alkhabeer Capital</div></td>'
            f'<td align="left" style="text-align:left;font-size:12px;color:{ON_NAVY};line-height:1.6">{e(kind_label)}</td></tr></table></td></tr>')
