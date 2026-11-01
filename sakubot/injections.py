"""Model-facing transient context: ordering, provenance and lifetime."""

ORDER = {'data': 10, 'environment': 20, 'guidance': 30, 'requirement': 40, 'reminder': 50}


def injection(content, *, source, category='guidance', lifetime='wake', role='system', priority=0):
    if not isinstance(content, str) or len(content) > 200000:
        raise ValueError('注入内容必须为文本，最多200000字符')
    if category not in ORDER or lifetime not in ('wake', 'request') or role not in ('system', 'user', 'assistant'):
        raise ValueError('注入类型、生命周期或角色无效')
    if type(priority) is not int or not -100 <= priority <= 100:
        raise ValueError('注入排序值应为 -100 至 100')
    return {'role': role, 'content': content, '_injection': {
        'source': source, 'category': category, 'lifetime': lifetime, 'priority': priority}}


def ordered(items):
    return sorted(items, key=lambda item: (ORDER.get(item.get('_injection', {}).get('category'), ORDER['guidance']),
                                           item.get('_injection', {}).get('priority', 0)))
