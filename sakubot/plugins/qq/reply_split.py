"""Turn a QQ message into ordered batches; non-text segments keep their position."""
import re


def batches(content, segments, settings):
    message = segments or [{'type': 'text', 'data': {'text': content}}]
    if not settings.reply_split_enabled:
        return [message]
    delimiter = re.compile(settings.reply_split_regex)
    remove = re.compile(settings.reply_remove_regex) if settings.reply_remove_regex else None
    ignore_empty = delimiter.match('') is not None
    result, current = [], []

    def add(text):
        cleaned = remove.sub('', text) if remove else text
        if cleaned:
            current.append({'type': 'text', 'data': {'text': cleaned}})

    def flush():
        nonlocal current
        combined = []
        for segment in current:
            if segment.get('type') == 'text' and combined and combined[-1].get('type') == 'text':
                combined[-1]['data']['text'] += segment['data']['text']
            else:
                combined.append(segment)
        for index, segment in enumerate(combined):
            if segment.get('type') != 'text':
                continue
            value = segment['data']['text']
            if settings.reply_merge_newlines:
                value = value.replace('\r\n', '\n').replace('\r', '\n')
                value = re.sub(r'\n(?:[^\S\n]*\n)+', '\n', value)
            if settings.reply_trim:
                if index == 0:
                    value = value.lstrip()
                if index == len(combined) - 1:
                    value = value.rstrip()
            segment['data']['text'] = value
        combined = [segment for segment in combined if segment.get('type') != 'text' or segment['data']['text']]
        if any(segment.get('type') != 'text' or segment['data']['text'].strip() for segment in combined):
            result.append(combined)
        current = []

    for segment in message:
        if segment.get('type') != 'text':
            current.append(segment)
            continue
        value = str(segment.get('data', {}).get('text', ''))
        offset = 0
        for match in delimiter.finditer(value):
            if match.end() <= offset or (ignore_empty and match.start() == match.end()):
                continue
            add(value[offset:match.end()])
            flush()
            offset = match.end()
        add(value[offset:])
    flush()
    return result
