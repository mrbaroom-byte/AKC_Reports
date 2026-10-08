"""Typeset Alkhabeer Diversified Income Traded Fund 2030 documents in the «الإشارة» (Signal) identity.
Usage: python3 render.py <id> <lang> [<id> <lang> ...]   → out/html/<id>.<lang>.html, then shot via pdf.js → out/pdf/"""
import json, os, sys, re, math, html, subprocess, glob
import props as PROPS_MOD
PROPS = []
CODE = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(CODE)
B = os.path.abspath(os.environ.get("FUND_DIR") or CODE)  # fund folder: struct/, out/, graphics/figures/, fund.json
CFG = json.load(open(os.path.join(B, "fund.json"), encoding="utf-8")) if os.path.exists(os.path.join(B, "fund.json")) else {}
OUT = os.path.join(B, "out"); os.makedirs(OUT + "/html", exist_ok=True); os.makedirs(OUT + "/pdf", exist_ok=True); os.makedirs(OUT + "/orig", exist_ok=True)
DOCS = CFG.get("docs") or json.load(open(os.path.join(B, "docs2.json")))
SRCPDF = {(d["id"], d["side"].lower()): os.path.join(B, d["file"]) for d in DOCS}
NAVY, NIGHT, ELEC, SKY, PAPER, INK, MUT, LINE = "#12284B", "#071A3A", "#3B7DD8", "#9DB8E0", "#F3F6FB", "#0B1733", "#5A6478", "#DCE3EE"
PAL = ["#12284B", "#3B7DD8", "#9DB8E0", "#5F64C4", "#7A8CA8", "#C9D6EE", "#2E6DB0", "#B9C3D6", "#4B5E80", "#DCE3EE"]
# Asset-class colour (library «ألوان الفئات»): capital markets = blue #3B7DD8 (default), real estate = bronze #9A6A45,
# private equity = #5F64C4. A fund's fund.json sets "accent", "accent_light" and "palette"; the whole document is recoloured.
LOGO_W = "file://" + os.path.join(R, "brand", "akc-logo-white.svg")
LOGO_C = "file://" + os.path.join(R, "brand", "akc-logo-color.svg")
FLOGO_W = "file://" + (os.path.join(B, CFG["logo_white"]) if CFG.get("logo_white") else os.path.join(R, "fundlogo", "dif2030-logo-white.svg"))
ART = {"cover": "file://" + os.path.join(R, "fundlogo", "cover-art.jpg"), "band": "file://" + os.path.join(R, "id4", "img", "b-kv.jpg")}
if CFG.get("cover_art"): ART["cover"] = "file://" + os.path.join(B, CFG["cover_art"])
FUND = CFG.get("fund") or {"ar": "صندوق الخبير للدخل المتنوع 2030 المتداول", "en": "Alkhabeer Diversified Income Traded Fund 2030"}
ACC = CFG.get("accent", "#3B7DD8"); ACC_L = CFG.get("accent_light", "#9DB8E0")
if CFG.get("palette"): PAL = CFG["palette"]
ELEC = ACC
_CO = ' dir="ltr" class="co"'
_NUMRE = r"[\s\d.,%()\-+*ر.س SAR]+"


def _hid(b):
    return (' id="' + str(b["hid"]) + '"') if b.get("hid") else ""


def _tag(tag):
    return ('<div class="tag">' + e(tag) + '</div>') if tag else ""


def _numcls(c):
    s = str(c or "")
    return "num" if re.fullmatch(_NUMRE, s) and re.search(r"\d", s) else ""


def recolour(h):
    if ACC == "#3B7DD8": return h
    lr = tuple(int(ACC_L[i:i + 2], 16) for i in (1, 3, 5))
    h = (h.replace("#3B7DD8", ACC).replace("#3b7dd8", ACC).replace("#9DB8E0", ACC_L).replace("#9db8e0", ACC_L)
             .replace("rgba(157,184,224", "rgba(%d,%d,%d" % lr))
    for a, b in CFG.get("recolour", {}).items(): h = h.replace(a, b).replace(a.lower(), b)
    return h
EYB = CFG.get("eyebrow") or {"ar": "صندوق استثمار عام مقفل متداول", "en": "Closed-ended Traded Public Investment Fund"}
QN = {"1": ("الأول", "Q1"), "2": ("الثاني", "Q2"), "3": ("الثالث", "Q3"), "4": ("الرابع", "Q4")}
def meta(i, lang):
    ar = lang == "ar"
    T = {"tc": ("الشروط والأحكام", "Terms and Conditions", "تحديث سبتمبر 2025م", "Updated September 2025", "full"),
         "exec": ("الملخص التنفيذي", "Executive Summary", "", "", "full"),
         "factsheet": ("ورقة الحقائق", "Fact Sheet", "", "", "full"),
         "faq": ("الأسئلة الشائعة", "Frequently Asked Questions", "", "", "full"),
         "voting": ("سياسة حقوق التصويت", "Voting Rights Policy", "نوفمبر 2025م", "November 2025", "full"),
         "annual-2024": ("التقرير السنوي", "Annual Report", "2024م", "2024", "full"),
         "annual-2025": ("التقرير السنوي", "Annual Report", "2025م", "2025", "full")}
    T.update({k: tuple(v) for k, v in CFG.get("meta", {}).items()})
    if CFG and i not in CFG.get("meta", {}): T = {k: v for k, v in T.items() if k in CFG.get("meta", {})}
    if i in T:
        a, e, da, de, kind = T[i]; return (a if ar else e), (da if ar else de), kind
    m = re.match(r"annual-(\d{4})$", i)
    if m: return ("التقرير السنوي" if ar else "Annual Report"), (f"{m.group(1)}م" if ar else m.group(1)), "full"
    m = re.match(r"q(\d)-(\d{4})", i)
    if m:
        q, y = m.groups()
        return ("البيان الربع سنوي" if ar else "Quarterly Statement"), (f"الربع {QN[q][0]} {y}م" if ar else f"{QN[q][1]} {y}"), "band"
    return i, "", "full"
TN = re.compile(r"\s*\[TRANSLATOR NOTE:[^\]]*\]")
INLINE_TN = []
def e(s):
    s = str(s if s is not None else "")
    for m in TN.findall(s): INLINE_TN.append(m.strip())
    return html.escape(TN.sub("", s))
def txt(s):  # paragraphs with line breaks; inline translator notes go to the review list, not the document
    s = str(s or "")
    for m in TN.findall(s): INLINE_TN.append(m.strip())
    s = TN.sub("", s)
    return "<br>".join(e(x) for x in str(s or "").split("\n"))

# Phone numbers: normalise format and isolate as LTR so they never flip inside Arabic text
_TEL = re.compile(r"(?<![\d/])(?:\+?\s?966\s?9200\s?\d{2}\s?\d{3}|\+?\s?966[\s\-\u2013]*(?:\(?0?\)?)?\d{1,2}[\s\-]*\d{3}[\s\-]*\d{4}|800[\s\-]?\d{3}[\s\-]?\d{4}|920[\s\-]?\d{3}[\s\-]?\d{3}|\b0?1[1-7] \d{3} \d{4})(?![\d])")
def _telfmt(m):
    d = re.sub(r"\D", "", m.group(0))
    if d.startswith("9669200") and len(d) == 12:
        n = f"+966 9200 {d[7:9]} {d[9:]}"
    elif d.startswith("966"):
        r = d[3:].lstrip("0")
        n = f"+966 {r[:-7]} {r[-7:-4]} {r[-4:]}"
    elif d[0] in "01" and len(d) <= 10:
        r = d.lstrip("0"); n = f"+966 {r[:-7]} {r[-7:-4]} {r[-4:]}"
    elif d.startswith("800"): n = f"{d[:3]} {d[3:6]} {d[6:]}"
    else: n = f"{d[:3]} {d[3:6]} {d[6:]}"
    return f'<bdi class="tel" dir="ltr">{n}</bdi>'
def tels(h):
    h = re.sub(r"(\d{4}) (\d{3}) 966-(\d{1,2})\+", r"+966 \3 \2 \1", h)  # numbers stored reversed in the source PDF
    h = h.replace("+966 12 658 3666", "+966 12 658 6663")  # typo in the Arabic T&C; the fax is 6663 in every other document
    return "".join(seg if seg.startswith("<") else _TEL.sub(_telfmt, _arnums(seg)) for seg in re.split(r"(<[^>]+>)", h))
_AW = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def _arnums(t):
    """Arabic-Indic digit groups joined by spaces/hyphens/slashes (phones, licence and CR numbers) are bidi 'AN' runs that
    the Arabic paragraph reorders right-to-left («+٩٦٦ ١٢ ٦٥٨ ٨٨٨٨» shows as «٨٨٨٨ ٦٥٨ ١٢ ٩٦٦+»). Phones become Western digits
    so the phone formatter normalises them; other grouped numbers are isolated left-to-right."""
    t = re.sub(r"\+?[٠-٩][٠-٩ \-]{6,}[٠-٩]", lambda m: m.group(0).translate(_AW) if re.match(r"\+?(٩٦٦|٨٠٠|٩٢٠|٠٥)", m.group(0)) else m.group(0), t)
    return re.sub(r"[٠-٩]+(?:[\-/][٠-٩]+)+|[٠-٩]+(?: [٠-٩]+)+", lambda m: f'<bdo dir="ltr">{m.group(0)}</bdo>', t)  # override: an LTR isolate alone still flips «٠٧٠٧٤-٣٧»
def num_fmt(v, unit, ar):
    if v is None: return ""
    s = f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.0f}"
    return (s + "%") if unit == "%" else s

# ---------- charts ----------
def _split_groups(ser):
    """Multi-series charts carry a "group" key. Whichever of label/group has fewer distinct values is the series;
    the other is the category axis. Returns (categories, series names, {(cat, ser): value})."""
    labs = list(dict.fromkeys(str(s.get("label")) for s in ser)); grps = list(dict.fromkeys(str(s.get("group")) for s in ser))
    if len(grps) <= len(labs): cats, names, ck, sk = labs, grps, "label", "group"
    else: cats, names, ck, sk = grps, labs, "group", "label"
    return cats, names, {(str(s.get(ck)), str(s.get(sk))): s.get("value") for s in ser}
def chart(b, ar):
    kind, ser, unit = b.get("kind"), b.get("series") or [], b.get("unit", "")
    if kind in ("bar", "line") and any("group" in s for s in ser) and len({str(s.get("group")) for s in ser}) > 1:
        return chart_multi(b, ar)
    title = f'<div class="ct">{e(b.get("title",""))}</div>' if b.get("title") else ""
    vals = [s.get("value") for s in ser]
    if not ser or all(v is None for v in vals):
        return ""  # nothing measurable → omit rather than draw a fake chart
    if kind == "pie":
        tot = sum(v or 0 for v in vals) or 1; a0 = -90; segs = []; leg = []
        for k, s in enumerate(ser):
            v = s.get("value") or 0; ang = v / tot * 360; c = PAL[k % len(PAL)]
            if ang >= 359.9: segs.append(f'<circle cx="90" cy="90" r="70" fill="none" stroke="{c}" stroke-width="34"/>')
            elif ang > 0:
                a1 = a0 + ang; la = 1 if ang > 180 else 0
                p = lambda a: (90 + 70 * math.cos(math.radians(a)), 90 + 70 * math.sin(math.radians(a)))
                (x0, y0), (x1, y1) = p(a0), p(a1)
                segs.append(f'<path d="M{x0:.2f},{y0:.2f} A70,70 0 {la} 1 {x1:.2f},{y1:.2f}" fill="none" stroke="{c}" stroke-width="34"/>')
            a0 += ang
            leg.append(f'<div class="lg"><i style="background:{c}"></i><span class="ll">{e(s.get("label"))}</span><b class="num">{num_fmt(s.get("value"), unit, ar)}</b></div>')
        return f'<figure class="chart pie">{title}<div class="pw"><svg viewBox="0 0 180 180" width="150" height="150">{"".join(segs)}</svg><div class="legend">{"".join(leg)}</div></div></figure>'
    if kind == "bar":
        mx = max(abs(v) for v in vals if v is not None) or 1
        rows = "".join(f'<div class="br"><span class="bl">{e(s.get("label"))}</span><span class="bt"><i style="width:{max(1.5,(s.get("value") or 0)/mx*100):.1f}%"></i></span><b class="num">{num_fmt(s.get("value"), unit, ar)}</b></div>' for s in ser)
        dg = '<div class="cap">قيم تقريبية مقاسة من الرسم الأصلي</div>' if b.get("digitized") and ar else ('<div class="cap">Approximate values measured from the original chart</div>' if b.get("digitized") else "")
        return f'<figure class="chart bars">{title}{rows}{dg}</figure>'
    if kind == "line":
        pts = [(s.get("label"), s.get("value")) for s in ser if s.get("value") is not None]
        if len(pts) < 2: return ""
        W, H, L, Rr, T, Bm = 640, 230, 46, 12, 12, 34
        ys = [v for _, v in pts]; lo, hi = min(ys), max(ys); pad = (hi - lo) * 0.12 or 0.5; lo -= pad; hi += pad
        step = 10 ** math.floor(math.log10((hi - lo) / 4));
        for m in (1, 2, 2.5, 5, 10):
            if (hi - lo) / (step * m) <= 5: step *= m; break
        X = lambda k: L + (W - L - Rr) * k / (len(pts) - 1)
        Y = lambda v: T + (H - T - Bm) * (1 - (v - lo) / (hi - lo))
        grid = []; t = math.ceil(lo / step) * step
        while t <= hi:
            grid.append(f'<line x1="{L}" x2="{W-Rr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{LINE}" stroke-width="1"/><text x="{L-6}" y="{Y(t)+3.5:.1f}" text-anchor="end" font-size="10" fill="{MUT}">{t:.2f}{"%" if unit=="%" else ""}</text>'); t += step
        d = " ".join(f"{X(k):.1f},{Y(v):.1f}" for k, (_, v) in enumerate(pts))
        area = f'<polygon points="{X(0):.1f},{H-Bm} {d} {X(len(pts)-1):.1f},{H-Bm}" fill="{ELEC}" fill-opacity=".10"/>'
        nl = 5; labs = []
        for j in range(nl):
            k = round(j * (len(pts) - 1) / (nl - 1)); lab = str(pts[k][0])
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lab)
            if m: lab = f"{int(m.group(3))}/{int(m.group(2))}/{m.group(1)}"
            labs.append(f'<text x="{X(k):.1f}" y="{H-12}" text-anchor="middle" font-size="10" fill="{MUT}">{e(lab)}</text>')
        end = f'<circle cx="{X(len(pts)-1):.1f}" cy="{Y(pts[-1][1]):.1f}" r="3.5" fill="{NAVY}"/>'
        dg = ('<div class="cap">منحنى تقريبي مُعاد رسمه من الرسم الأصلي</div>' if ar else '<div class="cap">Approximate curve redrawn from the original chart</div>') if b.get("digitized") else ""
        return f'<figure class="chart line">{title}<svg viewBox="0 0 {W} {H}" width="100%" direction="ltr" style="direction:ltr">{"".join(grid)}{area}<polyline points="{d}" fill="none" stroke="{NAVY}" stroke-width="2"/>{end}{"".join(labs)}</svg>{dg}</figure>'
    return ""

def chart_multi(b, ar):
    kind, unit = b.get("kind"), b.get("unit", ""); cats, names, V = _split_groups(b["series"])
    title = f'<div class="ct">{e(b.get("title",""))}</div>' if b.get("title") else ""
    col = {n: PAL[k % len(PAL)] for k, n in enumerate(names)}
    leg = '<div class="mleg">' + "".join(f'<span><i style="background:{col[n]}"></i>{e(n)}</span>' for n in names) + "</div>"
    dg = ""
    if b.get("digitized") or any(s.get("measured") for s in b["series"]):
        dg = '<div class="cap">قيم تقريبية مقاسة من الرسم الأصلي</div>' if ar else '<div class="cap">Approximate values measured from the original chart</div>'
    vals = [v for v in V.values() if isinstance(v, (int, float))]
    if not vals: return ""
    if kind == "bar":  # grouped columns (compact even with many dates)
        W, H, L, Rr, T, Bm = 640, 230, 46, 10, 16, 40
        lo = min(0, min(vals)); hi = max(0, max(vals)) * 1.08 or 1
        Y = lambda v: T + (H - T - Bm) * (1 - (v - lo) / (hi - lo))
        n = len(cats); gw = (W - L - Rr) / n; bw = min(22, gw * .8 / len(names)); out = []
        step = 10 ** math.floor(math.log10((hi - lo) / 4 or 1))
        for m in (1, 2, 2.5, 5, 10):
            if (hi - lo) / (step * m) <= 5: step *= m; break
        t = math.ceil(lo / step) * step
        while t <= hi:
            out.append(f'<line x1="{L}" x2="{W-Rr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{LINE}" stroke-width="1"/><text x="{L-6}" y="{Y(t)+3.5:.1f}" text-anchor="end" font-size="10" fill="{MUT}">{t:g}{"%" if unit=="%" else ""}</text>'); t += step
        show_vals = n * len(names) <= 14; every = max(1, math.ceil(n / 8))
        for k, c in enumerate(cats):
            x0 = L + gw * k + (gw - bw * len(names)) / 2
            for j, nm in enumerate(names):
                v = V.get((c, nm))
                if not isinstance(v, (int, float)): continue
                y = Y(max(v, 0)); h = abs(Y(v) - Y(0))
                out.append(f'<rect x="{x0 + j*bw:.1f}" y="{min(Y(v), Y(0)):.1f}" width="{bw-1.2:.1f}" height="{max(h,.8):.1f}" rx="1" fill="{col[nm]}"/>')
                if show_vals: out.append(f'<text x="{x0 + j*bw + bw/2:.1f}" y="{min(Y(v), Y(0)) - 3:.1f}" text-anchor="middle" font-size="8.5" fill="{INK}">{num_fmt(v, "", ar)}</text>')
            if k % every == 0: out.append(f'<text x="{L + gw*k + gw/2:.1f}" y="{H-Bm+14}" text-anchor="middle" font-size="9" fill="{MUT}">{e(c)}</text>')
        return f'<figure class="chart line">{title}{leg}<svg viewBox="0 0 {W} {H}" width="100%" style="direction:ltr">{"".join(out)}</svg>{dg}</figure>'
    W, H, L, Rr, T, Bm = 640, 240, 50, 14, 12, 34
    lo, hi = min(vals), max(vals); pad = (hi - lo) * 0.12 or 0.5; lo -= pad; hi += pad
    step = 10 ** math.floor(math.log10((hi - lo) / 4))
    for m in (1, 2, 2.5, 5, 10):
        if (hi - lo) / (step * m) <= 5: step *= m; break
    n = len(cats); X = lambda k: L + (W - L - Rr) * k / max(1, n - 1); Y = lambda v: T + (H - T - Bm) * (1 - (v - lo) / (hi - lo))
    grid = []; t = math.ceil(lo / step) * step
    while t <= hi:
        grid.append(f'<line x1="{L}" x2="{W-Rr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{LINE}" stroke-width="1"/><text x="{L-6}" y="{Y(t)+3.5:.1f}" text-anchor="end" font-size="10" fill="{MUT}">{t:g}{"%" if unit=="%" else ""}</text>'); t += step
    lines = []
    for nm in names:
        pts = [(X(k), Y(V[(c, nm)])) for k, c in enumerate(cats) if isinstance(V.get((c, nm)), (int, float))]
        if len(pts) >= 2: lines.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{col[nm]}" stroke-width="2"/>')
    nl = min(5, n); labs = []
    for j in range(nl):
        k = round(j * (n - 1) / max(1, nl - 1))
        labs.append(f'<text x="{X(k):.1f}" y="{H-12}" text-anchor="middle" font-size="10" fill="{MUT}">{e(cats[k])}</text>')
    return f'<figure class="chart line">{title}{leg}<svg viewBox="0 0 {W} {H}" width="100%" style="direction:ltr">{"".join(grid)}{"".join(lines)}{"".join(labs)}</svg>{dg}</figure>'

# ---------- original pages ----------
def originals(i, lang, a, z):
    src = SRCPDF.get((i, lang))
    d = os.path.join(OUT, "orig", f"{i}.{lang}"); os.makedirs(d, exist_ok=True)
    out = []
    for p in range(a, z + 1):
        f = os.path.join(d, f"p{p:03d}.jpg")
        if not os.path.exists(f):
            subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-r", str(CFG.get("orig_dpi", 150)), "-jpeg", "-jpegopt", f"quality={CFG.get('orig_q', 85)},optimize=y", "-singlefile", src, f[:-4]], check=True)
        out.append(f'<div class="orig"><div id="op-{p}" style="height:.2mm"></div><img src="file://{f}"></div>')
    return "".join(out)

# ---------- partners (logo grids) — registry read at render time ----------
_REG = None
def registry():
    """Load graphics/registry/partners.json once per run; every partners block resolves names/logos from it."""
    global _REG
    if _REG is None:
        _REG = {p["slug"]: p for p in json.load(open(os.path.join(CODE, "graphics", "registry", "partners.json"), encoding="utf-8"))}
    return _REG
def _px(path):  # native pixel size of a PNG/JPEG (no PIL dependency); None for SVG/unknown
    try:
        with open(path, "rb") as f: h = f.read(64 * 1024)
        if h[:8] == b"\x89PNG\r\n\x1a\n": import struct; return struct.unpack(">II", h[16:24])
        if h[:2] == b"\xff\xd8":
            import struct; k = 2
            while k < len(h) - 9:
                if h[k] != 0xFF: k += 1; continue
                m = h[k + 1]
                if m in (0xC0, 0xC1, 0xC2): hh, ww = struct.unpack(">HH", h[k + 5:k + 9]); return ww, hh
                k += 2 + struct.unpack(">H", h[k + 2:k + 4])[0]
    except OSError: pass
    return None
def partner_logo(p):
    if p["slug"] == "alkhabeer-capital": return os.path.join(R, "brand", "akc-logo-color.svg")  # official vector
    f = p.get("logo")
    f = os.path.join(CODE, "graphics", "registry", "logos", f) if f else ""
    return f if f and os.path.exists(f) else None
def partners(b, ar):
    reg = registry(); lang = "ar" if ar else "en"; show = b.get("show", "logo+name")
    MAXH, PXMM = 12.0, 25.4 / 300 * 1.4  # 12mm box; never more than 1.4x native size at 300 dpi
    out = []
    for g in b.get("groups", []):
        title = g.get(f"title_{lang}") or ""
        cards = []
        for it in g.get("items", []):
            p = reg.get(it["slug"])
            if p is None: cards.append(f'<div class="pc miss">{e(it["slug"])}</div>'); continue
            role = it.get(f"role_{lang}") or ""
            src = partner_logo(p); logo = ""
            if src:
                sz = _px(src); st = f"max-height:{MAXH}mm"
                if sz: st = f"max-height:{min(MAXH, sz[1] * PXMM):.2f}mm;max-width:min(100%,{sz[0] * PXMM:.2f}mm)"
                logo = f'<div class="pl"><img data-p="{e(p["slug"])}" src="file://{src}" style="{st}" alt="{e(p.get("name_" + lang))}"></div>'
            else: logo = '<div class="pl"></div>'
            name = f'<div class="pn" data-p="{e(p["slug"])}" data-f="name_{lang}">{e(p.get("name_" + lang))}</div>' if show in ("logo+name", "card") or not src else ""
            extra = ""
            if show == "card":
                rows = []
                if p.get(f"address_{lang}"): rows.append(f'<div data-p="{e(p["slug"])}" data-f="address_{lang}">{e(p["address_" + lang])}</div>')
                if p.get("website"): rows.append(f'<div><bdi dir="ltr" data-p="{e(p["slug"])}" data-f="website">{e(p["website"])}</bdi></div>')
                if p.get("tollfree"): rows.append(f'<div>{"الرقم المجاني" if ar else "Toll-free"}: <bdi dir="ltr" data-p="{e(p["slug"])}" data-f="tollfree">{e(p["tollfree"])}</bdi></div>')
                extra = f'<div class="pd">{"".join(rows)}</div>' if rows else ""
            cards.append(f'<div class="pc">{f"<div class=pr>{e(role)}</div>" if role else ""}{logo}{name}{extra}</div>')
        cols = g.get("cols") or (3 if show == "card" else 4)
        out.append(f'<div class="pg">{f"<h2>{e(title)}</h2>" if title else ""}<div class="pgrid c{cols}">{"".join(cards)}</div></div>')
    return f'<div class="partners">{"".join(out)}</div>'

TOC = re.compile(r'(جدول المحتويات|^المحتويات|^الفهرس|table of contents?|^contents|^index)', re.I)
def _nt(x):  # normalise a title for matching TOC entries to headings
    x = re.sub(r"[\u064B-\u0652\u0640]", "", str(x or "")).strip().lower()
    x = re.sub(r"^(?:\(?[0-9a-z\u0621-\u064a]{1,2}\s?[).\-–]\s*)+", "", x)  # list markers: (أ) 4) 1. a) (هـ)
    x = x.translate(str.maketrans("أإآىة", "اااىه"))
    return re.sub(r"[^\w]+", "", x)
TOCPAGES = {}
for _f in glob.glob(os.path.join(OUT, "toc", "*.json")):
    _d, _l = os.path.basename(_f)[:-5].rsplit(".", 1); TOCPAGES[(_d, _l)] = json.load(open(_f))
def build_toc(blocks, pre="h"):
    """House rule: the table of contents always starts on a new page and shows the page numbers of THIS document.
    TOC tables become {"t":"toc"} blocks whose entries link to the matching heading (or paragraph); page numbers come
    from a first PDF pass (out/toc/<doc>.<lang>.json, written by toc.py)."""
    import difflib
    blocks = [dict(b) for b in blocks]; arm = None
    for k, b in enumerate(blocks):
        if b["t"] in ("h1", "h2", "h3"):
            arm = k if TOC.search(b.get("text", "").strip()) else None
            if arm is not None: b["toc_head"] = True
            continue
        if b["t"] in ("table", "kv") and (arm is not None or TOC.search((b.get("caption") or "").strip())):
            rows = b.get("rows", []); nc = max((len(r) for r in rows), default=0)
            isnum = lambda c: re.fullmatch(r"[\s\d\-–]*", str(c or "")) is not None
            keep = [c for c in range(nc) if not all(isnum(r[c]) if c < len(r) else True for r in rows)]
            titles = [" ".join(str(r[c]) for c in keep if c < len(r) and str(r[c]).strip()) for r in rows]
            onum = []
            for r in rows:
                nums = [re.findall(r"\d+", str(r[c])) for c in range(len(r)) if c not in keep]
                nums = [int(x[0]) for x in nums if x]; onum.append(min(nums) if nums else None)
            pairs = [(t, o) for t, o in zip(titles, onum) if t.strip()]
            cap = None if arm is not None else (b.get("caption") or "").strip()
            b.clear(); b.update({"t": "toc", "titles": [t for t, _ in pairs], "onum": [o for _, o in pairs], "cap": cap, "at": k}); arm = None
    cands = [(k, v) for k, x in enumerate(blocks) if x["t"] in ("h1", "h2", "h3", "p") and not x.get("toc_head") and x.get("text")
             for v in dict.fromkeys([_nt(x["text"])] + ([_nt(str(x["num"]) + " " + x["text"])] if x.get("num") and not re.fullmatch(r"[\dA-Za-z\u0621-\u064a]{1,2}", str(x["num"])) else []))]
    used = set()
    def matches(nt):
        ex = [k for k, hn in dict.fromkeys(cands) if hn and (hn == nt or (len(nt) > 3 and (hn.startswith(nt) or (blocks[k]["t"] != "p" and nt.startswith(hn) and len(hn) > 6))))]
        if ex: return list(dict.fromkeys(ex))
        return [k for k, hn in cands if blocks[k]["t"] != "p" and hn and difflib.SequenceMatcher(None, hn[:80], nt[:80]).ratio() > .86]
    for b in blocks:
        if b["t"] != "toc": continue
        ents = []; onums = b.get("onum") or [None] * len(b["titles"])
        M = [matches(_nt(t)) for t in b["titles"]]
        # printed page → source page offset, learned from entries with a single unambiguous match
        offs = sorted(blocks[m[0]]["p"] - o for m, o in zip(M, onums) if len(m) == 1 and o is not None and blocks[m[0]].get("p"))
        off0 = offs[len(offs) // 2] if offs else None
        ptr = b["at"]; hits = []
        for m, o in zip(M, onums):
            m = [k for k in m if k not in used]; k = None
            if m:
                if off0 is not None and o is not None and len(m) > 1:  # several headings with this title → the one nearest its printed page
                    k = min(m, key=lambda j: (abs((blocks[j].get("p") or 0) - (o + off0)), j < ptr))
                else:
                    after = [j for j in m if j > ptr]; k = (after or m)[0]
                used.add(k); ptr = k
            hits.append(k)
        off0 = off0 or 0
        for t, o, k in zip(b["titles"], onums, hits):
            nt = _nt(t); hid = None
            if k is None and o is not None:  # pass 2: fall back to the original page number
                for off in (off0, off0 + 1, off0 - 1):
                    sp = o + off
                    op = [x for x in blocks if x["t"] == "original_pages" and x["from"] <= sp <= x["to"]]
                    if op: hid = f"op-{sp}"; break
                    on = [j for j, x in enumerate(blocks) if x.get("p") == sp and x["t"] != "toc" and j not in used]
                    if on:
                        hs = [j for j in on if blocks[j]["t"] in ("h1", "h2", "h3")]
                        k = max(hs, key=lambda j: difflib.SequenceMatcher(None, _nt(blocks[j].get("text")), nt).ratio()) if hs else on[0]
                        used.add(k); break
            if k is not None:
                blocks[k]["hid"] = f"{pre}-{k}"; hid = f"{pre}-{k}"
            ents.append((t, hid))
        b["entries"] = ents
    return blocks
def _img(b):
    cls = "ph" if b.get("kind") == "photo" else "gr"
    return f'<figure class="{cls}"><img src="file://{os.path.join(B, b["src"])}" alt=""></figure>'
def blocks_html(i, lang, blocks, review, pre="h"):
    ar = lang == "ar"; out = []; blocks = build_toc(blocks, pre); tp = TOCPAGES.get((i, lang), {}); long_doc = len(blocks) > 90; first_h1 = True; prev_p = None; prev_img_p = None; after_photo = False
    for bi, b in enumerate(blocks):
        t = b["t"]
        if b.get("skip"): continue
        if b.get("tn") and isinstance(b.get("tn"), str): review.append((b.get("p"), b["tn"]))
        if t == "note" and b.get("tn") is True:
            if "nofficial" in b.get("text", "") or "غير رسمية" in b.get("text", ""): out.append(f'<div class="notice">{txt(b["text"])}</div>')
            else: review.append((b.get("p"), b["text"]))
            continue
        n = f'<span class="n">{e(b.get("num",""))}</span>' if b.get("num") else ""
        if b.get("hid") and t not in ("h1", "h2", "h3", "p"): out.append(f'<span id="{b["hid"]}"></span>')
        if t not in ("image", "kv", "note", "h3") and not (t == "p" and len(b.get("text", "")) < 40): after_photo = False
        # House rule: main sections start at the top of a page. h1 always does (full documents); h2 does when it
        # opened a page in the original document. Legal T&C text flows, so there only h1 breaks.
        sec = pre == "h" and not re.match(r"q\d-", i) and (t == "h1" or (t == "h2" and not i.startswith("tc") and b.get("p") and b.get("p") != prev_p))
        if t in ("h1", "h2", "h3", "p", "table", "kv", "ul", "ol", "chart", "figure", "note", "partners"): prev_p = b.get("p") or prev_p
        if t == "h1":
            brk = " brk" if (sec or (long_doc and not first_h1)) else ""; first_h1 = False
            if b.get("toc_head"): brk = " brk"
            out.append(f'<h1{_hid(b)} class="h1{brk}">{n}{e(b["text"])}</h1>')
            nxt = next((x for x in blocks[bi + 1:] if not x.get("skip") and x["t"] != "image"), None)
            if nxt is not None and nxt.get("prop"): out.append(PROPS_MOD.overview(PROPS, lang, e))
        elif t == "h2" and b.get("prop"):
            out.append(PROPS_MOD.hero(b["prop"], lang, b.get("hid"), sec, _img, e, txt)); after_photo = True; continue
        elif t in ("h2", "h3"):
            cls = ' class="tochd"' if b.get("toc_head") else (' class="brk"' if sec else "")
            out.append(f'<{t}{_hid(b)}{cls}>{n}{e(b["text"])}</{t}>')
        elif t == "toc":
            cap = f'<h2 class="tochd">{e(b["cap"])}</h2>' if b.get("cap") else ""
            lvl = {x.get("hid"): x["t"] for x in blocks if x.get("hid")}
            rows = "".join(f'<a class="te{" l1" if lvl.get(h) == "h1" else ""}" href="#{h}"><span class="tt">{e(x)}</span><span class="tl"></span><span class="tp">{tp.get(h, "")}</span></a>' if h else
                           f'<div class="te"><span class="tt">{e(x)}</span><span class="tl"></span><span class="tp"></span></div>' for x, h in b["entries"])
            out.append(f'{cap}<nav class="toc">{rows}</nav>')
        elif t == "p": out.append(f'<p{_hid(b)}>{txt(b["text"])}</p>')
        elif t in ("ul", "ol"):
            items = b.get("items", [])
            if b.get("kind") == "diagram":
                cap = f'<div class="ct">{e(b.get("caption"))}</div>' if b.get("caption") else ""
                out.append(f'<div class="diagram">{cap}{"".join(f"<span>{e(x)}</span>" for x in items)}</div>'); continue
            cls = ' class="l2"' if b.get("level") == 2 else (' class="toc"' if b.get("toc") else "")
            tag = "ol" if t == "ol" and not any(re.match(r"^\s*(\(?[\dA-Za-z]{1,3}[\).]|[أ-ي][\).-])", x) for x in items) else "ul"
            if t == "ol" and tag == "ul": cls = ' class="plain"'
            out.append(f'<{tag}{cls}>{"".join(f"<li>{txt(x)}</li>" for x in items)}</{tag}>')
        elif t == "table":
            cap = f'<div class="ct">{e(b.get("caption"))}</div>' if b.get("caption") else ""
            head = b.get("head") or []
            hrows = head if head and isinstance(head[0], list) else [head]
            th = f'<thead>{"".join("<tr>" + "".join(f"<th>{txt(h)}</th>" for h in hr) + "</tr>" for hr in hrows)}</thead>' if any(str(h).strip() for hr in hrows for h in hr) else ""
            nc = max([len(hr) for hr in hrows] + [len(r) for r in b.get("rows", [])])
            rows = "".join("<tr>" + "".join(f'<td class="{_numcls(c)}">{txt(c)}</td>' for c in (r + [""] * (nc - len(r)))) + "</tr>" for r in b.get("rows", []))
            small = " sm" if nc >= 5 else ""
            out.append(f'<div class="tw">{cap}<table class="t{small}">{th}<tbody>{rows}</tbody></table></div>')
        elif t == "kv":
            cap = f'<div class="ct">{e(b.get("caption"))}</div>' if b.get("caption") else ""
            if b.get("rows") and (after_photo or len(b["rows"]) <= 40):   # key–value blocks → fact cards
                cells = "".join(f'<div class="fc{" w" if len(str(v)) > 90 else ""}"><span>{txt(k)}</span><b{_CO if "°" in str(v) else ""}>{txt(v)}</b></div>' for k, v in [(r + [""])[:2] for r in b.get("rows", [])])
                out.append(f'<div class="facts{" big" if len(b["rows"]) > 8 else ""}">{cap}<div class="fg">{cells}</div></div>')
            else:
                rows = "".join(f'<tr><th>{txt(k)}</th><td>{txt(v)}</td></tr>' for k, v in [(r + [""])[:2] for r in b.get("rows", [])])
                out.append(f'<div class="tw">{cap}<table class="kv">{rows}</table></div>')
        elif t == "note": out.append(f'<div class="note">{txt(b["text"])}</div>')
        elif t == "chart": out.append(chart(b, ar))
        elif t == "signature": out.append(f'<div class="sig">{txt(b["text"])}</div>')
        elif t == "image":
            if out and out[-1].startswith('<div class="gal') and b.get("kind") == "photo" and prev_img_p == b.get("p"):
                body_ = out[-1][out[-1].index(">") + 1:-6] + _img(b); n_ = body_.count("<figure")
                out[-1] = f'<div class="gal g{min(n_, 3)}">' + body_ + "</div>"
            else:
                out.append(f'<div class="gal g1">{_img(b)}</div>')
            prev_img_p = b.get("p"); after_photo = b.get("kind") == "photo"; continue
        elif t == "figure":
            ttl = f'<div class="ct">{e(b["title"])}</div>' if b.get("title") else ""
            out.append(f'<figure class="fig">{ttl}{open(os.path.join(B, b["src"]), encoding="utf-8").read()}</figure>')
        elif t == "partners": out.append(partners(b, ar))
        elif t == "original_pages":
            if i == "annual-2025" and lang == "en" and os.path.exists(os.path.join(B, "struct", "annual-2025-fs.en.json")):
                fs = json.load(open(os.path.join(B, "struct", "annual-2025-fs.en.json")))
                out.append('<div class="brk"></div>' + blocks_html(i, lang, fs["blocks"], review, "f"))
            else:
                out.append(originals(i, lang, b["from"], b["to"]))
    return "".join(out)

CSS = """
@page{size:A4;margin:24mm 0 20mm;
 @top-right{padding-right:17mm;content:"%(TR)s";font-family:'Alexandria',sans-serif;font-size:7.5pt;color:#5A6478;vertical-align:bottom;padding-bottom:5mm}
 @top-left{padding-left:17mm;content:"%(TL)s";font-family:'Alexandria',sans-serif;font-size:7.5pt;color:#3B7DD8;vertical-align:bottom;padding-bottom:5mm}
 @bottom-right{padding-right:17mm;content:%(BR)s;font-family:'Alexandria',sans-serif;font-size:7.5pt;color:#5A6478}
 @bottom-left{padding-left:17mm;content:%(BL)s;font-family:'Alexandria',sans-serif;font-size:7.5pt;color:#5A6478}}
@page :first{margin-top:0;@top-right{content:none}@top-left{content:none}}
@page cover{margin:0;@top-right{content:none}@top-left{content:none}@bottom-right{content:none}@bottom-left{content:none}}
@page orig{margin:0;@top-right{content:none}@top-left{content:none}@bottom-right{content:none}@bottom-left{content:none}}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-variant-ligatures:no-common-ligatures no-discretionary-ligatures;font-family:%(BODY)s;color:#0B1733;font-size:%(FS)s;line-height:%(LH)s}
.cover{page:cover;width:210mm;height:296.6mm;position:relative;overflow:hidden;background:#021640;color:#fff}
.cover .art{position:absolute;left:0;right:0;top:62mm;height:140mm;background:url(%(ART)s) center/210mm 140mm no-repeat}
.cover .fade{display:none}
.cover .flogo{position:absolute;top:20mm;%(START)s:18mm;width:64mm}
.cover .ft .akc{height:13.5mm;width:auto}
.cover .tx{position:absolute;bottom:36mm;%(START)s:18mm;%(END)s:18mm}
.cover .tx:before{content:"";display:block;width:14mm;height:.9mm;background:#3B7DD8;margin-bottom:5mm}
.cover .eyb{font-family:'Alexandria',sans-serif;font-size:10pt;color:#9DB8E0;letter-spacing:%(LS)s}
.cover .fund{font-family:'Alexandria',sans-serif;font-weight:700;font-size:24pt;line-height:1.6;margin-top:3mm;max-width:150mm}
.cover .doc{font-family:'Alexandria',sans-serif;font-weight:600;font-size:16pt;color:#7FB0EA;margin-top:6mm;padding-top:5mm;border-top:.3mm solid rgba(157,184,224,.3);max-width:110mm}
.cover .dt{font-size:11pt;color:#C9D6EE;margin-top:2mm}
.cover .tag{font-size:9.5pt;color:#C9D6EE;margin-top:6mm;max-width:150mm;line-height:1.6}
.cover .ft{position:absolute;bottom:12mm;%(START)s:18mm;%(END)s:18mm;font-size:7.5pt;color:#9DB8E0;display:flex;justify-content:space-between;align-items:center;border-top:.3mm solid rgba(157,184,224,.35);padding-top:3mm}
.band{position:relative;height:58mm;margin:0 -17mm 8mm;background:#071A3A;color:#fff;padding:14mm 17mm 0}
.band:after{content:"";position:absolute;left:0;right:0;bottom:0;height:1.2mm;background:#3B7DD8}
.band>*{position:relative;z-index:1}
.band .flogo{position:absolute;top:11mm;%(END)s:17mm;width:62mm}
.band .akc{position:absolute;bottom:9mm;%(END)s:17mm;width:30mm;opacity:.9}
.band .eyb{font-family:'Alexandria',sans-serif;font-size:9pt;color:#9DB8E0}
.band .fund{font-family:'Alexandria',sans-serif;font-weight:700;font-size:17pt;line-height:1.3;margin-top:2mm;max-width:120mm}
.band .doc{font-family:'Alexandria',sans-serif;font-size:12pt;color:#7FB0EA;margin-top:2mm}
main{padding:0 17mm}
h1,h2,h3{font-family:'Alexandria',sans-serif;color:#12284B;break-after:avoid}
h1{font-size:17pt;line-height:1.3;margin:2mm 0 5mm;padding-bottom:3mm;border-bottom:.5mm solid #3B7DD8}
h1.brk,.brk{break-before:page}
h2{font-size:12pt;line-height:1.4;margin:6mm 0 2.5mm}
h3{font-size:10.5pt;line-height:1.4;margin:4mm 0 2mm;color:#2E6DB0}
.n{color:#3B7DD8;margin-%(END)s:2mm;font-feature-settings:"tnum"}
p{margin:0 0 2.6mm;text-align:justify;orphans:2;widows:2}
ul,ol{margin:0 0 3mm;padding-%(START)s:6mm}
li{margin-bottom:1.4mm}
ul li::marker{color:#3B7DD8}
ul.l2{padding-%(START)s:12mm}
ul.plain{list-style:none;padding-%(START)s:0}
.tw{margin:2mm 0 4mm;break-inside:auto}
.ct{font-family:'Alexandria',sans-serif;font-size:9pt;font-weight:600;color:#12284B;margin-bottom:2mm}
table{width:100%%;border-collapse:collapse;font-size:%(TFS)s;line-height:1.45}
table.t th{background:#12284B;color:#fff;font-weight:600;padding:2mm 2.2mm;text-align:start;vertical-align:bottom;font-family:'Alexandria',sans-serif;font-size:%(THS)s}
table.t td{padding:1.8mm 2.2mm;border-bottom:.25mm solid #DCE3EE;vertical-align:top}
table.t tbody tr:nth-child(even) td{background:#F3F6FB}
table.sm{font-size:%(SMS)s}
table.sm tbody td:first-child:not(.num){min-width:30mm}
table.kv th{width:42%%;text-align:start;font-weight:500;color:#5A6478;padding:1.8mm 2.2mm;border-bottom:.25mm solid #DCE3EE;vertical-align:top}
table.kv td{padding:1.8mm 2.2mm;border-bottom:.25mm solid #DCE3EE;font-weight:600;vertical-align:top}
tr{break-inside:avoid}
thead{display:table-header-group}
td.num{white-space:nowrap;font-feature-settings:"tnum"}
.note{font-size:%(NFS)s;color:#3A4458;background:#F3F6FB;border-%(START)s:.8mm solid #9DB8E0;padding:2.4mm 3.2mm;margin:1mm 0 4mm;line-height:1.6}
.notice{font-size:8.5pt;font-weight:600;color:#12284B;background:#E6EEF8;padding:3mm 4mm;margin:0 0 5mm;border-radius:1.5mm}
.sig{margin:4mm 0;font-weight:600;break-before:avoid}
.fig{margin:3mm 0 6mm;break-inside:avoid}
figure.chart{margin:2mm 0 5mm;break-inside:avoid;border:.25mm solid #DCE3EE;border-radius:1.5mm;padding:4mm}
.gal{display:grid;gap:3mm;margin:2mm 0 5mm;break-inside:avoid}.gal.g2{grid-template-columns:1fr 1fr}
.gal figure{margin:0;break-inside:avoid}.gal img{display:block;width:100%%;border-radius:2mm}
.gal .ph img{height:82mm;object-fit:cover;box-shadow:0 1.2mm 3.5mm rgba(11,23,51,.16)}.gal.g2 .ph img{height:58mm}.gal.g3{grid-template-columns:1fr 1fr 1fr}.gal.g3 .ph img{height:40mm}.gal.g2,.gal.g3{break-inside:auto}
.gal .gr img{max-height:120mm;object-fit:contain;background:#F3F6FB;border:.25mm solid #DCE3EE}
.facts{margin:0 0 6mm;break-inside:avoid}.facts.big{break-inside:auto}.facts .fg{display:grid;grid-template-columns:1fr 1fr;column-gap:6mm;gap:0;border-top:.6mm solid #3B7DD8}
.facts .fc{padding:2.4mm 2.6mm 2.6mm;border-bottom:.25mm solid #DCE3EE;display:flex;flex-direction:column;gap:.8mm;break-inside:avoid}
.facts .fc.w{grid-column:1/-1}.facts .fc b.co{text-align:%(START)s;unicode-bidi:isolate}.facts .fc span{font-size:7.4pt;color:#5A6478;line-height:1.35}.facts .fc b{font-size:9pt;font-weight:600;color:#12284B;line-height:1.45}
h1.brk{font-size:21pt;line-height:1.3;border-bottom:0;padding:0;margin:2mm 0 7mm}
h1.brk:after{content:"";display:block;width:18mm;height:1.2mm;background:#3B7DD8;margin-top:4mm;border-radius:.6mm}
h1.brk .n{display:block;font-size:34pt;line-height:1;color:#9DB8E0;margin:0 0 3.5mm;font-weight:600}
h2 .n{display:inline-flex;align-items:center;justify-content:center;min-width:7mm;height:7mm;padding:0 1.6mm;border-radius:3.5mm;background:#3B7DD8;color:#fff;font-size:8.6pt;line-height:1;vertical-align:.4mm;margin-%(END)s:2.4mm}
h2{padding-bottom:1.6mm;border-bottom:.25mm solid #DCE3EE}
h3{color:#3B7DD8}
.toc .te.l1{padding-top:3.4mm;border-bottom-color:#9DB8E0}.toc .te.l1 .tt{font-family:'Alexandria',sans-serif;font-weight:600;color:#12284B;font-size:10pt}
.toc .te:not(.l1) .tt{padding-%(START)s:5mm;color:#3A4458}
.facts .fg{background:linear-gradient(#F7F9FC,#F7F9FC)}.facts .fc{padding:2.6mm 3mm 2.8mm}
.note{border-radius:0 1.5mm 1.5mm 0}
table.t thead tr:first-child th:first-child{border-start-start-radius:1.5mm}table.t thead tr:first-child th:last-child{border-start-end-radius:1.5mm}
.mleg{display:flex;flex-wrap:wrap;gap:1.5mm 5mm;font-size:7.4pt;color:#5A6478;margin:0 0 2.5mm}.mleg i{display:inline-block;width:3mm;height:3mm;border-radius:.6mm;margin-inline-end:1.5mm;vertical-align:-.4mm}
.mg{display:grid;grid-template-columns:34mm 1fr;gap:3mm;align-items:center;padding:1.2mm 0;border-bottom:.2mm solid #EEF2F8}.mg:last-child{border-bottom:0}
.mgl{font-size:7.6pt;color:#0B1733;line-height:1.3}.mg .br{grid-template-columns:1fr 18mm;margin:.4mm 0}
.pw{display:flex;align-items:center;gap:6mm}
.legend{flex:1;display:grid;gap:1.6mm;font-size:8.5pt}
.lg{display:flex;align-items:center;gap:2mm}.lg i{width:3mm;height:3mm;border-radius:.6mm;flex:none}.lg .ll{flex:1}.lg b{font-family:'Alexandria',sans-serif}
.br{display:grid;grid-template-columns:62mm 1fr 14mm;gap:3mm;align-items:center;font-size:8.3pt;margin-bottom:1.4mm}
.bt{height:3.2mm;background:#F3F6FB;border-radius:.8mm;overflow:hidden;display:flex}.bt i{background:#3B7DD8;border-radius:.8mm}
.br b{font-family:'Alexandria',sans-serif;font-weight:500;text-align:end}
.cap{font-size:7.5pt;color:#5A6478;margin-top:2mm}
.tochd{break-before:page}
.toc{display:block;margin:2mm 0 4mm}
.toc .te{display:flex;align-items:baseline;gap:2.5mm;padding:1.9mm 0;border-bottom:.25mm solid #DCE3EE;color:inherit;text-decoration:none;break-inside:avoid}
.toc .tt{flex:0 1 auto}
.toc .tl{flex:1 1 auto;min-width:6mm;border-bottom:.35mm dotted #9DB8E0;align-self:center;transform:translateY(1mm)}
.toc .tp{flex:0 0 9mm;text-align:end;font-family:'Alexandria',sans-serif;font-weight:600;color:#12284B}
.diagram{display:flex;flex-wrap:wrap;gap:2mm;margin:2mm 0 4mm}
.diagram span{border:.3mm solid #9DB8E0;border-radius:1.2mm;padding:1.5mm 3mm;font-size:8.5pt;color:#12284B;background:#F3F6FB}
.orig{page:orig;width:210mm;height:296.6mm;break-before:page;display:flex;align-items:center;justify-content:center;background:#fff}
.orig img{max-width:210mm;max-height:296.6mm}
.back{page:cover;break-before:page;width:210mm;height:296.6mm;background:#021640;color:#C9D6EE;position:relative}
.back .flogo{position:absolute;top:44%%;left:50%%;transform:translate(-50%%,-50%%);width:80mm}
.back .logo{position:absolute;top:60%%;left:50%%;transform:translate(-50%%,-50%%);width:56mm}
.back .ad{position:absolute;bottom:18mm;left:16mm;right:16mm;text-align:center;font-size:8pt;line-height:1.8}
"""
PCSS = """
.partners{margin:2mm 0 5mm}
.partners .pg{margin-bottom:4mm}
.partners .pg>h2{margin-top:4mm}
.pgrid{display:flex;flex-wrap:wrap;gap:3mm}
.pgrid .pc{width:calc((100% - 9mm) / 4)}
.pgrid.c3 .pc{width:calc((100% - 6mm) / 3)}
.pc{background:none;border:0;padding:2mm 2mm 2mm;break-inside:avoid;page-break-inside:avoid;display:flex;flex-direction:column;align-items:center;text-align:center}
.pr{font-family:'Alexandria',sans-serif;font-size:7.2pt;font-weight:500;color:#3B7DD8;line-height:1.35;min-height:4.2mm;margin-bottom:2mm}
.pl{height:12mm;width:100%;display:flex;align-items:center;justify-content:center}
.pl img{width:auto;height:auto;object-fit:contain;display:block}
.pn{font-size:7.6pt;color:#12284B;line-height:1.4;margin-top:2.2mm;width:100%}
.pd{font-size:6.8pt;color:#5A6478;line-height:1.45;margin-top:1.6mm;width:100%}
.pd bdi{unicode-bidi:isolate}
bdi.tel{unicode-bidi:isolate;direction:ltr;white-space:nowrap}
.pc.miss{color:#5A6478;font-size:7pt}
"""
CSS += PCSS.replace("%", "%%")

_IMGS = None
def images_for(i, lang):
    global _IMGS
    if _IMGS is None:
        f = os.path.join(B, "graphics", "img", "index.json"); _IMGS = json.load(open(f)) if os.path.exists(f) else {}
    return _IMGS.get(f"{i}.{lang}", [])
def inject_images(blocks, items):
    """Place each extracted photo/map on its source page: right after that page's first heading run, else before the
    page's first block, else after the last block of an earlier page."""
    blocks = list(blocks)
    for it in sorted(items, key=lambda x: (x["p"], x["y"]), reverse=True):
        p = it["p"]; idx = None
        on = [k for k, b in enumerate(blocks) if b.get("p") == p and b["t"] != "image"]
        hs = [k for k in on if blocks[k]["t"] in ("h1", "h2", "h3")]
        if hs:
            idx = hs[0] + 1
            while idx < len(blocks) and blocks[idx]["t"] in ("h1", "h2", "h3") and blocks[idx].get("p") == p: idx += 1
        elif on: idx = on[0]
        else:
            prev = [k for k, b in enumerate(blocks) if (b.get("p") or 0) < p]
            idx = (prev[-1] + 1) if prev else len(blocks)
        blk = {"t": "image", "src": it["src"], "kind": it.get("kind", "photo"), "w": it["w"], "h": it["h"], "p": p}
        blocks.insert(idx, blk)
    return blocks
def render(i, lang):
    ar = lang == "ar"
    src = os.path.join(B, "struct", f"{i}.{lang}.json"); d = json.load(open(src))
    title, date, kind = meta(i, lang)
    review = []
    blocks = d["blocks"]; tag = ""
    if kind == "full":
        p1 = [b for b in blocks if b.get("p") == 1 and b["t"] in ("p", "h1", "h2", "h3")]
        cand = [b["text"] for b in p1 if b["t"] == "p" and 25 <= len(b.get("text", "")) <= 220 and not any(x in b.get("text", "")[:60] for x in CFG.get("tag_exclude", ["2030"]))]
        tag = cand[0] if cand else ""
        blocks = [b for b in blocks if not (b.get("p") == 1 and b["t"] in ("p", "h1", "h2", "h3"))]
    INLINE_TN.clear()
    imgs = [x for x in images_for(i, lang) if not (kind == "full" and x["p"] == 1)]
    if imgs: blocks = inject_images(blocks, imgs)
    global PROPS
    blocks = [dict(b) for b in blocks]; PROPS = PROPS_MOD.prepare(blocks, lang)
    body = blocks_html(i, lang, blocks, review)
    review += [(None, x) for x in dict.fromkeys(INLINE_TN)]
    eyb = EYB[lang]
    if kind == "full":
        top = (f'<section class="cover"><div class="art"></div><div class="fade"></div><img class="flogo" src="{FLOGO_W}" alt="">'
               f'<div class="tx"><div class="eyb">{eyb}</div><div class="fund">{FUND[lang]}</div><div class="doc">{e(title)}</div><div class="dt">{e(date)}</div>{_tag(tag)}</div>'
               f'<div class="ft"><img class="akc" src="{LOGO_W}" alt=""><span>{"مدير الصندوق: الخبير المالية · ترخيص هيئة السوق المالية رقم 07074-37 · alkhabeer.com" if ar else "Fund Manager: Alkhabeer Capital · CMA License No. 07074-37 · alkhabeer.com"}</span></div></section>')
        back = (f'<section class="back"><img class="flogo" src="{FLOGO_W}" alt=""><img class="logo" src="{LOGO_W}" alt=""><div class="ad">'
                + ("شركة الخبير المالية · ص.ب 128289 جدة 21362 · المملكة العربية السعودية<br>هاتف ‎+966 12 658 8888 · info@alkhabeer.com · www.alkhabeer.com<br>شركة مرخصة من هيئة السوق المالية بترخيص رقم 07074-37 · سجل تجاري 4030177445"
                   if ar else "Alkhabeer Capital · P.O. Box 128289 Jeddah 21362 · Kingdom of Saudi Arabia<br>Tel +966 12 658 8888 · info@alkhabeer.com · www.alkhabeer.com<br>Licensed by the Capital Market Authority, License No. 07074-37 · C.R. 4030177445")
                + '</div></section>')
    else:
        top = f'<div class="band"><img class="flogo" src="{FLOGO_W}" alt=""><img class="akc" src="{LOGO_W}" alt=""><div class="eyb">{e(title)}</div><div class="fund">{FUND[lang]}</div><div class="doc">{e(date)}</div></div>'
        back = ""
    top_full, top_band = (top, "") if kind == "full" else ("", top)
    TR, TL = (FUND["ar"], f"{title} {date}".strip()) if ar else (f"{title} {date}".strip(), FUND["en"])
    if ar: BR, BL = '"الخبير المالية · alkhabeer.com"', "counter(page)"
    else: BR, BL = "counter(page)", '"Alkhabeer Capital · alkhabeer.com"'
    css = CSS % dict(TR=TR.replace('"', "'"), TL=TL.replace('"', "'"), BR=BR, BL=BL,
                     BODY="'IBM Plex Sans Arabic','Alexandria',sans-serif" if ar else "'IBM Plex Sans','Alexandria',sans-serif",
                     FS="9.6pt" if ar else "9.3pt", LH="1.75" if ar else "1.55", TFS="8.4pt", THS="8pt", SMS="7.6pt", NFS="8.2pt",
                     START="right" if ar else "left", END="left" if ar else "right", LS="0" if ar else ".04em", GRAD="270deg" if ar else "90deg",
                     ART=ART["cover"], BAND=ART["band"])
    if PROPS: css += re.sub(r"%(?!\()", "%%", PROPS_MOD.CSS) % dict(LS="0" if ar else ".04em", START="right" if ar else "left", END="left" if ar else "right")
    if CFG.get("cover_art"):  # class cover art: larger, edges dissolved into the page navy (no visible box)
        css += (".cover .art{top:46mm;height:140mm;background-size:210mm 140mm;background-position:center}")  # edge feather is baked into the image: CSS masks break in iOS/Preview PDF viewers
    fonts = "https://fonts.googleapis.com/css2?family=Alexandria:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
    doc = (f'<!doctype html><html lang="{lang}" dir="{"rtl" if ar else "ltr"}"><head><meta charset="utf-8"><title>{e(FUND[lang])} — {e(title)} {e(date)}</title>'
           f'<link rel="stylesheet" href="{fonts}"><style>{css}</style></head><body>{tels(top_full + "<main>" + top_band + body + "</main>" + back)}</body></html>')
    if CFG.get("corporate"):  # company documents (identity «ضوء»): no fund logo, company wording, corporate typeface
        doc = re.sub(r'<img class="flogo"[^>]*>', '', doc)
        doc = doc.replace("مدير الصندوق: الخبير المالية · ", "شركة الخبير المالية · ").replace("Fund Manager: Alkhabeer Capital · ", "Alkhabeer Capital · ")
        hf = CFG.get("head_font", "Zain")
        doc = doc.replace("'Alexandria'", f"'{hf}'").replace("'IBM Plex Sans Arabic'", f"'{hf}'").replace("'IBM Plex Sans'", f"'{hf}'")
        doc = doc.replace(fonts, fonts + f'&family={hf.replace(" ", "+")}:wght@300;400;700;800')
        doc = doc.replace("</style>", ".cover{background:#071A3A}.cover .art{top:0;height:200mm;background-size:cover;background-position:center}body{font-size:%s}</style>" % ("11pt" if ar else "10.5pt"), 1)
    doc = recolour(doc)
    p = os.path.join(OUT, "html", f"{i}.{lang}.html"); open(p, "w").write(doc)
    if review: json.dump(review, open(os.path.join(OUT, "html", f"{i}.{lang}.review.json"), "w"), ensure_ascii=False, indent=1)
    return p

if __name__ == "__main__":
    a = sys.argv[1:]; jobs = []
    for k in range(0, len(a), 2): jobs.append(render(a[k], a[k + 1]))
    json.dump(jobs, open(os.path.join(OUT, "jobs.json"), "w")); print("\n".join(jobs))
