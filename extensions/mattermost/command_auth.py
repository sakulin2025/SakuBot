"""Ingress verification is independent of automation bindings and script lifetimes."""
import hmac


def rejection(commands, token, data):
    command = data.get('command')
    candidates = [row for row in commands.records().values()
                  if row.get('team_id') == data.get('team_id') and '/' + row['trigger'] == command]
    if not candidates:
        return 'command_not_registered'
    for row in candidates:
        secret = row.get('token')
        if not isinstance(secret, str) or not secret or not hmac.compare_digest(token.encode(), secret.encode()):
            continue
        if row.get('account') != commands.account:
            return 'account_changed'
        if row.get('status') != 'ready':
            return 'command_not_ready'
        if not row.get('enabled'):
            return 'command_disabled'
        if not commands.plugin.config.get('slash_enabled'):
            return 'slash_disabled'
        if any(row.get(key) and row[key] != data.get(key) for key in ('user_id', 'channel_id')):
            return 'sender_or_channel_restricted'
        return ''
    return 'token_mismatch'
