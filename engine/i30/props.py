"""Property dossiers for real-estate fund reports.

A property section in the source is: h2 «العقار الأول: …» / «First Property: …», a city line, the photo(s), an h3 and a
facts table. Here it becomes one designed spread: the photo as a hero with the name and tags on it, a locator map, and
a row of key figures taken from the same report (portfolio table + portfolio-weight chart + the facts table). No text
is invented: every figure and label value comes from the document itself; only short design labels are added.
"""
import re, difflib, html

PROP_RE = re.compile(r"^\s*(العقار\s*[^:：]{2,25}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Property)\s*[:：]\s*(.+)$")
CITY = {  # lon, lat
    "الرياض": (46.72, 24.71), "riyadh": (46.72, 24.71), "جدة": (39.19, 21.54), "جده": (39.19, 21.54), "jeddah": (39.19, 21.54),
    "تبوك": (36.57, 28.38), "tabuk": (36.57, 28.38), "مكة": (39.83, 21.42), "makkah": (39.83, 21.42), "mecca": (39.83, 21.42),
    "الدمام": (50.10, 26.43), "dammam": (50.10, 26.43), "الخبر": (50.21, 26.28), "khobar": (50.21, 26.28),
    "المدينة المنورة": (39.61, 24.47), "madinah": (39.61, 24.47), "medina": (39.61, 24.47)}
CITY_EN = {"الرياض": "Riyadh", "جدة": "Jeddah", "جده": "Jeddah", "تبوك": "Tabuk", "مكة": "Makkah", "الدمام": "Dammam", "الخبر": "Khobar"}
# Simplified outline of the Kingdom (lon, lat) — a locator silhouette, not a survey map.
KSA = [(34.95, 29.36), (36.07, 29.19), (36.75, 29.87), (37.5, 30.0), (38.0, 30.5), (37.0, 31.5), (39.2, 32.15), (40.4, 31.9),
       (42.0, 31.1), (44.7, 29.2), (46.5, 29.1), (47.45, 28.99), (48.4, 28.55), (48.8, 27.6), (49.5, 26.9), (50.1, 26.2),
       (50.15, 25.6), (50.8, 24.75), (51.6, 24.25), (52.0, 23.0), (55.2, 22.7), (55.65, 22.0), (55.0, 20.0), (52.0, 19.0),
       (49.0, 18.6), (48.2, 18.2), (47.0, 16.95), (46.0, 17.3), (44.5, 17.4), (43.3, 17.55), (42.8, 16.4), (42.6, 16.8),
       (41.8, 17.8), (40.8, 19.5), (39.6, 20.9), (39.1, 21.7), (38.5, 23.6), (37.4, 24.8), (36.5, 25.9), (35.6, 27.5),
       (34.8, 28.1), (34.6, 28.1)]
LON0, LAT0, KX = 34.3, 32.6, 0.913


def _xy(lon, lat): return round((lon - LON0) * KX, 3), round(LAT0 - lat, 3)


def _norm(s):
    s = re.sub(r"[ً-ْـ\"'“”«»()\-–*]", " ", str(s or "")).lower()
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه").replace("جاليري", "جالري")
    s = re.sub(r"\b(مركز|التجاري|center|centre|commercial|plaza|سابقا|سابقاً|formerly)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _match(name, cands):
    n = _norm(name); best, sc = None, 0.0
    for k, c in enumerate(cands):
        m = _norm(c)
        if not m: continue
        r = difflib.SequenceMatcher(None, n, m).ratio()
        if m in n or n in m: r = max(r, 0.9)
        if r > sc: best, sc = k, r
    return best if sc >= 0.62 else None


def _col(head, *keys):
    for k, h in enumerate(head):
        if any(x in str(h).lower() for x in keys): return k
    return None


def city_of(text):
    t = str(text or "").lower()
    for k in sorted(CITY, key=len, reverse=True):
        if k in t: return k
    return None


def prepare(blocks, lang):
    """Mark property h2 blocks with their dossier data and the blocks folded into the hero. Returns the overview list."""
    ar = lang == "ar"
    tbl = next((b for b in blocks if b["t"] == "table" and _col(b.get("head") or [], "اسم العقار", "property name") is not None), None)
    pie = next((b for b in blocks if b["t"] == "chart" and b.get("kind") == "pie" and len(b.get("series", [])) >= 4), None)
    rows = []
    if tbl:
        hd = tbl["head"]; c = {k: _col(hd, *v) for k, v in {
            "name": ("اسم العقار", "property name"), "city": ("المدينة", "city"), "sector": ("القطاع", "segment", "sector"),
            "own": ("الملكية", "ownership"), "occ": ("الإشغال", "occupancy"), "rent": ("نسبة الإيجار", "rent per asset", "rents"),
            "bua": ("البناء", "bua", "built")}.items()}
        for r in tbl.get("rows", []):
            g = lambda k: (str(r[c[k]]).strip() if c[k] is not None and c[k] < len(r) else "")
            rows.append({k: g(k) for k in c})
    props = []
    for k, b in enumerate(blocks):
        if b["t"] != "h2": continue
        m = PROP_RE.match(b.get("text", ""))
        if not m: continue
        d = {"ord": m.group(1).strip(), "name": m.group(2).strip(), "photos": [], "kv": None, "exited": False}
        j = k + 1
        while j < len(blocks) and blocks[j]["t"] not in ("h1", "h2"):
            x = blocks[j]
            if x["t"] == "p" and len(x.get("text", "")) < 40 and not d.get("cityline") and city_of(x["text"]):
                d["cityline"] = x["text"].strip(); x["skip"] = True
            elif x["t"] == "image" and x.get("kind") == "photo":
                d["photos"].append(x); x["skip"] = True
            elif x["t"] == "kv" and d["kv"] is None: d["kv"] = x
            elif x["t"] == "note" and re.search(r"التخارج|بيع العقار|exit|sold", x.get("text", ""), re.I): d["exited"] = True
            j += 1
        kv = {str(a).strip(): str(v).strip() for a, v in ((r + [""])[:2] for r in (d["kv"] or {}).get("rows", []))}
        if any(re.search(r"تاريخ بيع|sale date|date of sale", a, re.I) for a in kv): d["exited"] = True
        d["kvmap"] = kv
        r = rows[_match(d["name"], [x["name"] for x in rows])] if rows and _match(d["name"], [x["name"] for x in rows]) is not None else {}
        d["row"] = r
        if pie:
            pk = _match(d["name"], [s.get("label") for s in pie["series"]])
            d["weight"] = pie["series"][pk]["value"] if pk is not None else None
        d["city"] = city_of(d.get("cityline")) or city_of(r.get("city")) or city_of(kv.get("موقع العقار") or kv.get("Property Location"))
        b["prop"] = d; props.append(d)
    return props


def _num(v):
    """Split a value like '15,925 متراً مربعاً .' into (number, unit)."""
    v = re.sub(r"\s*[.،]\s*$", "", str(v or "")).strip()
    m = re.match(r"^([\d٠-٩][\d٠-٩,.٬٫]*\s*%?)\s*(.*)$", v)
    if not m: return v, ""
    u = m.group(2).strip()
    if re.search(r"متر|square|sq", u, re.I): u = "م²" if re.search(r"[؀-ۿ]", u) else "m²"
    return m.group(1).strip(), u


def map_svg(points, big=False):
    """points: list of (lon, lat, label, n, muted)."""
    path = "M" + " L".join(f"{x},{y}" for x, y in (_xy(*p) for p in KSA)) + " Z"
    dots = []
    for lon, lat, lab, n, muted in points:
        x, y = _xy(lon, lat); r = .62 if big else .75
        col = "#9DB8E0" if muted else "#3B7DD8"
        dots.append(f'<circle cx="{x}" cy="{y}" r="{r * 2.1}" fill="{col}" opacity=".22"/><circle cx="{x}" cy="{y}" r="{r}" fill="{col}" stroke="#fff" stroke-width=".22"/>')
        if big and lab:
            dots.append(f'<text x="{x}" y="{y - 1.35}" text-anchor="middle" class="ml">{html.escape(lab)}</text>')
            if n: dots.append(f'<text x="{x}" y="{y + 2.05}" text-anchor="middle" class="mn">{n}</text>')
    w, h = _xy(56.2, 15.9)
    return (f'<svg class="ksa" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg"><path d="{path}" fill="#E9EEF6" stroke="#9DB8E0" stroke-width=".12" stroke-linejoin="round"/>'
            + "".join(dots) + "</svg>")


def hero(d, lang, hid, brk, img_html, e, txt):
    ar = lang == "ar"; r = d["row"]; kv = d["kvmap"]
    city = (d.get("cityline") or r.get("city") or "").replace("مدينة ", "").replace("City of ", "")
    tags = [x for x in dict.fromkeys([city, r.get("sector") or re.sub(r"\s*\.$", "", kv.get("الاستخدام") or kv.get("Use") or ""), r.get("own")]) if x]
    if d["exited"]: tags.append("تم التخارج" if ar else "Exited")
    ph = d["photos"][0] if d["photos"] else None
    loc = CITY.get(d.get("city") or "")
    mapc = f'<div class="pmap">{map_svg([(loc[0], loc[1], "", 0, False)])}<span>{e(city)}</span></div>' if loc else ""
    pic = img_html(ph) if ph else '<div class="noimg"></div>'
    # key figures — taken from this report only
    kp = []
    def add(val, lab, bar=None, raw=False):
        if val and str(val).strip() not in ("", "-", "—", "لا يوجد", "N/A"): kp.append((val, lab, bar, raw))
    if d["exited"]:
        for a, v in kv.items():
            if re.search(r"قيمة بيع|sale value|sale price|تاريخ بيع|sale date|date of sale|الأرباح من بيع|gain|profit", a, re.I): add(re.sub(r"\s*[.،]\s*$", "", v), a, raw=True)
    else:
        add(r.get("occ"), "نسبة الإشغال" if ar else "Occupancy rate", r.get("occ"))
        if d.get("weight") is not None: add(f'{d["weight"]:.2f}%'.replace(".00%", "%"), "من إجمالي قيمة العقارات" if ar else "of total property value", f'{d["weight"]}%')
        add(r.get("rent"), "من إجمالي إيجارات الصندوق" if ar else "of the Fund's total rents", r.get("rent"))
    land = next((v for a, v in kv.items() if re.search(r"مساحة الأرض|land area", a, re.I)), None)
    bua = next((v for a, v in kv.items() if re.search(r"مسطح البناء|built-?up|bua|building area", a, re.I)), None)
    for v, lab in ((bua, "إجمالي مسطح البناء" if ar else "Total built-up area"), (land, "مساحة الأرض" if ar else "Land area")):
        if len(kp) < 4 and v: add(v, lab)
    cards = []
    for val, lab, bar, raw in kp[:4]:
        if raw:
            cards.append(f'<div class="kp tx"><b>{e(val)}</b><span>{e(lab)}</span></div>'); continue
        n, u = _num(val)
        pct = None
        if bar:
            m = re.search(r"([\d.]+)", str(bar).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")))
            pct = min(100.0, float(m.group(1))) if m else None
        barh = f'<i style="width:{pct:.1f}%"></i>' if pct is not None else ""
        cards.append(f'<div class="kp"><b>{e(n)}{f"<small>{e(u)}</small>" if u else ""}</b><span>{e(lab)}</span>{f"<em>{barh}</em>" if barh else ""}</div>')
    kpis = f'<div class="kps k{len(cards)}">{"".join(cards)}</div>' if cards else ""
    more = d["photos"][1:4]
    gal = f'<div class="gal g{min(len(more), 3)}">{"".join(img_html(x) for x in more)}</div>' if more else ""
    return (f'<section class="prop{" brk" if brk else ""}{" ex" if d["exited"] else ""}"><div class="hero">{pic}<div class="ov">'
            f'<span class="ord">{e(d["ord"])}</span><h2{f" id={chr(34)}{hid}{chr(34)}" if hid else ""}>{e(d["name"])}</h2>'
            f'<div class="tags">{"".join(f"<span>{e(t)}</span>" for t in tags)}</div></div>{mapc}</div>{kpis}{gal}</section>')


def overview(props, lang, e):
    """Portfolio map for the property-overview section: pins per city, list with portfolio weights."""
    ar = lang == "ar"; byc = {}
    for d in props:
        c = d.get("city")
        if not c or c not in CITY: continue
        key = CITY[c]; byc.setdefault(key, {"names": [], "lab": (d.get("cityline") or c).replace("مدينة ", "").replace("City of ", ""), "live": 0})
        byc[key]["names"].append(d); byc[key]["live"] += 0 if d["exited"] else 1
    if len(props) < 3 or not byc: return ""
    pts = [(lon, lat, v["lab"], v["live"] or "", v["live"] == 0) for (lon, lat), v in byc.items()]
    lists = []
    for (lon, lat), v in sorted(byc.items(), key=lambda kv: -len(kv[1]["names"])):
        items = []
        for d in v["names"]:
            w = d.get("weight")
            bar = f'<em><i style="width:{min(100, w / 30 * 100):.1f}%"></i></em><b>{w:.2f}%</b>'.replace(".00%", "%") if w is not None and not d["exited"] else (
                f'<b class="x">{"تم التخارج" if ar else "Exited"}</b>' if d["exited"] else "")
            items.append(f'<li{" class=x" if d["exited"] else ""}><span>{e(d["name"])}</span>{bar}</li>')
        lists.append(f'<div class="pvc"><h4>{e(v["lab"])}<small>{v["live"]}</small></h4><ul>{"".join(items)}</ul></div>')
    leg = ("النسبة من إجمالي قيمة العقارات كما في الرسم البياني للمحفظة" if ar else "Share of total property value, as in the portfolio chart") if any(d.get("weight") is not None for d in props) else ""
    return (f'<div class="pov"><div class="pvm">{map_svg(pts, big=True)}</div><div class="pvl">{"".join(lists)}'
            f'{f"<p class=pvlg>{e(leg)}</p>" if leg else ""}</div></div>')


CSS = """
.prop{break-inside:avoid;margin:0 0 3mm}
.prop ~ h3{break-after:avoid;margin-top:3mm}.prop ~ .facts{break-inside:auto}
.prop .hero{position:relative;height:86mm;border-radius:3mm;overflow:hidden;background:#12284B;margin:0 0 4mm}
.prop .hero figure{margin:0;height:100%}.prop .hero img{width:100%;height:100%;object-fit:cover;display:block}
.prop .hero .noimg{position:absolute;inset:0;background:linear-gradient(135deg,#12284B,#0B1733)}
.prop .ov{position:absolute;inset:auto 0 0 0;padding:16mm 7mm 6mm;background:linear-gradient(to top,rgba(11,23,51,.92) 0,rgba(11,23,51,.72) 45%,rgba(11,23,51,0) 100%);color:#fff}
.prop .ord{display:inline-block;font:600 7.6pt/1 'Alexandria',sans-serif;letter-spacing:%(LS)s;color:#9DB8E0;margin:0 0 2.2mm}
.prop h2{color:#fff;font-size:19pt;line-height:1.25;margin:0 0 3mm;font-family:'Alexandria',sans-serif;font-weight:600}
.prop .tags{display:flex;flex-wrap:wrap;gap:1.6mm}.prop .tags span{font-size:7.4pt;line-height:1;padding:1.6mm 2.6mm;border-radius:5mm;background:rgba(255,255,255,.14);border:.2mm solid rgba(255,255,255,.35);color:#fff}
.prop.ex .tags span:last-child{background:#3B7DD8;border-color:#3B7DD8}
.prop.ex .hero img{filter:saturate(.55)}
.pmap{position:absolute;top:5mm;%(END)s:5mm;width:34mm;padding:2.2mm 2.2mm 1.6mm;border-radius:2.2mm;background:rgba(255,255,255,.92);text-align:center;box-shadow:0 1mm 3mm rgba(11,23,51,.25)}
.pmap svg{display:block;width:100%;height:auto}.pmap span{display:block;font-size:6.8pt;color:#12284B;font-weight:600;margin-top:.6mm}
.kps{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm;margin:0 0 5mm}.kps.k3{grid-template-columns:repeat(3,1fr)}.kps.k2{grid-template-columns:repeat(2,1fr)}.kps.k1{grid-template-columns:1fr}
.kp{border-top:.8mm solid #3B7DD8;background:#F3F6FB;padding:3mm 3.2mm 3mm;border-radius:0 0 1.6mm 1.6mm;display:flex;flex-direction:column;gap:1.2mm}
.kp b{font:600 15pt/1.15 'Alexandria',sans-serif;color:#12284B;direction:ltr;unicode-bidi:isolate;text-align:%(START)s}.kp b small{font-size:7.6pt;font-weight:500;color:#5A6478;margin-inline-start:1mm}
.kp.tx b{font-size:11.5pt;line-height:1.3;direction:inherit;text-align:%(START)s}
.kp span{font-size:7.4pt;line-height:1.35;color:#5A6478}
.kp em{display:block;height:1.3mm;border-radius:1mm;background:#DCE3EE;overflow:hidden;margin-top:.6mm}.kp em i{display:block;height:100%;background:#3B7DD8;border-radius:1mm}
.pov{display:grid;grid-template-columns:1.05fr 1fr;gap:7mm;align-items:start;margin:4mm 0 6mm;break-inside:avoid}
.pov .pvm{background:#F3F6FB;border-radius:3mm;padding:5mm}.pov svg{width:100%;height:auto;display:block}
.pov .ml{font:600 1.05px 'Alexandria',sans-serif;fill:#12284B}.pov .mn{font:600 .9px 'Alexandria',sans-serif;fill:#3B7DD8}
.pov .pvc{margin:0 0 4mm}.pov h4{font:600 10pt/1.3 'Alexandria',sans-serif;color:#12284B;margin:0 0 1.6mm;display:flex;align-items:center;gap:2mm;border-bottom:.5mm solid #3B7DD8;padding-bottom:1.2mm}
.pov h4 small{font-size:7pt;background:#3B7DD8;color:#fff;border-radius:3mm;padding:.6mm 2mm}
.pov ul{list-style:none;margin:0;padding:0}.pov li{display:grid;grid-template-columns:1fr 22mm 12mm;gap:2mm;align-items:center;font-size:7.8pt;line-height:1.35;padding:1.2mm 0;border-bottom:.2mm solid #DCE3EE}
.pov li em{display:block;height:1.6mm;background:#DCE3EE;border-radius:1mm;overflow:hidden}.pov li em i{display:block;height:100%;background:#3B7DD8}
.pov li b{font-size:7.8pt;color:#12284B;direction:ltr;text-align:%(END)s}.pov li.x{color:#8A93A6}.pov li b.x{grid-column:2/4;color:#8A93A6;font-weight:500;text-align:%(END)s}
.pov .pvlg{font-size:6.8pt;color:#5A6478;margin:1mm 0 0}
"""
