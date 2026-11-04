"""Read back authoritative command configuration before publishing ready state."""
import time


async def readback(commands, row):
    remote = await commands.api('GET', '/' + row['command_id'])
    if (remote.get('id') != row['command_id'] or
            remote.get('creator_id') != commands.plugin.bot_id or
            remote.get('team_id') != row['team_id']):
        raise ValueError('命令同步失败：远端 ID、账号或团队不匹配')
    differences = [key for key, value in commands.remote_body(row).items() if remote.get(key) != value]
    if differences:
        raise ValueError('命令同步失败：远端配置不一致（' + '、'.join(differences) + '）')
    token = remote.get('token')
    if not isinstance(token, str) or not token:
        raise ValueError('命令同步失败：远端未返回有效令牌')
    row['token'] = token
    row['synced_at'] = time.time()
