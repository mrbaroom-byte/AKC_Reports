"""Fund manager commentary: improve the wording, translate between Arabic and English, and check its figures.

Every result is a suggestion shown beside the current text; a translation is marked machine-translated until a
person confirms they reviewed it, and a statement with an unreviewed translation cannot be submitted for approval.
"""
import re, json
import model as M, ai

TERMS = [  # house terms taken from the published statements; the model keeps them
    ('صافي قيمة الأصول', 'net asset value (NAV)'), ('صافي قيمة الوحدة', 'NAV per unit'), ('المؤشر الاسترشادي', 'benchmark'),
    ('هيئة السوق المالية', 'Capital Market Authority (CMA)'), ('صكوك', 'sukuk'), ('صفقات الإجارة', 'Ijara transactions'),
    ('صفقات التمويل التجاري', 'trade finance transactions'), ('صناديق الدخل', 'income funds'), ('عوائد موزعة', 'distributions'),
    ('الربع المعني', 'the reporting quarter'), ('مدير الصندوق', 'the Fund Manager'), ('الخبير المالية', 'Alkhabeer Capital'),
    ('توزيعات نقدية', 'cash distributions'), ('معدل فائدة التمويل المضمون لليلة واحدة', 'SOFR'), ('نقطة أساس', 'basis points'),
]

TOOL = {'name': 'commentary_result', 'description': 'Return the revised or translated commentary.',
        'input_schema': {'type': 'object', 'properties': {
            'text': {'type': 'string', 'description': 'the full commentary, keeping the line conventions: # heading, - list item, blank line between paragraphs'},
            'changes': {'type': 'array', 'items': {'type': 'string'}, 'description': 'short notes on what was changed and why, in the language named in the task'},
            'doubts': {'type': 'array', 'items': {'type': 'string'}, 'description': 'anything unclear in the source that a person should check, in the language named in the task'}},
            'required': ['text']}}

BASE = """You edit the fund manager commentary of a quarterly statement issued by Alkhabeer Capital, a CMA-licensed fund manager in Saudi Arabia.
Keep every fact and every figure exactly as given. Add nothing that is not in the source. Keep the line conventions: a line starting with "# " is a heading, a line starting with "- " is a list item, and paragraphs are separated by a blank line.
Arabic is formal Modern Standard Arabic (فصحى) in the register of Saudi capital-market documents, with Western digits as in the published statements; English is formal, plain and precise, in the register of the fund's published English statements.
Use these house terms consistently: """ + '; '.join(f'{a} = {b}' for a, b in TERMS) + '.\nReport through the commentary_result tool only.'


def _ref(prev):
    c = prev.get('commentary') or {}
    if c.get('ar') and c.get('en'):
        return f"\n\nLast quarter's published commentary, for terminology and tone only (do not copy its facts):\n[Arabic]\n{c['ar'][:6000]}\n[English]\n{c['en'][:6000]}"
    return ''


def _notes(ui):
    return '\nWrite the changes and doubts notes in ' + ('Arabic.' if ui == 'ar' else 'English.')


def improve(lang, text, prev, actor='', obj='', ui='ar'):
    sys_ = BASE + ('\nTask: improve the Arabic commentary: correct grammar and spelling, shorten long sentences, keep the meaning.' if lang == 'ar'
                   else '\nTask: improve the English commentary: correct grammar and spelling, shorten long sentences, keep the meaning.') + _notes(ui)
    r = ai.call([{'role': 'user', 'content': f'Commentary ({"Arabic" if lang == "ar" else "English"}):\n{text}{_ref(prev)}'}], system=sys_,
                tools=[TOOL], tool_choice={'type': 'tool', 'name': 'commentary_result'}, max_tokens=6000, actor=actor, feature='commentary.improve', obj=obj)
    return ai.tool_input(r, 'commentary_result') or {'text': ''}


def translate(src, text, prev, actor='', obj='', ui='ar'):
    dst = 'en' if src == 'ar' else 'ar'
    sys_ = BASE + (f'\nTask: translate the {"Arabic" if src == "ar" else "English"} commentary into {"English" if dst == "en" else "Arabic"}, '
                   'faithfully and completely, sentence by sentence, as the official version in that language would read. Keep figures, dates and names exactly.') + _notes(ui)
    r = ai.call([{'role': 'user', 'content': f'Source commentary:\n{text}{_ref(prev)}'}], system=sys_,
                tools=[TOOL], tool_choice={'type': 'tool', 'name': 'commentary_result'}, max_tokens=6000, actor=actor, feature='commentary.translate', obj=obj)
    return ai.tool_input(r, 'commentary_result') or {'text': ''}


_NUM = re.compile(r'(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?')
_DIG = str.maketrans('٠١٢٣٤٥٦٧٨٩٫٬', '0123456789.,')


def figures(text):
    out = []
    for m in _NUM.finditer((text or '').translate(_DIG)):
        s = m.group(0); n = M.to_float(s.rstrip('%'))
        if n is None or (1990 <= n <= 2100 and '%' not in s and ',' not in s): continue   # years
        out.append((s, n))
    return out


def check(text, other, data):
    """Figures in one language's commentary that the other language or the form does not carry."""
    vals = set()
    def add(v):
        if isinstance(v, (int, float)): vals.update({round(v, 2), round(v, 1), round(v), round(v * 100, 2), round(v / 1e6, 1), round(v / 1e6, 2)})
    for k, v in (data or {}).items():
        if isinstance(v, (int, float)): add(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, (int, float)): add(x)
                elif isinstance(x, dict): [add(y) for y in x.values()]
        elif isinstance(v, dict):
            for x in v.values():
                if isinstance(x, list): [add(y) for y in x if isinstance(y, (int, float))]
    oth = {round(n, 2) for _, n in figures(other)}
    res = []
    for s, n in figures(text):
        if round(n, 2) in oth: continue
        res.append({'figure': s, 'in_form': any(abs(n - v) < 0.006 for v in vals)})
    return res
