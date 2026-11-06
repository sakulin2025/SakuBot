import ast
import math
import operator
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    name = 'utilities'

    def setup(self):
        self.tool('image_describe', '使用支持图片的模型解读图片，可自定义 prompt 进行文字提取、食物辨识、界面分析等。image 接受 HTTP/HTTPS 图片 URL、工作空间相对路径、/api/artifacts/附件标识或 base64 图片 data URL。需要登录的图片先下载到工作空间。可用 model_id 指定框架模型条目的 ID；未指定时优先当前智能体的图片模型，否则选择首个已启用图片模型。返回描述、原始图片地址、模型和用量。会产生额外模型请求；不保证推断准确。', {'type': 'object', 'properties': {'image': {'type': 'string', 'description': '图片 HTTP/HTTPS URL、工作空间相对路径、框架附件 URL 或图片 data URL'}, 'prompt': {'type': 'string', 'description': '自定义图片分析要求；不传时准确描述主体、文字和重要细节'}, 'model_id': {'type': 'string', 'description': '可选框架模型条目 ID；不是供应商模型名称'}, 'max_tokens': {'type': 'integer', 'description': '最大输出 Token，默认2048', 'minimum': 128, 'maximum': 16000}}, 'required': ['image'], 'additionalProperties': False}, self.describe_image)
        self.tool('time_info', '获取指定时区的当前准确日期、时间、星期和 Unix 时间戳，也可转换已有时间。timezone 使用 IANA 名称如 Asia/Shanghai、UTC、America/New_York；value 留空表示现在，支持 ISO8601 或 Unix 秒。未带时区的输入按所选 timezone 理解。不是定时提醒，提醒使用定时任务插件。', {'type': 'object', 'properties': {'timezone': {'type': 'string', 'description': '目标 IANA 时区，默认 Asia/Shanghai'}, 'value': {'type': 'string', 'description': '可选 ISO8601 或 Unix 秒；留空表示当前时间'}}, 'required': [], 'additionalProperties': False}, self.time_info)
        self.tool('time_difference', '计算两个时间点相差多少秒、小时和天，结果为 end 减 start；一天按24小时。接受 ISO8601 或 Unix 秒，无时区的输入按 timezone（默认 Asia/Shanghai）解释。夏令时跨越按实际经过时间计算。', {'type': 'object', 'properties': {'start': {'type': 'string', 'description': '开始时间，ISO8601 或 Unix 秒'}, 'end': {'type': 'string', 'description': '结束时间，ISO8601 或 Unix 秒'}, 'timezone': {'type': 'string', 'description': '无时区输入使用的 IANA 时区，默认 Asia/Shanghai'}}, 'required': ['start', 'end'], 'additionalProperties': False}, self.time_difference)
        self.tool('calculate', '计算数值表达式，支持 + - * / // % **、括号、pi/e、abs/round/min/max/sqrt/sin/cos/tan/log/log10/exp/floor/ceil。乘方用 **，不支持变量赋值或代码执行。结果是数值计算，浮点数可能有舍入误差；不能充当货币账本。', {'type': 'object', 'properties': {'expression': {'type': 'string', 'description': '数值表达式，例如 (120+35)*0.85；不接受赋值或代码执行'}}, 'required': ['expression'], 'additionalProperties': False}, self.calculate)

    async def describe_image(self, invocation, args) :
        from sakubot.image_description import describe
        return await describe(self, invocation, args)

    def prompt_context(self, invocation):
        return '其他时区和日期计算可用 time_info、time_difference；数值计算使用 calculate。'

    def wake_context(self, invocation):
        if invocation.agent_id == 'main':
            return ''  # Main environment is rendered centrally.
        return '本轮唤醒时间（Asia/Shanghai）：' + datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds') + '。需要当前精确时间时使用 time_info。'

    @staticmethod
    def zone(name):
        try:
            return ZoneInfo(name or 'Asia/Shanghai')
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('时区无效，请使用 Asia/Shanghai、UTC 等 IANA 名称') from None

    @staticmethod
    def parse(value, zone):
        try:
            if value.strip() == '':
                return datetime.now(zone)
            try:
                seconds = float(value)
            except ValueError:
                result = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if result.tzinfo is None:
                    if result.replace(tzinfo=zone, fold=0).utcoffset() != result.replace(tzinfo=zone, fold=1).utcoffset():
                        raise ValueError()
                    result = result.replace(tzinfo=zone)
            else:
                result = datetime.fromtimestamp(seconds, timezone.utc)
            local = result.astimezone(zone)
            # Reject nonexistent wall times instead of silently shifting through DST.
            if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                raise ValueError()
            return local
        except (ValueError, OverflowError, OSError):
            raise ValueError('时间无效，请提供 ISO8601 或 Unix 秒；夏令时歧义请显式提供 UTC 偏移') from None

    async def time_info(self, invocation, args):
        name = args.get('timezone') or 'Asia/Shanghai'
        value = self.parse(args.get('value', ''), self.zone(name))
        return {'timezone': name, 'iso': value.isoformat(timespec='seconds'), 'date': value.date().isoformat(),
            'weekday': ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'][value.weekday()],
            'unix_seconds': value.timestamp(), 'utc': value.astimezone(timezone.utc).isoformat(timespec='seconds')}

    async def time_difference(self, invocation, args):
        zone = self.zone(args.get('timezone', ''))
        start, end = (self.parse(args[key], zone).astimezone(timezone.utc) for key in ('start', 'end'))
        seconds = (end - start).total_seconds()
        return {'seconds': seconds, 'hours': seconds / 3600, 'days': seconds / 86400}

    async def calculate(self, invocation, args) :
        expression = args['expression'].strip()
        if not expression or len(expression) > 1000:
            raise ValueError('表达式需为1到1000字符')
        functions = {name: getattr(math, name) for name in ('sqrt', 'sin', 'cos', 'tan', 'log', 'log10', 'exp', 'floor', 'ceil')}
        functions.update(abs=abs, round=round, min=min, max=max)
        binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}

        def visit(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = node.value
            elif isinstance(node, ast.Name) and node.id in ('pi', 'e'):
                value = getattr(math, node.id)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            elif isinstance(node, ast.BinOp) and type(node.op) in binary:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                    raise ValueError('指数绝对值不能超过1000')
                value = binary[type(node.op)](left, right)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and not node.keywords and len(node.args) <= 10:
                value = functions[node.func.id](*(visit(arg) for arg in node.args))
            else:
                raise ValueError('表达式含不支持的运算或函数')
            if type(value) not in (int, float) or (isinstance(value, int) and value.bit_length() > 4096) or (isinstance(value, float) and not math.isfinite(value)):
                raise ValueError('结果超出支持的数值范围')
            return value

        try:
            tree = ast.parse(expression, mode='eval')
            if sum(1 for _ in ast.walk(tree)) > 200:
                raise ValueError('表达式过于复杂')
            value = visit(tree.body)
        except (SyntaxError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
            raise ValueError('表达式无效、除数为零或结果超出范围') from None
        return {'expression': expression, 'result': value}
