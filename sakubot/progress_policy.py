"""Per-wake progress reporting policy; batches remain atomic for insertion."""


class ProgressPolicy:
    def __init__(self, invocation, settings):
        self.invocation = invocation
        self.settings = settings.model_copy(deep=True)
        self.enabled = invocation.agent_id == 'main' and self.settings.enabled
        self.count = 0
        self.seconds = 0.0
        self.publish()

    def publish(self):
        self.invocation.metadata['progress_reporting'] = {
            'enabled': self.enabled, 'mode': self.settings.mode,
            'tool_count': self.count, 'tool_seconds': round(self.seconds, 3),
            'tool_threshold': self.settings.tool_threshold,
            'seconds_threshold': self.settings.seconds_threshold,
        }

    def due(self):
        return self.count >= self.settings.tool_threshold or self.seconds >= self.settings.seconds_threshold

    def rejection(self, calls):
        if not self.enabled or self.settings.mode != 'require' or not self.due():
            return None
        if calls[0]['function']['name'] == 'message_send':
            return None
        return ('本批工具尚未执行：已达到进度汇报阈值。下一批必须将 message_send 放在首位，'
                '成功提交进展消息后才能执行其他工具。' + self.settings.prompt)

    def completed(self, name, elapsed, result):
        if not self.enabled:
            return
        if name == 'message_send' and isinstance(result, dict) and result.get('submitted') is True:
            self.count = 0
            self.seconds = 0.0
        else:
            self.count += 1
            self.seconds += elapsed
        self.publish()

    def reminder(self):
        if not self.enabled or not self.due():
            return None
        return ('框架进度汇报提醒（不是工具原始输出）：' + self.settings.prompt +
                f' 当前累计工具调用 {self.count} 次、工具耗时 {self.seconds:.1f} 秒。' +
                (' 下一批首项必须为 message_send。' if self.settings.mode == 'require' else ''))
