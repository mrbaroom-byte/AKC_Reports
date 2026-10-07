"""Canned Messages API replies for local tests (AI_MOCK=1). Never used in production."""
import json, re, itertools

_ids = itertools.count(1)


def _use(name, inp):
    return {'content': [{'type': 'tool_use', 'id': f'tu_{next(_ids)}', 'name': name, 'input': inp}], 'usage': {'input_tokens': 1200, 'output_tokens': 150}, 'model': 'mock'}


def _text(t):
    return {'content': [{'type': 'text', 'text': t}], 'usage': {'input_tokens': 900, 'output_tokens': 80}, 'model': 'mock'}


def reply(messages, system, tools, tool_choice):
    names = [t['name'] for t in tools or []]
    last = messages[-1]['content']
    if tool_choice and tool_choice.get('name') == 'propose_values':
        txt = json.dumps(last, ensure_ascii=False)
        m = re.search(r'NAV per unit[^0-9]{0,40}([0-9]+\.[0-9]+)', txt)
        props = [{'field': 'nav_unit', 'value': float(m.group(1)) if m else 9.1111, 'file': 'mock', 'location': 'page 1', 'quote': 'NAV per unit', 'confidence': 0.93, 'note': ''},
                 {'field': 'no_such_field', 'value': 1, 'file': 'mock', 'location': '-', 'quote': '-', 'confidence': 0.5}]
        return _use('propose_values', {'proposals': props, 'summary': 'ملف تجريبي يتضمن صافي قيمة الوحدة.', 'not_found': ['units']})
    if tool_choice and tool_choice.get('name') == 'commentary_result':
        src = last if isinstance(last, str) else ''
        body = src.split('\n', 1)[1].split("\n\nLast quarter", 1)[0] if '\n' in src else src
        if 'translate' in system:
            return _use('commentary_result', {'text': '[translation] ' + body.strip(), 'changes': [], 'doubts': ['تجريبي']})
        return _use('commentary_result', {'text': body.strip() + '.', 'changes': ['تصحيح الترقيم'], 'doubts': []})
    if 'update_statement' in names:
        if isinstance(last, list):   # tool results came back
            return _text('تم. عدّلت صافي قيمة الوحدة، ويمكنك التراجع.' if 'saved' in json.dumps(last) else 'الحالة: ' + json.dumps(last, ensure_ascii=False)[:200])
        q = last.lower()
        if 'nav' in q or 'صافي' in q:
            return _use('update_statement', {'fund': 'income', 'quarter': 'q3-2026', 'changes': [{'field': 'nav_unit', 'value': 9.2222}], 'reason': 'طلب المستخدم'})
        return _use('list_statements', {})
    return _text('ok')
