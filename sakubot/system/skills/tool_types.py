"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Skill(TypedDict, total=False):
    id: Required[Annotated[str, '完整技能 ID']]
    name: Required[Annotated[str, '名称']]
    description: Required[Annotated[str, '使用场景']]
    plugin_id: Required[Annotated[str, '来源插件，独立技能可能为空']]
    source: Required[Annotated[str, '来源标签']]
    version: Required[Annotated[str, '正文版本哈希']]
    content: Annotated[str, '含 frontmatter 的完整 SKILL.md']
    body: Annotated[str, '去掉 frontmatter 的正文']
    directory: Annotated[str, '技能所在目录']
    files: Annotated[list[str], '附属文件相对路径']

class Listing(TypedDict, total=False):
    items: Required[Annotated[list[Skill], '本页技能条目']]
    total: Required[Annotated[int, '匹配总数']]
    has_more: Required[Annotated[bool, '是否还有条目']]

class FilePage(TypedDict, total=False):
    id: Required[Annotated[str, '技能 ID']]
    path: Required[Annotated[str, '技能内相对路径']]
    version: Required[Annotated[str, '文件版本']]
    size: Required[Annotated[int, '字节数']]
    binary: Required[Annotated[bool, '是否二进制']]
    content: Required[Annotated[str, '本页正文']]
    has_more: Required[Annotated[bool, '是否还有正文']]
    offset: Annotated[int, '本页行偏移']
    next_offset: Annotated[int, '下一页偏移']
    total_lines: Annotated[int, '总行数']

R_skill_list: TypeAlias = Listing
R_skill_read: TypeAlias = Skill
R_skill_read_file: TypeAlias = FilePage

RESULTS = {'skill_list': R_skill_list, 'skill_read': R_skill_read, 'skill_read_file': R_skill_read_file}
