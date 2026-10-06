"""Turn the print HTML (out/html/<doc>.<lang>.html) into the web version published in the document centre
(hub/html/<doc>.<lang>.html): file:// assets → hub/assets/, original signed pages → a link to the original PDF,
and write hub/manifest.json with each document's partners and a content hash (used to flag stale PDFs)."""
import os, re, json, hashlib, shutil, datetime, sys
CODE = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(CODE, "hub")
B = os.path.abspath(os.environ.get("FUND_DIR") or CODE)
CFG = json.load(open(os.path.join(B, "fund.json"), encoding="utf-8")) if os.path.exists(os.path.join(B, "fund.json")) else {}
FK = CFG.get("key", "")            # "" for the 2030 fund (keeps its original paths/keys), e.g. "reit"
SUB = (FK + "/") if FK else ""
PFX = CFG.get("file_prefix", "AKC-DIF2030")
os.makedirs(os.path.join(H, "html", SUB), exist_ok=True); os.makedirs(os.path.join(H, "assets"), exist_ok=True)
REG = {p["slug"]: p for p in json.load(open(os.path.join(CODE, "graphics", "registry", "partners.json")))}
STEM = {'tc': 'TC', 'exec': 'EXEC-SUMMARY', 'factsheet': 'FACTSHEET', 'faq': 'FAQ', 'voting': 'VOTING-POLICY', 'annual-2024': 'ANNUAL-REPORT-2024', 'annual-2025': 'ANNUAL-REPORT-2025'}
STEM.update(CFG.get("stems", {}))
URL2030 = {(d["id"], d["side"]): d["url"] for d in json.load(open(os.path.join(CODE, "docs2.json")))}
def stem(i):
    if i in STEM: return STEM[i]
    m = re.match(r'annual-(\d{4})$', i)
    if m: return f"ANNUAL-REPORT-{m.group(1)}"
    m = re.match(r'q(\d)-(\d{4})', i); return f'QUARTERLY-STATEMENT-{m.group(2)}-Q{m.group(1)}'
FIELDS = ["name_ar", "name_en", "address_ar", "address_en", "website", "tollfree", "logo_asset", "status"]
def phash(slugs):
    """Same algorithm as the hub page (djb2 over JSON of the partner fields) so the page can tell when a PDF is stale."""
    arr = [[s] + [str(REG.get(s, {}).get(f, "") or "") for f in FIELDS] for s in sorted(slugs)]
    txt = json.dumps(arr, ensure_ascii=False, separators=(",", ":"))
    h = 5381
    for ch in txt:
        for cu in (ch.encode("utf-16-le")[i:i + 2] for i in range(0, len(ch.encode("utf-16-le")), 2)):
            h = (h * 33 + int.from_bytes(cu, "little")) & 0xFFFFFFFF
    return format(h, "08x")
def convert(doc, lang):
    src = open(os.path.join(B, "out", "html", f"{doc}.{lang}.html"), encoding="utf-8").read()
    ar = lang == "ar"
    # original signed pages → one link card per run of pages
    orig_pdf = (CFG.get("orig_urls", {}).get(f"{doc}.{lang}") or "") if FK else URL2030.get((doc, lang.upper()), "")
    label = ("الصفحات الأصلية الموقّعة (القوائم المالية المدققة وتقرير المراجع ونماذج التوقيع) — افتح الملف الأصلي" if ar else
             "Original signed pages (audited financial statements, auditor's report, signature forms) — open the original file")
    src = re.sub(r'(?:<div class="orig">(?:<div id="op-\d+"[^>]*></div>)?<img src="[^"]+"></div>)+',
                 lambda m: "".join(f'<span id="{a}"></span>' for a in re.findall(r'id="(op-\d+)"', m.group(0))) +
                 (f'<div class="note" style="margin:6mm 0"><a href="{orig_pdf}" target="_blank" rel="noopener">{label}</a> · {m.group(0).count("<img")} {"صفحة" if ar else "pages"}</div>' if orig_pdf else
                  f'<div class="note" style="margin:6mm 0">{label.split(" — ")[0]} · {m.group(0).count("<img")} {"صفحة" if ar else "pages"}</div>'), src)
    def asset(m):
        path = m.group(2)
        if not os.path.exists(path): return m.group(0)
        if "/graphics/img/" in path:
            from PIL import Image; import io, base64
            im = Image.open(path).convert("RGB"); im.thumbnail((900, 900)); buf = io.BytesIO(); im.save(buf, "JPEG", quality=70, optimize=True)
            return m.group(1) + "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        hsh = hashlib.md5(open(path, "rb").read()).hexdigest()[:8]
        name = f"{hsh}-{os.path.basename(path)}"
        dst = os.path.join(H, "assets", name)
        if not os.path.exists(dst): shutil.copy(path, dst)
        return f'{m.group(1)}assets/{name}'
    src = re.sub(r'(src="|url\()file://([^")]+)', asset, src)
    slugs = sorted(set(re.findall(r'data-p="([a-z0-9\-]+)"', src)))
    body_hash = hashlib.md5(re.sub(r'\s+', ' ', src).encode()).hexdigest()[:12]
    open(os.path.join(H, "html", SUB, f"{doc}.{lang}.html"), "w", encoding="utf-8").write(src)
    return {"fund": FK or "dif2030", "key": (FK + "." if FK else "") + f"{doc}.{lang}", "doc": doc, "lang": lang, "html": f"html/{SUB}{doc}.{lang}.html", "pdf": f"new/{SUB}{PFX}-{stem(doc)}-{lang.upper()}.pdf",
            "partners": slugs, "partners_hash": phash(slugs), "content_hash": body_hash}
if __name__ == "__main__":
    docs = CFG.get("doc_ids") or ["tc", "exec", "factsheet", "faq", "voting", "annual-2024", "annual-2025", "q3-2024", "q4-2024", "q1-2025", "q2-2025", "q3-2025", "q4-2025", "q1-2026", "q2-2026"]
    man = {"built_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d %H:%M"), "docs": [convert(d, l) for d in docs for l in ("ar", "en")]}
    json.dump(man, open(os.path.join(H, f"manifest{'-' + FK if FK else ''}.json"), "w"), ensure_ascii=False, indent=1)
    print(len(man["docs"]), sum(len(x["partners"]) > 0 for x in man["docs"]), "docs with partners")
