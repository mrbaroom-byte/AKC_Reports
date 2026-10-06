# Alkhabeer icon bank (template library, slide 9): one thin navy line, the fund-class colour is the only accent.
# Redrawn as SVG on a 24 grid, stroke 1.4 at 64px-equivalent.
INK = '#12284B'

def _svg(body, acc, ink=INK, size='6mm'):
    return ('<svg class="ico" viewBox="0 0 24 24" width="%s" height="%s" fill="none" stroke="%s" stroke-width="1.5" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>') % (size, size, ink, body.replace('ACC', acc))

ICONS = {
    # fund classes
    'cm':       '<rect x="4" y="3.5" width="6" height="17" rx=".6"/><path d="M4 7h6M4 17h6"/><rect x="13" y="3.5" width="6" height="17" rx=".6"/><path d="M13 7h6"/><rect x="14.6" y="12" width="2.8" height="6" fill="ACC" stroke="none"/>',
    're':       '<path d="M5 20V7l2-2.5L9 7l3-3 3 3 2-2.5L19 7v13"/><path d="M3.5 20h17"/><path d="M9.5 20v-6a2.5 2.5 0 0 1 5 0v6" fill="ACC" stroke="ACC"/>',
    'pe':       '<rect x="3.5" y="3.5" width="17" height="17" rx=".6"/><path d="M3.5 12h17M12 3.5v17"/><rect x="12.6" y="4.1" width="7.3" height="7.3" fill="ACC" stroke="none"/><path d="M5.5 5.5l3 3M8.5 5.5l-3 3"/>',
    # documents
    'factsheet':'<path d="M6 3h8.5L19 7.5V21H6z"/><path d="M14.5 3v4.5H19"/><path d="M9 11h7M9 14h7M9 17h5"/>',
    'tc':       '<rect x="5.5" y="3" width="13" height="18" rx=".6"/><path d="M8.5 7h7M8.5 10h7"/><circle cx="12" cy="15.5" r="2.6" fill="ACC" stroke="none"/>',
    'annual':   '<rect x="4" y="4" width="16" height="16" rx=".6"/><path d="M8 16v-3M11 16v-5M14 16v-7M17 16V8"/>',
    'quarterly':'<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 8 8h-8z" fill="ACC" stroke="ACC"/>',
    'notice':   '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    # topics
    'dist':     '<path d="M3.5 20h17"/><rect x="5" y="14" width="3" height="6" rx=".3"/><rect x="10.5" y="10" width="3" height="10" rx=".3" fill="ACC" stroke="ACC"/><rect x="16" y="6" width="3" height="14" rx=".3"/>',
    'perf':     '<path d="M3.5 17l5.5-5.5 4 4L20 8.5"/><path d="M15 8.5h5v5"/>',
    'dates':    '<rect x="4" y="5" width="16" height="15" rx=".8"/><path d="M4 9.5h16M8 3v4M16 3v4"/><rect x="13.2" y="13" width="4" height="4" fill="ACC" stroke="none"/>',
    'risk':     '<path d="M4 16a8 8 0 0 1 16 0"/><path d="M12 16l4-5"/><circle cx="12" cy="16" r="1.6" fill="ACC" stroke="ACC"/>',
    'sharia':   '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M8.8 12.2l2.2 2.2 4.4-4.6" stroke="ACC" stroke-width="2"/>',
    'contact':  '<path d="M6.5 3.5l3 3-1.6 2.6a11 11 0 0 0 7 7l2.6-1.6 3 3-1.8 2.6c-7.4-.6-14.3-7.5-14.9-14.9z"/>',
    'download': '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5"/><path d="M5 19.5h14"/>',
    'chat':     '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12.5h5"/>',
}

def icon(name, acc, ink=INK, size='6mm'):
    return _svg(ICONS[name], acc, ink, size)

# heading text -> icon (Arabic and English quarterly statements)
import re
RULES = [
    (r'توزيع(?!\s*الاستثمارات)|التوزيعات|الأرباح الموزعة|Dividend|Distribution(?!\s+of\s+Invest)', 'dist'),
    (r'المخاطر|Risk', 'risk'),
    (r'الأداء|العوائد|العائد|Performance|Return', 'perf'),
    (r'مستجدات|التغيرات|تغيرات|Updates|Changes', 'dates'),
    (r'شرعي|الشريعة|Shari', 'sharia'),
    (r'للحصول على المزيد|المزيد من المعلومات|Further Information|Contact', 'contact'),
    (r'إشعار مهم|Disclaimer|Important Notice', 'notice'),
    (r'نبذة|هدف الصندوق|Overview|Objective', 'CLASS'),
    (r'البيانات الأساسية|بيانات الصندوق|Key Fund|Fund Facts|Fund Data|Fund Information', 'factsheet'),
    (r'المعادلات|Equation', 'annual'),
]

def pick(text):
    for pat, name in RULES:
        if re.search(pat, text, re.I): return name
    return None
