from .event_docs import PARAMETERS, EVENT, ID_DESCRIPTION
import asyncio
import uuid
from datetime import datetime
from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection, settings_section
from .client import Client, date_range, workout_id, validate_url, LOCAL_ZONE
from .polling import Polling
from .report import make_report


class Extension(Polling, Plugin):
    
    
    name = 'freereps_activity'

    def setup(self):
        self.config = self.configure({'base_url': 'http://freereps:8080', 'poll_enabled': False,
            'poll_interval_minutes': 5, 'lookback_days': 7})
        self.client = Client(self.config)
        self.report_workouts = []
        self.setup_polling()
        from sakubot.plugin import object_schema
        self.trigger_source('workout_added.*','新增训练记录',PARAMETERS, EVENT, id_description=ID_DESCRIPTION,
            match=lambda event,params:not params.get('workout_type') or params['workout_type'].casefold() in str(event['workout'].get('name','')).casefold(),legacy_ids=('workout_added',))

        for name, method in [('freereps_workouts', self.workouts), ('freereps_workout_detail', self.detail),
                ('freereps_activity', self.activity), ('freereps_metrics', self.metrics),
                ('freereps_sleep', self.sleep), ('freereps_status', self.status),
                ('freereps_workout_report', self.workout_report)]:
            self.function(method, name=name)
        self.fields = [field('base_url', 'FreeReps 地址', required=True, format='http-url', default='http://freereps:8080'),
            field('poll_enabled', '轮询', 'boolean', default=False),
            field('poll_interval_minutes', '轮询间隔 · 分钟', 'number', min=1, max=1440, required=True, default=5),
            field('lookback_days', '回看范围 · 天', 'number', min=1, max=90, required=True, default=7)]
        self.management('FreeReps 活动数据同步', [
            collection('workouts', '训练报告', [field('name', '训练类型'), field('start_time', '开始时间'),
                field('duration_sec', '时长 · 秒'), field('distance', '距离'), field('distance_units', '距离单位')],
                create=False, edit=False, remove=False, commands=[{'id': 'refresh', 'label': '获取训练'}],
                row_commands=[{'id': 'report', 'label': '生成报告'}]),
            collection('monitor', '轮询状态', [field('enabled', '轮询', 'boolean'), field('baseline', '基线', 'boolean'),
                field('last_poll', '最近轮询'), field('pending', '待发布事件'), field('error', '错误')], create=False, edit=False, remove=False),
            settings_section(self.fields)], self.view, self.manage, group_id='productivity')

    def availability(self):
        try:
            validate_url(self.config.get('base_url', ''))
            return {'available': True, 'reason': ''}
        except ValueError:
            return {'available': False, 'reason': '待配置 FreeReps 地址'}

    async def start(self):
        from .migration import migrate_events
        migrate_events(self)
        self.background(self.poll_loop())

    async def stop(self):
        await super().stop()
        await self.client.close()

    def view(self):
        data = self.state.get('monitor', {})
        last = data.get('last_poll_at')
        status = {'id': 'monitor', 'enabled': self.config.get('poll_enabled', False), 'baseline': data.get('baseline', False),
            'last_poll': datetime.fromtimestamp(last, LOCAL_ZONE).isoformat() if last else '',
            'pending': len(data.get('trigger_pending', {})), 'error': self.poll_error}
        return {'data': {'workouts': self.report_workouts, 'monitor': [status],
            'config': self.config.public([f['key'] for f in self.fields])}}

    async def manage(self, data):
        if data['section'] == 'workouts' and data['action'] == 'command':
            if data.get('command') == 'refresh':
                self.report_workouts = await self.client.workouts(days=90)
                return None
            if data.get('command') == 'report':
                result = await self.workout_report(data.get('key', ''))
                return {'image': self.artifact(self.workspace.path(result['path'], allow_root=False)),
                    'path': result['path']}
            raise ValueError('操作无效')
        raise ValueError('操作无效')

    async def workouts(self, start: str='', end: str='', workout_type: str='', limit: int=30, offset: int=0) :
        """按时间和训练类型查询 FreeReps 训练记录。新记录的到达时间不等于训练结束时间。返回分页与训练 ID；类型筛选需使用 FreeReps 实际类型名称。

        Args:
            start(string): 开始日期或带时区的 ISO 时间；日期按 Asia/Shanghai 理解，默认最近七天。
            end(string): 结束日期或带时区的 ISO 时间；日期按 Asia/Shanghai 理解，默认当前时间。
            workout_type(string): FreeReps 训练类型，留空全部。
            limit(int): 每页条数，1 至 100。
            offset(int): 分页偏移，从 0 开始。
        """
        if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 100 or offset < 0:
            raise ValueError('分页参数无效')
        rows = await self.client.workouts(start, end, workout_type)
        return {'items': rows[offset:offset + limit], 'total': len(rows), 'offset': offset, 'has_more': offset + limit < len(rows)}

    async def detail(self, id: str, include_sets: bool=True, start: str='', end: str='') :
        """查询训练详情和力量训练组。部分由力量训练合成的列表条目没有常规训练详情，返回 unavailable，不代表训练不存在。详情可能包含敏感路线，按需提供。

        Args:
            id(string): FreeReps 训练 UUID。
            include_sets(bool): 是否同时查询训练动作与组数。
            start(string): 合成训练的开始时间，使用列表提供的 ISO 时间。
            end(string): 合成训练的结束时间，使用列表提供的 ISO 时间。
        """
        identifier = workout_id(id)
        result = {}
        for label, path in [('detail', 'workouts/' + identifier), ('sets', 'workouts/' + identifier + '/sets')]:
            if label == 'sets' and not include_sets:
                continue
            try:
                result[label] = await self.client.get(path, date_range(start, end) if label == 'sets' and start and end else None)
            except ValueError as exc:
                if 'HTTP 404' not in str(exc):
                    raise
                result[label] = None
                result[label + '_unavailable'] = True
        return result

    async def activity(self, start: str='', end: str='') :
        """查询指定时间的每日活动汇总；未同步不代表没有活动。日期格式 YYYY-MM-DD。"""
        return await self.client.get('activity-summaries', date_range(start, end))

    async def workout_report(self, id: str) :
        """为一条训练生成 PNG 长图，保存到共享工作空间。按需显示概览、GPS 轨迹背景、心率和速度或配速；不含地图底图。结果包含工作空间相对路径，可用 workspace_publish 发送。

        Args:
            id(string): FreeReps 训练 UUID；先通过 freereps_workouts 查询。
        """
        identifier = workout_id(id)
        detail = await self.client.get('workouts/' + identifier)
        content, sections = await asyncio.to_thread(make_report, detail)
        path = 'artifacts/freereps/workout-' + identifier + '-' + uuid.uuid4().hex[:8] + '.png'
        self.workspace.write_bytes(path, content)
        return {'path': path, 'format': 'png', 'timezone': 'Asia/Shanghai', **sections,
            'delivery': '使用 workspace_publish 发布或发送图片。GPS 轨迹不含地图底图。'}

    async def metrics(self, metric: str='', start: str='', end: str='', mode: str='latest') :
        """查询最新健康指标、指定指标的记录或统计。mode 为 latest、available、history、stats；单位和缺失值须按返回结果解释。"""
        if mode in ('latest', 'available'):
            return await self.client.get('metrics/' + mode)
        if mode not in ('history', 'stats') or not metric.strip():
            raise ValueError('请选择 latest/available/history/stats，history 和 stats 需要指标名')
        params = date_range(start, end)
        params['name' if mode == 'history' else 'metric'] = metric.strip()
        return await self.client.get('metrics' if mode == 'history' else 'metrics/stats', params)

    async def sleep(self, start: str='', end: str='') :
        """查询指定时间内睡眠记录和阶段；结果缺失不等于未睡眠。日期格式 YYYY-MM-DD。"""
        return await self.client.get('sleep', date_range(start, end))

    async def status(self, include_sources: bool=False) :
        """查询 FreeReps 版本、轮询与基线状态，不主动注入健康数据。"""
        version = await self.client.get('version')
        state = self.state.get('monitor', {})
        result = {'version': version, 'poll_enabled': self.config.get('poll_enabled', False),
            'baseline_ready': state.get('baseline', False), 'last_poll_at': datetime.fromtimestamp(state['last_poll_at'], LOCAL_ZONE).isoformat() if state.get('last_poll_at') else None,
            'next_poll_at': datetime.fromtimestamp(self.next_poll, LOCAL_ZONE).isoformat() if self.next_poll else None, 'timezone': 'Asia/Shanghai', 'pending_events': len(state.get('trigger_pending', {})), 'poll_error': self.poll_error}
        if include_sources:
            sources = {}
            for name in ('oura', 'withings', 'hevy'):
                try:
                    data = await self.client.get(name + '/status')
                    sources[name] = {key: data[key] for key in ('configured', 'connected', 'last_sync', 'sync_states') if key in data}
                except ValueError as exc:
                    sources[name] = {'error': str(exc)}
            result['sources'] = sources
        return result
