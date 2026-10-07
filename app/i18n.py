"""Interface language (Arabic / English).

Arabic is the source language of the interface. English is produced from this catalogue:
- templates and the shared script are translated once at load time (`source`), segment by segment;
- strings created at run time (statuses, messages, dates, quarter names, event lines) go through `T`.
Statement content (the documents themselves, in each language) is never passed through this catalogue.
"""
import re

AR = '؀-ۿ'
SEG = re.compile(rf'[{AR}](?:[{AR}\s،؛؟.:·«»()%0-9\-–/+*]|(?:[A-Za-z][A-Za-z0-9&/.\-]*)(?=[\s{AR}،.)»:]))*')
EN_M = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
AR_M = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
QORD = {'الأول': 'Q1', 'الثاني': 'Q2', 'الثالث': 'Q3', 'الرابع': 'Q4'}

C = {
    # ---- shell ----
    'البيانات الربعية': 'Quarterly Statements', 'الخبير المالية': 'Alkhabeer Capital', 'الصفحة الرئيسية': 'Home', 'التنقل': 'Navigation',
    'الربع الحالي': 'Current quarter', 'البيانات المنشورة': 'Published statements', 'المستخدمون': 'Users', 'مركز المستندات': 'Document centre',
    'خروج': 'Sign out', 'شركة الخبير المالية · ترخيص هيئة السوق المالية رقم': 'Alkhabeer Capital · CMA licence no.', 'للاستخدام الداخلي': 'Internal use',
    'النسخ الاحتياطية': 'Backups', 'سجل التدقيق': 'Audit log', 'اللغة': 'Language', 'المظهر': 'Theme', 'فاتح': 'Light', 'داكن': 'Dark', 'تلقائي': 'System',
    'منصة البيانات الربعية': 'Quarterly statements platform', 'تخطَّ إلى المحتوى': 'Skip to content',
    # ---- roles / statuses ----
    'المعتمِد': 'Approver', 'مُدخل البيانات': 'Data entry', 'لم يبدأ': 'Not started', 'قيد الإدخال': 'In progress', 'مسودة جاهزة': 'Draft ready',
    'بانتظار الاعتماد': 'Awaiting approval', 'أُعيد للتعديل': 'Returned for changes', 'نهائي': 'Final', 'منشور': 'Published', 'منشور · مصحَّح': 'Published · corrected',
    # ---- funds ----
    'صندوق الخبير للدخل المتنوع 2030 المتداول': 'Alkhabeer Diversified Income Traded Fund 2030', 'صندوق الخبير للدخل المتنوع المتداول': 'Alkhabeer Diversified Income Traded Fund',
    'صندوق الخبير للنمو والدخل': 'Alkhabeer Growth and Income Fund',
    # ---- backups ----
    'نسخة كاملة كل يوم تُحفظ آخر': 'A full backup every day; the last', 'منها، ونسخة قبل كل اعتماد نهائي أو تصحيح تُحفظ 90 يومًا. تضم قاعدة البيانات، وملفات البيانات وأصولها المنشورة، والملفات النهائية والمصحّحة، والملفات المرفوعة.': 'are kept, plus one before every final approval or correction, kept for 90 days. Each holds the database, the statement data and published originals, the final and corrected files, and uploaded files.',
    'إنشاء نسخة الآن': 'Back up now', 'النسخة': 'Version', 'الملف': 'File', 'النوع': 'Type', 'التاريخ': 'Date', 'الحجم': 'Size', 'يومية': 'Daily', 'قبل اعتماد أو تصحيح': 'Before approval or correction',
    'يدوية': 'Manual', 'تنزيل': 'Download', 'لا نسخ بعد. تُنشأ أول نسخة يومية خلال ساعة من تشغيل الخادم.': 'No backups yet. The first daily backup is made within an hour of the server starting.',
    'النسخ محفوظة على خادم المنصة نفسه، فلا تحمي من فقدانه. نزّل نسخة دوريًا واحفظها في SharePoint إلى أن يُفعَّل النسخ الخارجي التلقائي.': 'Backups are stored on the platform server itself, so they do not protect against losing it. Download one regularly and keep it in SharePoint until automatic off-site backup is enabled.',
    'تُنشأ': 'Creating', 'أُنشئت النسخة.': 'Backup created.',
    # ---- editor ----
    'يُبنى على البيان المعتمد لـ': 'Builds on the approved statement for ', 'مراحل البيان': 'Statement stages', 'الإدخال': 'Entry', 'المسودة': 'Draft', 'الاعتماد': 'Approval',
    'أرقام FACO': 'FACO figures', 'مدير الصندوق': 'Fund manager', 'تداول والرسم': 'Tadawul & chart', 'رسم الأداء': 'Performance chart', 'الملاحظات والسجل': 'Notes & history',
    'ملاحظات المراجعين': 'Reviewer notes', 'تظهر هنا أيضًا ملاحظات الإعادة للتعديل': 'Notes from returns for changes also appear here',
    'ملاحظات على المسودة، ومصدر كل رقم يحتاج تأكيدًا': 'Notes on the draft, and the source of any figure that needs confirming', 'حفظ الملاحظات': 'Save notes',
    'السجل': 'History', 'التحقق': 'Checks', 'يُحسب': 'Calculating', 'المحسوب آليًا': 'Calculated', 'استلام الأرقام بملف': 'Receive figures by',
    'نزّل القالب وأرسله للجهات: صفحة لـ FACO، وصفحة لإدارة أسواق المال، وصفحة لتداول. ثم ارفع الملف المعبّأ لتراجع التغييرات قبل اعتمادها في النموذج.': 'Download the template and send it out: one sheet for FACO, one for Capital Markets, one for Tadawul. Then upload the completed file to review the changes before they go into the form.',
    'تنزيل القالب': 'Download template', 'رفع ملف معبّأ': 'Upload completed file', 'الملفات': 'Files', 'لم تصدر مسودة بعد.': 'No draft issued yet.', 'آخر الأحداث': 'Recent activity',
    'آخر حفظ': 'Last saved', 'حفظ': 'Save', 'إصدار المسودات': 'Issue drafts', 'رفع للاعتماد': 'Submit for approval', 'إعادة للتعديل': 'Return for changes',
    'اعتماد النسخة النهائية': 'Approve final version', 'السابق': 'Previous', 'التقويم والأحجام': 'Valuation and size',
    'المصدر: إدارة عمليات الصناديق والحفظ (FACO)': 'Source: Fund Administration & Custody Operations (FACO)', 'تاريخ التقويم': 'Valuation date', 'آخر يوم تقويم في الربع': 'Last valuation day of the quarter',
    'صافي قيمة الوحدة (ر.س.)': 'NAV per unit (SAR)', 'حجم الصندوق: إجمالي الأصول (ر.س.)': 'Fund size: total assets (SAR)', 'عدد الوحدات القائمة': 'Units outstanding',
    'يُؤكَّد مصدره': 'Source to confirm', 'متوسط صافي الأصول خلال الربع (ر.س.)': 'Average NAV in the quarter (SAR)', 'عدد أيام المتوسط المرجح': 'Weighted average days',
    'المصاريف': 'Expenses', 'المصدر: FACO · النسب تُحسب آليًا': 'Source: FACO · ratios are calculated', 'الأتعاب والمصروفات الإجمالية (ر.س.)': 'Total fees and expenses (SAR)',
    'الاقتراض (ر.س.) · فارغ إن لم يوجد': 'Borrowing (SAR) · leave empty if none', 'مصاريف التعامل (ر.س.)': 'Dealing expenses (SAR)', 'استثمار مدير الصندوق (ر.س.)': 'Fund manager’s investment (SAR)',
    'الأرباح الموزعة': 'Distributions', 'المصدر: FACO · فارغة إن لم يوزَّع في الربع': 'Source: FACO · leave empty if nothing was distributed', 'إجمالي الأرباح الموزعة (ر.س.)': 'Total distributions (SAR)',
    'عدد الوحدات المستحقة': 'Entitled units', 'الربح الموزع لكل وحدة (ر.س.)': 'Distribution per unit (SAR)', 'أحقية التوزيعات': 'Distribution entitlement',
    'الاسم بالعربية': 'Name in Arabic', 'النسبة %': 'Share %', 'حذف البند': 'Remove item', 'تعليق مدير الصندوق': 'Fund manager commentary',
    'المصدر: إدارة أسواق المال · يُكتب كل نص بلغته، ولا يُترجم أحدهما من الآخر': 'Source: Capital Markets · each language is written on its own',
    'المصدر: إدارة أسواق المال · كل نص بلغته، ويمكن اقتراح ترجمة تُراجع قبل الاعتماد': 'Source: Capital Markets · each language on its own; a suggested translation can be reviewed before approval',
    'سطر يبدأ بـ': 'A line starting with', 'عنوان فرعي · سطر يبدأ بـ': 'subheading · a line starting with', 'بند في قائمة · سطر فارغ بين الفقرات': 'list item · blank line between paragraphs',
    'العربية': 'Arabic', 'الإنجليزية': 'English', 'أكبر عشرة استثمارات': 'Top ten investments', 'المصدر: إدارة أسواق المال': 'Source: Capital Markets', 'بند': 'item',
    'المصدر: إدارة أسواق المال · المجموع 100%': 'Source: Capital Markets · total 100%', 'العائد %': 'Return %',
    'المصدر: إدارة أسواق المال · فارق الأداء يُحسب آليًا · فارغ إن لم ينطبق': 'Source: Capital Markets · spread is calculated · leave empty if not applicable',
    'الصندوق': 'Fund', 'المؤشر الاسترشادي': 'Benchmark', 'القيم الباهتة داخل الخانات هي قيم الربع السابق للمقارنة.': 'Faint values inside the fields are last quarter’s, for comparison.',
    'الأداء والمخاطر': 'Performance and risk', 'الملكية والتصنيف الائتماني': 'Ownership and credit rating', 'ملكية تامة %': 'Full ownership %', 'حق منفعة %': 'Usufruct %',
    'مكرر الربحية (P/E)': 'Price/earnings (P/E)', 'التصنيف الائتماني لأكبر عشرة استثمارات': 'Credit rating of the top ten investments', 'الأداة': 'Instrument', 'المُصدِر': 'Issuer',
    'الوكالة': 'Agency', 'سعر الوحدة في السوق': 'Unit market price', 'المصدر: تداول السعودية · الرمز': 'Source: Saudi Exchange · symbol',
    'سعر الإغلاق في آخر يوم تداول من الربع (ر.س.)': 'Closing price on the last trading day of the quarter (SAR)', 'سوق الصناديق في موقع تداول': 'Funds market on the Tadawul site',
    'سعر الإغلاق (ر.س.)': 'Closing price (SAR)', 'القيمة': 'Value', 'الصندوق %': 'Fund %', 'المؤشر %': 'Benchmark %', 'رسم سعر السوق منذ البداية': 'Market price since inception',
    'رسم الأداء مقارنة بالمؤشر': 'Performance against the benchmark', 'المصدر: تداول · تُضاف نقاط هذا الربع إلى السلسلة المحفوظة': 'Source: Tadawul · this quarter’s points are added to the saved series',
    'المصدر: إدارة أسواق المال · العائد التراكمي منذ البداية': 'Source: Capital Markets · cumulative return since inception', 'حذف النقطة': 'Remove point', 'نقطة': 'point',
    'آخر نقاط السلسلة': 'Latest points in the series', 'بيانات الاتصال': 'Contact details', 'رقم الهاتف في البيان': 'Phone number in the statement',
    'فارغ لإبقاء الرقم الحالي': 'Leave empty to keep the current number', 'المجموع': 'Total', 'من 10': 'of 10', 'كلمة': 'words', 'تعديلات غير محفوظة': 'Unsaved changes',
    'انتقل إلى الحقل': 'Go to field', 'لا ملاحظات. البيانات جاهزة للإصدار.': 'No issues. The data is ready to issue.', 'صافي الأصول': 'Net assets',
    'تغير سعر السوق': 'Market price change', 'تغير صافي القيمة': 'NAV change', 'نسبة المصاريف (TER)': 'Expense ratio (TER)', 'العلاوة على صافي القيمة': 'Premium to NAV',
    'الخصم عن صافي القيمة': 'Discount to NAV', 'التوزيع إلى صافي الأصول': 'Distribution to net assets', 'فارق الأداء (3 أشهر)': 'Performance spread (3 months)', 'تعذّر التحقق': 'Checks could not run',
    'أُعيد البيان للتعديل. راجع ملاحظات المعتمِد في تبويب «الملاحظات والسجل»، ثم عدّل وأصدر المسودات من جديد.': 'The statement was returned for changes. Read the approver’s notes in “Notes & history”, then edit and issue the drafts again.',
    'البيان مرفوع للاعتماد. راجع المسودة في «الملفات»، ثم اعتمدها أو أعدها للتعديل مع ملاحظاتك.': 'The statement is awaiting approval. Review the draft under “Files”, then approve it or return it with your notes.',
    'البيان مرفوع للاعتماد، ولا يُعدَّل حتى يعتمده المعتمِد أو يعيده للتعديل.': 'The statement is awaiting approval and cannot be edited until the approver approves it or returns it.',
    'البيان معتمد نهائيًا وصار أساس الربع التالي.': 'The statement is final and is now the base for the next quarter.', 'يمكنك إعادته للتعديل عند الحاجة.': 'You can return it for changes if needed.',
    'أكمل النقص المذكور في «التحقق» أولًا': 'First complete what “Checks” lists as missing', 'لا شيء بعد.': 'Nothing yet.', 'النسخة النهائية': 'Final version', 'تنزيل الكل': 'Download all',
    'معاينة': 'Preview', 'حُفظ': 'Saved', 'يُحفظ': 'Saving', 'حُفظت البيانات.': 'Data saved.', 'يُصدر': 'Issuing', 'أكمل النقص المذكور في «التحقق» أولًا.': 'First complete what “Checks” lists as missing.',
    'احفظ وأصدر المسودات بعد آخر تعديل أولًا.': 'Save and issue the drafts after your last change first.', 'رفع البيان للاعتماد؟': 'Submit the statement for approval?',
    'يُقفل البيان للتعديل حتى يعتمده المعتمِد أو يعيده إليك مع ملاحظاته.': 'The statement is locked until the approver approves it or returns it to you with notes.',
    'رُفع البيان للاعتماد.': 'Submitted for approval.', 'اعتماد النسخة النهائية؟': 'Approve the final version?',
    'تُصدر النسخة النهائية بالعربية والإنجليزية، وتصبح أساس بيان الربع التالي.': 'The final version is issued in Arabic and English and becomes the base for the next quarter’s statement.',
    'اعتماد': 'Approve', 'يُعتمد': 'Approving', 'إعادة البيان للتعديل': 'Return the statement for changes',
    'تُضاف ملاحظاتك إلى «الملاحظات» ويُفتح البيان لمُدخل البيانات.': 'Your notes are added to “Notes” and the statement reopens for data entry.',
    'ما الذي يحتاج تعديلًا؟ (اختياري)': 'What needs changing? (optional)', 'أُعيد البيان للتعديل.': 'Returned for changes.', 'اعتُمدت النسخة النهائية.': 'The final version is approved.',
    'صدرت المسودات. راجعها ثم ارفعها للاعتماد.': 'Drafts issued. Review them, then submit for approval.', 'صدرت المسودات بالعربية والإنجليزية.': 'Drafts issued in Arabic and English.',
    'حُفظت الملاحظات.': 'Notes saved.', 'البيان مقفل، فلا يُستورد إليه.': 'The statement is locked, so nothing can be imported into it.', 'تُقرأ': 'Reading', 'تعذّرت قراءة الملف.': 'The file could not be read.',
    'لا جديد في الملف: كل قيمه مطابقة للنموذج.': 'Nothing new in the file: every value matches the form.', 'قراءة': 'Reading', 'تطبيق': 'Apply', 'تغيير': 'change(s)', 'إغلاق': 'Close',
    'تُطبَّق في النموذج ولا تُحفظ حتى تضغط «حفظ».': 'They go into the form and are not saved until you press “Save”.', 'البند': 'Item', 'الحالي': 'Current', 'من الملف': 'From file',
    'طُبّق': 'Applied', 'تغيير من الملف. راجعها ثم احفظ.': 'change(s) from the file. Review them, then save.',
    # ---- home ----
    'دورة البيان الربعي · صناديق أسواق المال': 'Quarterly statement cycle · capital markets funds', 'الربع السابق': 'Previous quarter', 'الربع التالي': 'Next quarter',
    'العودة إلى الربع المستحق': 'Back to the quarter due', 'نهاية الربع': 'Quarter end', 'آخر موعد للنشر (المادة 78 د)': 'Publication deadline (Art. 78(d))', 'تجاوز الموعد بـ': 'Overdue by ',
    'يوم': 'day(s)', 'اليوم': 'Today', 'باقٍ': '', 'يومًا': 'days left', 'التقدم': 'Progress', 'متداول': 'Traded', 'عام مفتوح': 'Open-ended', 'نقص يمنع الإصدار': 'blocking issue(s)',
    'تنبيه': 'warning(s)', 'ينتظر اعتماد الربع السابق': 'Waiting for the previous quarter’s approval', 'آخر تعديل': 'Last edited', 'منشور في مستندات الصندوق': 'Published in the fund documents',
    'لم يبدأ بعد': 'Not started yet', 'عرض البيان': 'View statement', 'ابدأ الإدخال': 'Start entry', 'مراجعة واعتماد': 'Review and approve', 'متابعة': 'Continue',
    'دورة الربع': 'The quarter’s cycle', 'من استلام الأرقام إلى النسخة النهائية': 'From receiving the figures to the final version', 'أرقام الصندوق': 'Fund figures',
    'حجم الصندوق، وصافي قيمة الوحدة، والأتعاب والمصاريف، والتوزيعات.': 'Fund size, NAV per unit, fees and expenses, and distributions.', 'محتوى مدير الصندوق': 'Fund manager content',
    'التعليق باللغتين، والملكية، وأكبر الاستثمارات، والتصنيف، وتوزيع الأصول، والعائد والمخاطر.': 'Commentary in both languages, ownership, top investments, ratings, asset allocation, returns and risk.',
    'إدارة أسواق المال': 'Capital Markets', 'أسعار السوق': 'Market prices', 'سعر الوحدة في نهاية الربع، وأسعار نهاية كل شهر لرسم السعر.': 'Unit price at quarter end, and month-end prices for the price chart.',
    'تداول السعودية': 'Saudi Exchange', 'التحقق والمسودات': 'Checks and drafts', 'فحص آلي للنقص والمجاميع والتغيّرات، ثم إصدار العربي والإنجليزي بصيغتي PDF وWord.': 'Automatic checks for gaps, totals and changes, then Arabic and English issued as PDF and Word.',
    'جمع ملاحظات المراجعين، ثم اعتماد النسخة النهائية لتصبح أساس الربع التالي.': 'Collect reviewer notes, then approve the final version so it becomes the base for the next quarter.',
    # ---- login ----
    'الدخول · البيانات الربعية · الخبير المالية': 'Sign in · Quarterly Statements · Alkhabeer Capital', 'البيانات الربعية لصناديق أسواق المال': 'Quarterly statements for capital markets funds',
    'منصة داخلية تبني البيان الربعي لكل صندوق على البيان المعتمد للربع السابق، وتتحقق من الأرقام، وتُصدره بالعربية والإنجليزية بهوية مستندات الصناديق المعتمدة.': 'An internal platform that builds each fund’s quarterly statement on the previous quarter’s approved statement, checks the figures, and issues it in Arabic and English in the approved fund-document identity.',
    'صناديق': 'funds', 'لغتان مستقلتان': 'independent languages', 'صيغ الإصدار': 'output formats', 'تسجيل الدخول': 'Sign in', 'شركة الخبير المالية · للاستخدام الداخلي': 'Alkhabeer Capital · internal use',
    'لم تُضبط كلمة مرور المعتمِد بعد. أضف المتغير': 'The approver password is not set yet. Add the variable', 'في إعدادات الخدمة على Railway.': 'in the service settings on Railway.',
    'اسم المستخدم أو كلمة المرور غير صحيحة.': 'The username or password is incorrect.', 'محاولات كثيرة غير ناجحة. حاول مرة أخرى بعد ربع ساعة.': 'Too many failed attempts. Try again in 15 minutes.',
    'اسم المستخدم': 'Username', 'كلمة المرور': 'Password', 'إظهار': 'Show', 'إخفاء': 'Hide', 'دخول': 'Sign in', 'المعتمِد يكتب': 'The approver types',
    'أو يترك اسم المستخدم فارغًا. مُدخلو البيانات يستخدمون الحساب الذي أنشأه المعتمِد.': 'or leaves the username empty. Data entry users sign in with the account the approver created.',
    # ---- nobase ----
    'لا يبدأ هذا البيان قبل اعتماد بيان': 'This statement cannot start before the statement for',
    '، لأن النظام يبني كل ربع على البيان المعتمد للربع الذي قبله: النصوص الثابتة كما هي، والتواريخ تنتقل إلى الربع الجديد، والأرقام تُستبدل.': ' is approved, because each quarter is built on the approved statement of the quarter before: fixed text stays, dates move to the new quarter, and figures are replaced.',
    'فتح بيان': 'Open the statement for', 'العودة': 'Back',
    # ---- record ----
    'مسودة تصحيح': 'Correction draft', 'تعديل': 'change(s)', 'اختلاف بين اللغتين': 'AR/EN difference(s)', 'المنشور': 'Published', 'آخر تصحيح': 'Latest correction', 'ع': 'AR',
    'عرض فقط. تصحيح البيانات المنشورة للمعتمِد.': 'View only. Published statements are corrected by the approver.', 'التعديلات المحفوظة في المسودة': 'Changes saved in the draft',
    'لم تُعتمد بعد، والمنشور كما هو': 'Not approved yet; the published version is unchanged', 'القسم': 'Section', 'قبل': 'Before', 'بعد': 'After', 'النسخة العربية': 'Arabic version',
    'الاختلافات بين النسختين': 'AR/EN differences', 'سجل التصحيحات': 'Corrections log', 'عدّل أي قيمة ثم احفظ. تُبرز الخانات المعدّلة.': 'Edit any value, then save. Edited fields are highlighted.',
    'افتح القسم لعرض محتواه.': 'Open a section to see its content.', 'فتح الكل': 'Expand all', 'طي الكل': 'Collapse all', 'نتيجة التحقق من الملفات الأصلية المنشورة': 'Checked against the original published files',
    'قُرئت هذه الاختلافات من صفحات البيان الأصلي بالعربية والإنجليزية، وثبت أنها في المنشور نفسه. «مقترح» يعني أن المستند نفسه يحسم القيمة الصحيحة؛ «يحتاج مصدرًا» يعني أن الحسم يتطلب الرقم من FACO أو إدارة أسواق المال.': 'These differences were read from the pages of the original Arabic and English statements and are in the published files themselves. “Proposed” means the document itself settles the correct value; “Needs source” means FACO or Capital Markets must provide the figure.',
    'الحالة': 'Status', 'المقترح': 'Proposed', 'الدليل': 'Evidence', 'صُحِّح': 'Corrected', 'مقترح': 'Proposed', 'يحتاج مصدرًا': 'Needs source', 'ضعه في المسودة': 'Put in draft',
    'أرقام تختلف بين النسختين العربية والإنجليزية من البيان نفسه، رُصدت آليًا. تُقارن رسوم التوزيع بقيمها لا بترتيبها، وتُتجاهل فروق التقريب ومنحنيات الأداء (قُرئت من صور الرسوم المنشورة). صحّح النسخة الخاطئة من تبويبها.': 'Figures that differ between the Arabic and English versions of the same statement, found automatically. Allocation charts are compared by value, not order; rounding differences and performance lines (read from the published chart images) are ignored. Correct the wrong version in its own tab.',
    'العربي': 'Arabic', 'الإنجليزي': 'English', 'جدول': 'Table', 'رسم': 'Chart', 'لا اختلاف في الأرقام بين النسختين.': 'No figures differ between the two versions.', 'بواسطة': 'By', 'السبب': 'Reason',
    'لم يُصحَّح هذا البيان منذ نشره.': 'This statement has not been corrected since publication.', 'توجد مسودة تصحيح محفوظة. عاينها ثم اعتمدها.': 'A saved correction draft exists. Preview it, then approve it.',
    'عدّل أي قيمة ثم احفظ. يبقى المنشور كما هو حتى تعتمد التصحيح.': 'Edit any value, then save. The published version stays as it is until you approve the correction.', 'إلغاء المسودة': 'Discard draft',
    'معاينة PDF و': 'Preview PDF and ', 'حفظ التعديلات': 'Save changes', 'اعتماد التصحيح': 'Approve correction', 'عنوان القسم': 'Section title', 'عنوان فرعي': 'Subheading', 'فقرة': 'Paragraph',
    'ملاحظة': 'Note', 'قائمة (بند في كل سطر)': 'List (one item per line)', 'رسم بياني': 'Chart', 'المجموعة': 'Group', 'مقدمة': 'Introduction', 'معدّل': 'edited', 'جارٍ': 'In progress',
    'القيمة الحالية تغيّرت عن المنشور؛ عدّلها يدويًا.': 'The current value differs from the published one; edit it by hand.', 'في المسودة': 'In draft',
    'وُضع المقترح في المسودة. احفظ التعديلات، ثم عاين واعتمد مع ذكر السبب.': 'The proposal is in the draft. Save the changes, then preview and approve with a reason.', 'وُضع المقترح في المسودة.': 'Proposal added to the draft.',
    'تعديلات غير محفوظة.': 'Unsaved changes.', 'حُفظت المسودة': 'Draft saved', 'تعديل. المنشور لم يتغير.': 'change(s). The published version has not changed.',
    'لا فرق عن المنشور، فلم تُحفظ مسودة.': 'No difference from the published version, so no draft was saved.', 'حُفظت مسودة التصحيح.': 'Correction draft saved.', 'لا تعديلات.': 'No changes.',
    'احفظ التعديلات أولًا.': 'Save the changes first.', 'تُصدر المعاينة': 'Issuing preview', 'البيانات اللاحقة': 'Later statements', 'قد تتضمن أرقامًا من هذا البيان، ولا تُعدَّل تلقائيًا.': 'may carry figures from this statement and are not changed automatically.',
    'يُحفظ الأصل المنشور مرة واحدة، ويُسجَّل كل تعديل مع سببه، وتصدر نسخة مصحّحة (PDF وWord) دون استبدال الملفات المنشورة.': 'The published original is kept once, every change is logged with its reason, and a corrected version (PDF and Word) is issued without replacing the published files.',
    'سبب التصحيح': 'Reason for the correction', 'مثال: طلب هيئة السوق المالية رقم': 'For example: CMA request no.', 'بتاريخ': 'dated', 'اعتماد وإصدار النسخة المصحّحة': 'Approve and issue the corrected version',
    'إلغاء مسودة التصحيح؟': 'Discard the correction draft?', 'تُحذف التعديلات المحفوظة ومعاينتها، ويبقى المنشور كما هو.': 'The saved changes and their preview are deleted; the published version stays as it is.',
    # ---- records ----
    'بيانًا مستوردًا من مستندات الصناديق ومحفوظًا جداولَ قابلة للتصحيح. التصحيح للمعتمِد فقط، ولا يستبدل الملفات المنشورة، ويُسجَّل كل تعديل مع سببه.': 'statements imported from the fund documents and stored as correctable tables. Only the approver corrects; published files are never replaced, and every change is logged with its reason.',
    'الصناديق': 'Funds', 'بيانًا ربعيًا': 'quarterly statements', 'اختلافًا بين العربي والإنجليزي': 'AR/EN differences', 'تصحيحًا معتمدًا': 'approved corrections', 'بحث بالسنة': 'Filter by year',
    'تصفية بالسنة، مثل 2025': 'Filter by year, e.g. 2025', 'الربع': 'Quarter', 'اختلافات اللغتين': 'AR/EN differences', 'التصحيحات': 'Corrections', 'الملفات المنشورة': 'Published files',
    'فتح': 'Open', 'لا بيانات منشورة لهذا الصندوق.': 'No published statements for this fund.',
    # ---- users ----
    'حسابات مُدخلي البيانات. يُدخل كلٌّ منهم الأرقام ويُصدر المسودات ويرفعها للاعتماد، ولا يعتمد النسخة النهائية إلا المعتمِد.': 'Data entry accounts. Each enters figures, issues drafts and submits them for approval; only the approver approves the final version.',
    'كلمة المرور المؤقتة للحساب': 'Temporary password for', 'نسخ': 'Copy', 'تظهر مرة واحدة فقط ولا تُحفظ نصًا. سلّمها لصاحب الحساب مع اسم المستخدم. إن فُقدت فأنشئ كلمة مرور جديدة من الجدول.': 'Shown once only and never stored in clear. Give it to the account holder with the username. If it is lost, create a new password from the table.',
    'المستخدم': 'User', 'الصلاحية': 'Role', 'آخر دخول': 'Last sign-in', 'م': 'A', 'نشط': 'Active', 'كلمة المرور في إعدادات': 'Password in the settings of', 'لم يدخل بعد': 'Never signed in',
    'موقوف': 'Suspended', 'كلمة مرور جديدة': 'New password', 'إيقاف': 'Suspend', 'تفعيل': 'Activate', 'لا حسابات لمُدخلي البيانات بعد. أنشئ أول حساب من النموذج.': 'No data entry accounts yet. Create the first one with the form.',
    'حساب جديد': 'New account', 'الاسم الظاهر': 'Display name', 'مثل: إدارة تطوير المنتجات': 'e.g. Product Development', 'اسم المستخدم (بالإنجليزية)': 'Username (Latin letters)', 'إنشاء الحساب': 'Create account',
    'الصلاحيات': 'Roles', 'يُدخل أرقام الربع، ويُصدر المسودات، ويرفعها للاعتماد، ويكتب الملاحظات.': 'Enters the quarter’s figures, issues drafts, submits them for approval and writes notes.',
    'يعتمد النسخة النهائية أو يعيدها للتعديل، ويصحّح البيانات المنشورة، ويدير الحسابات.': 'Approves the final version or returns it, corrects published statements and manages accounts.',
    'إنشاء كلمة مرور جديدة لـ': 'Create a new password for ', '؟ تتوقف القديمة فورًا.': '? The old one stops working immediately.', 'نُسخ اسم المستخدم وكلمة المرور.': 'Username and password copied.',
    'تعذّر الإجراء': 'The action failed', 'رجوع': 'Cancel', 'الإدارة': 'Admin', 'تصدير': 'Export', 'بناء النسخة العربية': 'Building the Arabic version', 'بناء النسخة الإنجليزية': 'Building the English version', 'إخراج PDF': 'Producing PDF', 'إخراج Word العربي': 'Producing the Arabic Word file', 'إخراج Word الإنجليزي': 'Producing the English Word file', 'آخر 24 ساعة': 'Last 24 hours', 'مرفوض أو فاشل · 24 ساعة': 'Denied or failed · 24 h', 'طلبات · 24 ساعة': 'Requests · 24 h', 'الصفحات': 'Pages',
    'الانحراف المعياري': 'Standard deviation', 'مؤشر شارب': 'Sharpe ratio', 'خطأ التتبع': 'Tracking error', 'بيتا': 'Beta', 'ألفا': 'Alpha', 'مؤشر المعلومات': 'Information ratio',
    # ---- server messages ----
    'طلب من خارج الموقع.': 'Request from outside the site.', 'هذا الإجراء للمعتمِد فقط.': 'This action is for the approver only.', 'هذه الصفحة للمعتمِد فقط.': 'This page is for the approver only.',
    'البيان': 'The statement is', '، فلا يُعدَّل إلا بعد إعادته للتعديل.': ', so it can only be edited after it is returned for changes.', 'حفظ البيانات': 'saved the data',
    'تحديث الملاحظات': 'updated the notes', 'بانتظار انتهاء إصدار آخر': 'Waiting for another build to finish', 'تجهيز البيانات': 'Preparing data', 'يوجد نقص يمنع الإصدار. راجع قائمة التحقق.': 'Something is missing that blocks issuing. See the checks list.',
    'بناء النسخة': 'Building the', 'بقيت إشارات إلى الربع السابق': 'references to the previous quarter remain', 'إخراج': 'Producing', 'إخراج Word': 'Producing Word', 'تعذّر إخراج Word': 'Word output failed',
    'تعذّرت النسخة الاحتياطية قبل الاعتماد': 'Backup before approval failed', 'تعذّر الإخراج': 'Output failed', 'يُعتمد البيان بعد أن يُرفع للاعتماد.': 'A statement can be approved only after it is submitted for approval.',
    'في الطابور': 'Queued', 'أصدر المسودات بعد آخر تعديل، ثم ارفعها للاعتماد.': 'Issue the drafts after your last change, then submit them for approval.', 'رفع المسودة للاعتماد': 'submitted the draft for approval',
    'لا شيء بانتظار الاعتماد.': 'Nothing is awaiting approval.', 'ليس بيانًا منشورًا.': 'Not a published statement.', 'التصحيح يعدّل القيم فقط، ولا يضيف أقسامًا أو صفوفًا أو يحذفها.': 'A correction changes values only; it cannot add or remove sections or rows.',
    'حفظ مسودة تصحيح': 'saved a correction draft', 'إلغاء مسودة التصحيح': 'discarded the correction draft', 'تجهيز': 'Preparing', 'لا توجد مسودة تصحيح.': 'There is no correction draft.',
    'إصدار معاينة التصحيح': 'issued a correction preview', 'تعذّرت النسخة الاحتياطية قبل التصحيح': 'Backup before the correction failed', 'اكتب سبب التصحيح (مثل: طلب هيئة السوق المالية رقم': 'Write the reason for the correction (e.g. CMA request no.',
    '، فلا يُستورد إليه.': ', so nothing can be imported into it.', 'اختر ملف Excel.': 'Choose an Excel file.', 'الملف أكبر من 15 ميغابايت.': 'The file is larger than 15 MB.',
    'تعذّرت قراءة الملف. استخدم قالب المنصة بصيغة xlsx.': 'The file could not be read. Use the platform template in xlsx format.', 'قراءة ملف Excel': 'read an Excel file',
    'استيراد البيان المنشور من مستندات الصناديق': 'imported the published statement from the fund documents', 'إصدار المسودات': 'Issue drafts',
    'اعتماد النسخة النهائية': 'Approve final version', 'اعتماد التصحيح': 'Approve correction', 'الربع': 'Quarter',
    # ---- audit ----
    'كل ما يحدث في المنصة: الدخول والخروج، وكل تعديل بقيمته قبل وبعد، والإصدار والاعتماد، والتنزيل، والنسخ الاحتياطي. السجل مسلسل بسلسلة تجزئة، فأي تعديل أو حذف لسطر يكشفه التحقق.': 'Everything that happens on the platform: sign-ins and sign-outs, every change with its before and after value, issuing and approval, downloads and backups. The log is hash-chained, so editing or deleting any line is detected by the integrity check.',
    'سلامة السجل': 'Log integrity', 'سليم': 'Intact', 'مكسور عند السطر': 'Broken at entry', 'الإجراء': 'Action', 'الكائن': 'Object', 'التفاصيل': 'Details', 'العنوان': 'IP address',
    'الكل': 'All', 'من': 'From', 'إلى': 'To', 'تصفية': 'Filter', 'تصدير CSV': 'Export CSV', 'لا سجلات تطابق التصفية.': 'No entries match the filter.', 'السابقة': 'Newer', 'التالية': 'Older',
    'كل الإجراءات': 'All actions', 'كل المستخدمين': 'All users', 'سطرًا': 'entries', 'النتيجة': 'Result', 'نجح': 'OK', 'رُفض': 'Denied', 'فشل': 'Failed',
}
# audit action names
ACTIONS = {
    'auth.login': ('الدخول', 'Sign in'), 'auth.login_failed': ('دخول غير ناجح', 'Failed sign-in'), 'auth.logout': ('الخروج', 'Sign out'), 'auth.throttled': ('حظر مؤقت للدخول', 'Sign-in throttled'),
    'auth.denied': ('رفض صلاحية', 'Permission denied'), 'auth.origin': ('طلب من خارج الموقع', 'Cross-site request'),
    'user.create': ('إنشاء حساب', 'Create account'), 'user.reset': ('كلمة مرور جديدة', 'New password'), 'user.toggle': ('إيقاف أو تفعيل حساب', 'Suspend/activate account'),
    'statement.save': ('حفظ بيانات', 'Save data'), 'statement.notes': ('تحديث الملاحظات', 'Update notes'), 'statement.generate': ('إصدار المسودات', 'Issue drafts'),
    'statement.submit': ('رفع للاعتماد', 'Submit for approval'), 'statement.return': ('إعادة للتعديل', 'Return for changes'), 'statement.final': ('اعتماد نهائي', 'Final approval'),
    'statement.import': ('قراءة ملف Excel', 'Excel import'), 'statement.template': ('تنزيل قالب Excel', 'Excel template download'), 'statement.clear_test': ('حذف بيانات تجربة', 'Clear test data'),
    'record.draft': ('حفظ مسودة تصحيح', 'Save correction draft'), 'record.discard': ('إلغاء مسودة تصحيح', 'Discard correction draft'), 'record.preview': ('معاينة تصحيح', 'Correction preview'),
    'record.approve': ('اعتماد تصحيح', 'Approve correction'), 'file.download': ('تنزيل ملف', 'File download'), 'file.zip': ('تنزيل حزمة', 'Zip download'),
    'backup.create': ('نسخة احتياطية', 'Backup'), 'backup.download': ('تنزيل نسخة احتياطية', 'Backup download'), 'audit.export': ('تصدير سجل التدقيق', 'Audit export'),
    'pref.lang': ('تغيير اللغة', 'Language change'), 'pref.theme': ('تغيير المظهر', 'Theme change'),
}
_KEYS = sorted(C, key=len, reverse=True)


def source(text):
    """Translate an Arabic template/script source into English, segment by segment (unknown segments stay)."""
    def rep(m):
        raw = m.group(0); t = raw.rstrip(' (-–/+*:·'); tail = raw[len(t):]; core = t.strip(); lead = t[:len(t) - len(t.lstrip())]
        en = C.get(core)
        if en is not None: return lead + en + tail
        # a known phrase joined to others («المعتمِد: حفظ البيانات», «حفظ مسودة تصحيح (3 تعديل)»): translate each part
        parts = re.split(r'(\s*[:،—]\s*|\s*\(\s*|\s*\)\s*)', core)
        if len(parts) > 1 and any(p.strip() in C for p in parts):
            return lead + ''.join(C.get(p.strip(), p) if p.strip() else p for p in parts) + tail
        return raw
    return SEG.sub(rep, text)


def qlabel_en(s):
    m = re.match(r'^الربع (الأول|الثاني|الثالث|الرابع) (\d{4})م?$', s.strip())
    return f'{QORD[m.group(1)]} {m.group(2)}' if m else None


def date_en(s):
    def rep(m): return f'{int(m.group(1))} {EN_M[AR_M.index(m.group(2))]} {m.group(3)}'
    return re.sub(rf'(\d{{1,2}}) ({"|".join(AR_M)}) (\d{{4}})م?', rep, s)


def T(s, lang='ar'):
    """A run-time interface string in the viewer's language."""
    if lang != 'en' or not isinstance(s, str) or not re.search(f'[{AR}]', s): return s
    if s in C: return C[s]
    q = qlabel_en(s)
    if q: return q
    s = date_en(s)
    s = re.sub(r'(\d+) (تعديل|تغيير)', r'\1 change(s)', s)
    s = re.sub(r'الربع (الأول|الثاني|الثالث|الرابع) (\d{4})م?', lambda m: f'{QORD[m.group(1)]} {m.group(2)}', s)
    return source(s)


def deep(v, lang, skip=('data', 'conflicts', 'corrections', 'verified', 's', 'items', 'details', 'ua')):
    """Translate interface strings inside a render context. Statement content is left alone."""
    if lang != 'en': return v
    if isinstance(v, str): return T(v, lang)
    if isinstance(v, list): return [deep(x, lang) for x in v]
    if isinstance(v, dict): return {k: (x if k in skip or k.endswith('_json') else deep(x, lang)) for k, x in v.items()}
    return v
