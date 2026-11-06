"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_pdf_read1 = TypedDict(
    'A_pdf_read1',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'start_page': NotRequired[Annotated[int, {'default': 1, 'description': '从1开始的起始页码'}]],
        'page_count': NotRequired[Annotated[int, {'default': 3, 'description': '一次读取的页数，1至5'}]],
        'tables': NotRequired[Annotated[bool, {'default': False, 'description': '是否同时抽取表格；不保证视觉布局'}]],
    },
    total=False,
)

A_pdf_read: TypeAlias = Annotated[A_pdf_read1, {'additionalProperties': False}]

A_pdf_create_blocksItem3 = TypedDict(
    'A_pdf_create_blocksItem3',
    {
        'type': Required[Annotated[str, {'description': '正文块分类：paragraph/heading/bullet/table/page_break'}]],
        'text': NotRequired[Annotated[str, {'description': '文字正文'}]],
        'level': NotRequired[Annotated[int, {'description': '标题级别，具体范围依 PDF/Word 工具'}]],
        'rows': NotRequired[Annotated[list[Annotated[list[Annotated[str, {'description': '单元格文字'}]], {'description': '一行单元格'}]], {'description': '表格的行'}]],
    },
    total=False,
)

A_pdf_create2 = TypedDict(
    'A_pdf_create2',
    {
        'output': Required[Annotated[str, {'description': '新文件相对路径，以 .pdf 结尾。'}]],
        'title': Required[Annotated[str, {'description': '文档标题。'}]],
        'blocks': Required[Annotated[list[Annotated[A_pdf_create_blocksItem3, {'description': '一个列表元素；结构化正文块，复杂图表可读取 Skill 后使用 reportlab 脚本。', 'additionalProperties': True}]], {'description': '结构化正文块，复杂图表可读取 Skill 后使用 reportlab 脚本。'}]],
    },
    total=False,
)

A_pdf_create: TypeAlias = Annotated[A_pdf_create2, {'additionalProperties': False}]

A_pdf_render4 = TypedDict(
    'A_pdf_render4',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'pages': NotRequired[Annotated[list[Annotated[int, {'description': '一个列表元素；元素结构由该参数定义'}]] | None, {'default': None, 'description': '要渲染的1起始页码列表，一次1至4页'}]],
    },
    total=False,
)

A_pdf_render: TypeAlias = Annotated[A_pdf_render4, {'additionalProperties': False}]

A_pdf_merge5 = TypedDict(
    'A_pdf_merge5',
    {
        'paths': Required[Annotated[list[Annotated[str, {'description': '一个列表元素；按合并顺序提供的 PDF 工作空间相对路径列表'}]], {'description': '按合并顺序提供的 PDF 工作空间相对路径列表'}]],
        'output': Required[Annotated[str, {'description': '新合并 PDF 相对路径'}]],
    },
    total=False,
)

A_pdf_merge: TypeAlias = Annotated[A_pdf_merge5, {'additionalProperties': False}]

A_pdf_form6 = TypedDict(
    'A_pdf_form6',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'output': NotRequired[Annotated[str, {'default': '', 'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
        'values': NotRequired[Annotated[dict[str, object] | None, {'default': None, 'description': '字段名到填写值的映射；省略或空对象时只读取字段定义'}]],
    },
    total=False,
)

A_pdf_form: TypeAlias = Annotated[A_pdf_form6, {'additionalProperties': False}]

A_document_read7 = TypedDict(
    'A_document_read7',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'offset': NotRequired[Annotated[int, {'default': 0, 'description': '从0开始的正文块偏移'}]],
        'limit': NotRequired[Annotated[int, {'default': 30, 'description': '最多返回的段落/表格块数'}]],
    },
    total=False,
)

A_document_read: TypeAlias = Annotated[A_document_read7, {'additionalProperties': False}]

A_document_create_blocksItem9 = TypedDict(
    'A_document_create_blocksItem9',
    {
        'type': Required[Annotated[str, {'description': '正文块分类：paragraph/heading/bullet/table/page_break'}]],
        'text': NotRequired[Annotated[str, {'description': '文字正文'}]],
        'level': NotRequired[Annotated[int, {'description': '标题级别，具体范围依 PDF/Word 工具'}]],
        'rows': NotRequired[Annotated[list[Annotated[list[Annotated[str, {'description': '单元格文字'}]], {'description': '一行单元格'}]], {'description': '表格的行'}]],
    },
    total=False,
)

A_document_create8 = TypedDict(
    'A_document_create8',
    {
        'output': Required[Annotated[str, {'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
        'title': Required[Annotated[str, {'description': '新文档标题'}]],
        'blocks': Required[Annotated[list[Annotated[A_document_create_blocksItem9, {'description': '一个列表元素；结构化正文块，复杂图表可读取 Skill 后使用 reportlab 脚本。', 'additionalProperties': True}]], {'description': '正文块列表，支持 paragraph/heading/bullet/table/page_break；文字为 text，表格为 rows 二维文本数组'}]],
    },
    total=False,
)

A_document_create: TypeAlias = Annotated[A_document_create8, {'additionalProperties': False}]

A_document_replace_changesItem11 = TypedDict(
    'A_document_replace_changesItem11',
    {
        'old': Required[Annotated[str, {'description': '待精确匹配的旧文字'}]],
        'new': Required[Annotated[str, {'description': '替换文字'}]],
    },
    total=False,
)

A_document_replace10 = TypedDict(
    'A_document_replace10',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'output': Required[Annotated[str, {'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
        'changes': Required[Annotated[list[Annotated[A_document_replace_changesItem11, {'description': '一个列表元素；按 old/new 对执行精确文本替换，每项旧文字须匹配；生成新文档不覆盖源文件', 'additionalProperties': False}]], {'description': '按 old/new 对执行精确文本替换，每项旧文字须匹配；生成新文档不覆盖源文件'}]],
    },
    total=False,
)

A_document_replace: TypeAlias = Annotated[A_document_replace10, {'additionalProperties': False}]

A_document_convert12 = TypedDict(
    'A_document_convert12',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'output': Required[Annotated[str, {'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
    },
    total=False,
)

A_document_convert: TypeAlias = Annotated[A_document_convert12, {'additionalProperties': False}]

A_document_render13 = TypedDict(
    'A_document_render13',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'pages': NotRequired[Annotated[list[Annotated[int, {'description': '一个列表元素；元素结构由该参数定义'}]] | None, {'default': None, 'description': '要渲染的1起始页码列表，一次1至4页'}]],
    },
    total=False,
)

A_document_render: TypeAlias = Annotated[A_document_render13, {'additionalProperties': False}]

A_spreadsheet_read14 = TypedDict(
    'A_spreadsheet_read14',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'sheet': NotRequired[Annotated[str, {'default': '', 'description': '工作表名称，留空使用首个工作表'}]],
        'range': NotRequired[Annotated[str, {'default': 'A1:L25', 'description': '单个 A1 范围，例如 A1:L25；最多100行50列2000格'}]],
    },
    total=False,
)

A_spreadsheet_read: TypeAlias = Annotated[A_spreadsheet_read14, {'additionalProperties': False}]

A_spreadsheet_create15 = TypedDict(
    'A_spreadsheet_create15',
    {
        'output': Required[Annotated[str, {'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
        'sheets': Required[Annotated[list[Annotated[dict[str, object], {'description': '一个列表元素；工作表定义列表：name、rows 二维值，可选 header、freeze、widths'}]], {'description': '工作表定义列表：name、rows 二维值，可选 header、freeze、widths'}]],
    },
    total=False,
)

A_spreadsheet_create: TypeAlias = Annotated[A_spreadsheet_create15, {'additionalProperties': False}]

A_spreadsheet_update16 = TypedDict(
    'A_spreadsheet_update16',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'output': Required[Annotated[str, {'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
        'sheet': Required[Annotated[str, {'description': '目标工作表的准确名称'}]],
        'cells': Required[Annotated[dict[str, object], {'description': 'A1单元格地址到新值的映射；支持标量、{date:ISO日期} 或 {formula:=公式}'}]],
        'number_formats': NotRequired[Annotated[dict[str, object] | None, {'default': None, 'description': 'A1地址到 Excel 数字格式字符串的映射'}]],
    },
    total=False,
)

A_spreadsheet_update: TypeAlias = Annotated[A_spreadsheet_update16, {'additionalProperties': False}]

A_spreadsheet_recalculate17 = TypedDict(
    'A_spreadsheet_recalculate17',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'output': Required[Annotated[str, {'description': '新产物的工作空间相对路径，不覆盖已有文件'}]],
    },
    total=False,
)

A_spreadsheet_recalculate: TypeAlias = Annotated[A_spreadsheet_recalculate17, {'additionalProperties': False}]

A_spreadsheet_errors18 = TypedDict(
    'A_spreadsheet_errors18',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'max_cells': NotRequired[Annotated[int, {'default': 100000, 'description': '最多扫描的单元格数，1至1000000'}]],
    },
    total=False,
)

A_spreadsheet_errors: TypeAlias = Annotated[A_spreadsheet_errors18, {'additionalProperties': False}]

A_spreadsheet_render19 = TypedDict(
    'A_spreadsheet_render19',
    {
        'path': Required[Annotated[str, {'description': '源文件的工作空间相对路径，扩展名需符合该工具支持的格式'}]],
        'pages': NotRequired[Annotated[list[Annotated[int, {'description': '一个列表元素；元素结构由该参数定义'}]] | None, {'default': None, 'description': '要渲染的1起始页码列表，一次1至4页'}]],
    },
    total=False,
)

A_spreadsheet_render: TypeAlias = Annotated[A_spreadsheet_render19, {'additionalProperties': False}]

ARGUMENTS = {'pdf_read': A_pdf_read, 'pdf_create': A_pdf_create, 'pdf_render': A_pdf_render, 'pdf_merge': A_pdf_merge, 'pdf_form': A_pdf_form, 'document_read': A_document_read, 'document_create': A_document_create, 'document_replace': A_document_replace, 'document_convert': A_document_convert, 'document_render': A_document_render, 'spreadsheet_read': A_spreadsheet_read, 'spreadsheet_create': A_spreadsheet_create, 'spreadsheet_update': A_spreadsheet_update, 'spreadsheet_recalculate': A_spreadsheet_recalculate, 'spreadsheet_errors': A_spreadsheet_errors, 'spreadsheet_render': A_spreadsheet_render}
