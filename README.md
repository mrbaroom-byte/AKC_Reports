# منصة البيانات الربعية — صناديق أسواق المال

موقع داخلي لشركة الخبير المالية يُصدر البيان الربعي لصناديق أسواق المال (صندوق 2030، والخبير للدخل، والخبير للنمو والدخل) بالعربية والإنجليزية بصيغ PDF وWord وHTML، بهوية المستندات المعتمدة نفسها.

## كيف يعمل
1. تُدخل أرقام FACO، ومحتوى إدارة أسواق المال، وأسعار تداول، في صفحة الصندوق للربع.
2. يتحقق النظام من البيانات آليًا (الحقول الناقصة، ومجاميع التوزيع، وتغيّر الأرقام، وتطابق اللغتين).
3. يبني البيان على البيان المعتمد للربع السابق: النصوص الثابتة كما هي، والتواريخ تنتقل إلى الربع الجديد، والأرقام تُستبدل.
4. «إصدار المسودات» يُخرج المسودة؛ «اعتماد النسخة النهائية» يجعلها أساس الربع التالي.

## التشغيل على Railway
- يُبنى من `Dockerfile` (Playwright + Chromium).
- متغيرات: `ADMIN_PASSWORD` (كلمة الدخول)، `SESSION_SECRET` (اختياري)، `DATA_DIR=/data`.
- وحدة تخزين (Volume) مركّبة على `/data` لحفظ البيانات والملفات.

## البنية
- `app/` الموقع (FastAPI): `model.py` البيانات والتحقق، `pipeline.py` الإخراج، `store.py` التخزين، `records.py` البيانات المنشورة.
- `app/static/` واجهة الموقع: `app.css` (نظام التصميم: كحلي الخبير وأزرق أسواق المال، دون أخضر أو أحمر)، `app.js` (الطلبات والتنبيهات ونافذة التأكيد)، والشعارات.
- الحماية: الكتابة من الموقع نفسه فقط (فحص Origin)، وإيقاف الدخول ربع ساعة بعد 8 محاولات فاشلة، وبيانات JSON في الصفحات مُهرَّبة، ويُبنى مستند واحد في كل مرة لأن المحرك يكتب في مجلدات مشتركة.
- فحص الاختلاف بين العربي والإنجليزي يقارن رسوم التوزيع بقيمها لا بترتيبها؛ وعند تغيير الفحص تُرفع `CHECK_V` في `records.py` فيُعاد حسابه عند التشغيل.
- `engine/` محرك المستندات: `i30/render.py`، و`v3/` (الهوية والمراجعات وWord)، وقوالب الصناديق المنشورة للربع الثاني 2026م أساسًا أول.

## Published statements as records
At start-up every statement in `engine/published/<fund>/<q>` (with its AR/EN structs in `engine/<dir>/struct/`) is imported once as a `published` record; numbers that differ between the Arabic and English versions are stored in `conflicts`.
`/records` lists them per fund; `/r/<fund>/<q>` shows every field. Only the admin corrects: save a draft (values only), preview PDF/Word, then approve with a reason. Approval keeps the original struct once (`structs/<fund>/original/`), logs each change in `corrections`, writes the corrected struct (the next quarter builds on it), issues a corrected PDF/Word under `out/<fund>/<q>/corrected/<time>/`, and sets the status `corrected`. Published files are never replaced; later quarters are not regenerated.
