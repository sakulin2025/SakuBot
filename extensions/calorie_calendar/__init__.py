import calendar
import math
import re
import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sakubot.plugin import Plugin, object_schema, text

SPECIAL = {'intake': ('早餐', '午餐', '晚餐'), 'expenditure': ('基础代谢', '活动消耗')}


def day_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期格式应为 YYYY-MM-DD')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('日期无效') from None


def today():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()


class Extension(Plugin):
    name = 'calorie_calendar'

    def setup(self):
        self.db = sqlite3.connect(self.data_dir / 'calories.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS entries (
              id TEXT PRIMARY KEY, day TEXT NOT NULL, kind TEXT NOT NULL,
              label TEXT NOT NULL, kcal REAL NOT NULL, estimated INTEGER NOT NULL,
              note TEXT NOT NULL, source TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS entries_day ON entries(day, kind, created);
            CREATE UNIQUE INDEX IF NOT EXISTS unique_special ON entries(day, kind, label)
              WHERE label IN ('早餐','午餐','晚餐','基础代谢','活动消耗');
            CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, confirmed INTEGER NOT NULL, updated REAL NOT NULL);
        ''')
        for source, title in [('record_changed','热量记录变化'),('confirmation_changed','热量日期确认变化')]:
            self.trigger_source(source + '.*',title,object_schema({'day':{'type':'string','title':'日期 · 留空不限','pattern':r'^$|^\d{4}-\d{2}-\d{2}$'}}),
                object_schema({'day':{'type':'string'},'action':{'type':'string'},'record_id':{'type':'string'},'summary':{'type':'object'}},('day','action','summary')),
                match=lambda event,params:not params.get('day') or params['day']==event['day'],legacy_ids=(source,))
        self.page('manage', '热量日历' , Path(__file__).parent / 'web' / 'dist', icon='activity', group_id='productivity', order=30)
        self.api('calendar', self.calendar_api)
        self.api('day', self.day_api)
        self.api('entry', self.entry_api, methods=('POST',))
        self.api('entry/{identifier}', self.delete_api, methods=('DELETE',))
        self.api('confirm', self.confirm_api, methods=('POST',))
        self.tool('calorie_record', '按日期添加、修改或删除热量摄入/消耗记录。早餐、午餐、晚餐、基础代谢、活动消耗是每天各一条的特殊标签；其他标签可重复。增删改记录不会改变日期确认状态。',
            object_schema({'action': {'type': 'string', 'enum': ['add', 'update', 'delete']}, 'id': text('修改或删除时提供记录 ID'),
                'date': text('日期 YYYY-MM-DD，新增时可留空表示今天'), 'kind': {'type': 'string', 'enum': ['intake', 'expenditure']},
                'label': text('餐次、消耗类型或自定义标签'), 'kcal': {'type': 'number', 'minimum': 0, 'maximum': 100000},
                'estimated': {'type': 'boolean'}, 'note': text('详情描述：具体食物、份量、估算依据或修正说明；追加食物时保留并更新已有详情'), 'source': text('数据来源，例如用户、设备、品牌营养表或估算')}, ('action',)), self.record_tool)
        self.tool('calorie_report', '查询日期区间的热量记录及统计；汇总仅包括已确认日期。可只传 date 查询某日，也可传 start、end 查询最长 366 天。',
            object_schema({'date': text('单日 YYYY-MM-DD'), 'start': text('开始日期 YYYY-MM-DD'), 'end': text('结束日期 YYYY-MM-DD')}, ()), self.report_tool)
        self.tool('calorie_confirm', '确认或取消确认某天热量记录。只有已确认的日期计入累计统计；增删改记录不会改变确认状态。',
            object_schema({'date': text('日期 YYYY-MM-DD，留空表示今天'), 'confirmed': {'type': 'boolean'}}, ('confirmed',)), self.confirm_tool)

    async def stop(self):
        await super().stop()
        self.db.close()

    def totals(self, start=None, end=None, confirmed_only=False):
        sql = '''SELECT b.day, sum(CASE WHEN e.kind='intake' THEN e.kcal ELSE 0 END) intake,
                 sum(CASE WHEN e.kind='expenditure' THEN e.kcal ELSE 0 END) expenditure,
                 count(e.id) count, coalesce(d.confirmed,0) confirmed
                 FROM (SELECT day FROM entries UNION SELECT day FROM days WHERE confirmed=1) b
                 LEFT JOIN entries e ON e.day=b.day LEFT JOIN days d ON d.day=b.day WHERE 1=1'''
        params = []
        if start:
            sql += ' AND b.day>=?'; params.append(start)
        if end:
            sql += ' AND b.day<=?'; params.append(end)
        if confirmed_only:
            sql += ' AND d.confirmed=1'
        sql += ' GROUP BY b.day ORDER BY b.day'
        return [self.format_day(dict(row)) for row in self.db.execute(sql, params)]

    @staticmethod
    def format_day(row):
        row['intake'] = round(row['intake'] or 0, 2)
        row['expenditure'] = round(row['expenditure'] or 0, 2)
        row['balance'] = round(row['intake'] - row['expenditure'], 2)
        row['confirmed'] = bool(row['confirmed'])
        return row

    @staticmethod
    def aggregate(rows):
        selected = [row for row in rows if row['confirmed']]
        intake = round(sum(row['intake'] for row in selected), 2)
        expenditure = round(sum(row['expenditure'] for row in selected), 2)
        return {'days': len(selected), 'intake': intake, 'expenditure': expenditure, 'balance': round(intake - expenditure, 2)}

    def day(self, day):
        day = day_value(day)
        rows = [dict(row) for row in self.db.execute('SELECT * FROM entries WHERE day=? ORDER BY created,id', (day,))]
        for row in rows:
            row['estimated'] = bool(row['estimated'])
        summary = next(iter(self.totals(day, day)), {'day': day, 'intake': 0, 'expenditure': 0, 'balance': 0, 'count': 0, 'confirmed': False})
        return {**summary, 'entries': rows}

    def calendar(self, month):
        if not isinstance(month, str) or not re.fullmatch(r'\d{4}-\d{2}', month):
            raise ValueError('月份格式应为 YYYY-MM')
        try:
            year, number = map(int, month.split('-'))
            date(year, number, 1)
            last = calendar.monthrange(year, number)[1]
        except (ValueError, OverflowError):
            raise ValueError('月份无效') from None
        start, end = month + '-01', month + '-' + str(last).zfill(2)
        rows = self.totals(start, end)
        return {'month': month, 'today': today(), 'days': rows, 'month_total': self.aggregate(rows),
                'all_total': self.aggregate(self.totals(confirmed_only=True))}

    def save_entry(self, payload):
        if not isinstance(payload, dict) or set(payload) - {'id', 'date', 'kind', 'label', 'kcal', 'estimated', 'note', 'source'}:
            raise ValueError('记录格式无效')
        record_id = payload.get('id') or ''
        old = self.db.execute('SELECT * FROM entries WHERE id=?', (record_id,)).fetchone() if record_id else None
        if record_id and not old:
            raise ValueError('记录不存在')
        previous = dict(old) if old else {}
        day = day_value(payload.get('date') or previous.get('day') or today())
        kind = payload.get('kind', previous.get('kind', ''))
        label = payload.get('label', previous.get('label', ''))
        kcal = payload.get('kcal', previous.get('kcal'))
        estimated = payload.get('estimated', bool(previous.get('estimated', False)))
        note = payload.get('note', previous.get('note', ''))
        source = payload.get('source', previous.get('source', ''))
        if kind not in SPECIAL or not isinstance(label, str) or not label.strip() or len(label.strip()) > 60:
            raise ValueError('记录类型或标签无效')
        label = label.strip()
        if any(label in labels for other, labels in SPECIAL.items() if other != kind):
            raise ValueError('该特殊标签不属于此记录类型')
        if isinstance(kcal, bool) or not isinstance(kcal, (int, float)) or not math.isfinite(kcal) or not 0 <= kcal <= 100000:
            raise ValueError('热量应为 0 至 100000 大卡')
        if type(estimated) is not bool or not isinstance(note, str) or len(note) > 4000 or not isinstance(source, str) or len(source) > 500:
            raise ValueError('记录详情无效')
        now = time.time()
        saved_id = record_id or uuid.uuid4().hex
        try:
            with self.db:
                self.db.execute('''INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET day=excluded.day,kind=excluded.kind,label=excluded.label,kcal=excluded.kcal,
                    estimated=excluded.estimated,note=excluded.note,source=excluded.source,updated=excluded.updated''',
                    (saved_id, day, kind, label, round(kcal, 2), int(estimated), note.strip(), source.strip(), previous.get('created', now), now))
        except sqlite3.IntegrityError:
            raise ValueError('该日期已有此特殊标签，请修改已有记录') from None
        result = self.day(day)
        self.publish_trigger('record_changed.' + day, {'day':day,'action':'update' if old else 'add','record_id':saved_id,'summary':result})
        if previous.get('day') and previous['day'] != day:
            self.publish_trigger('record_changed.' + previous['day'], {'day':previous['day'],'action':'move','record_id':saved_id,'summary':self.day(previous['day'])})
        return result

    def delete_entry(self, identifier):
        row = self.db.execute('SELECT day FROM entries WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise ValueError('记录不存在')
        day = row['day']
        with self.db:
            self.db.execute('DELETE FROM entries WHERE id=?', (identifier,))
        result=self.day(day)
        self.publish_trigger('record_changed.' + day, {'day':day,'action':'delete','record_id':identifier,'summary':result})
        return result

    def confirm(self, day, confirmed):
        day = day_value(day or today())
        if type(confirmed) is not bool:
            raise ValueError('确认状态必须为布尔值')
        if confirmed and not self.db.execute('SELECT 1 FROM entries WHERE day=? LIMIT 1', (day,)).fetchone():
            raise ValueError('当天没有记录')
        previous=self.day(day)['confirmed']
        with self.db:
            self.db.execute('INSERT INTO days VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET confirmed=excluded.confirmed,updated=excluded.updated', (day, int(confirmed), time.time()))
        result=self.day(day)
        if previous != confirmed:
            self.publish_trigger('confirmation_changed.' + day, {'day':day,'action':'confirm' if confirmed else 'unconfirm','summary':result})
        return result

    async def calendar_api(self, request):
        return self.calendar(request.query_params.get('month') or today()[:7])

    async def day_api(self, request):
        return self.day(request.query_params.get('date') or today())

    async def entry_api(self, request):
        return self.save_entry(await request.json())

    async def delete_api(self, request):
        return self.delete_entry(request.path_params['identifier'])

    async def confirm_api(self, request):
        data = await request.json()
        return self.confirm(data.get('date'), data.get('confirmed'))

    async def record_tool(self, inv, args):
        action = args['action']
        payload = {k: v for k, v in args.items() if k != 'action'}
        if action in ('update', 'delete') and not payload.get('id'):
            raise ValueError('请提供记录 ID')
        if action == 'add' and payload.get('id'):
            raise ValueError('新增记录不应指定 ID')
        return self.delete_entry(payload['id']) if action == 'delete' else self.save_entry(payload)

    async def report_tool(self, inv, args):
        if args.get('date'):
            return self.day(args['date'])
        start = day_value(args.get('start') or today())
        end = day_value(args.get('end') or start)
        if not 0 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 365:
            raise ValueError('日期范围不能倒序或超过 366 天')
        rows = self.totals(start, end)
        return {'start': start, 'end': end, 'days': rows, 'total': self.aggregate(rows)}

    async def confirm_tool(self, inv, args):
        return self.confirm(args.get('date'), args['confirmed'])
