"""Shared approximate token accounting; never compare UTF-8 bytes to token limits."""
import json
import math


def estimate(messages, tools=None):
    images = 0
    def clean(value):
        nonlocal images
        if isinstance(value, dict):
            if value.get('type') == 'image_url':
                images += 1
                return {'type':'image_url','image_url':{'url':'<image>'}}
            return {key:clean(item) for key,item in value.items() if not key.startswith('_')}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    text = json.dumps({'messages':clean(messages),'tools':tools or []},ensure_ascii=False)
    ascii_count = sum(ord(char) < 128 for char in text)
    return math.ceil(ascii_count / 3.5 + (len(text)-ascii_count) * 1.2) + images * 16384
