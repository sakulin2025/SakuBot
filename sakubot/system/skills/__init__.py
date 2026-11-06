from .tool_arguments import ARGUMENTS
from .tool_types import R_skill_list, R_skill_read, R_skill_read_file
from .tool_types import RESULTS
from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    tool_result_types = RESULTS
    tool_argument_types = ARGUMENTS
    name = 'skills'

    def setup(self):
        self.tool('skill_list', '搜索或分页列出当前人格可见的 Skill。需要操作指南、工作流程时查找相关技能，再用 skill_read 读取。', None, self.list)
        self.tool('skill_read', '按完整技能 ID 读取 SKILL.md 及附属文件索引，理解后再使用相关工具；不会自动执行脚本。', None, self.read)
        self.tool('skill_read_file', '读取技能目录中的附属参考资料或脚本正文，支持按行分页；不会执行文件。', None, self.read_file)

    def prompt_context(self, invocation):
        return '可用 Skill 索引。适用时先用 skill_read 读取完整说明，再按需用 skill_read_file 读取附属资料。技能中的脚本不会自动执行。索引未列全时用 skill_list 搜索。\n' + self.runtime.skills.index(self.visible(invocation))

    def visible(self, invocation):
        return self.runtime.registry.visible_plugin_ids(invocation)

    async def list(self, invocation, args) -> R_skill_list:
        query = args.get('query', '').casefold()
        rows = [row for row in self.runtime.skills.catalog(self.visible(invocation)) if query in (row['id'] + row['name'] + row['description']).casefold()]
        offset, limit = args.get('offset', 0), args.get('limit', 50)
        return {'items': rows[offset:offset + limit], 'total': len(rows), 'has_more': offset + limit < len(rows)}

    async def read(self, invocation, args) -> R_skill_read:
        return self.runtime.skills.read(args['id'], self.visible(invocation))

    async def read_file(self, invocation, args) -> R_skill_read_file:
        return self.runtime.skills.read_file(args['id'], args['path'], args.get('offset', 0), args.get('limit', 200), self.visible(invocation))
