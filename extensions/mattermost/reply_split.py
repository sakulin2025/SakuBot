import re


def split_reply(content, settings):
    if not settings.reply_split_enabled:
        return [content] if content.strip() else []
    delimiter = re.compile(settings.reply_split_regex)
    remove = re.compile(settings.reply_remove_regex) if settings.reply_remove_regex else None
    result, offset = [], 0

    def add(value):
        if remove:
            value = remove.sub('', value)
        if settings.reply_merge_newlines:
            value = re.sub(r'\n(?:[^\S\n]*\n)+', '\n', value.replace('\r\n', '\n').replace('\r', '\n'))
        if settings.reply_trim:
            value = value.strip()
        if value.strip():
            result.append(value)

    for match in delimiter.finditer(content):
        if match.start() == match.end() or match.end() <= offset:
            continue
        add(content[offset:match.end()])
        offset = match.end()
    add(content[offset:])
    return result
