"""Minimal JSON event envelope shared by trigger and manual runs."""
def validate_event(event):
    if not isinstance(event, dict) or not isinstance(event.get('source'), str) or not isinstance(event.get('id'), str) or type(event.get('at')) not in (int, float) or not isinstance(event.get('data'), dict):
        raise ValueError('事件须为含 id、source、at、data 的字典；data 为字典')
