"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class FileResult(TypedDict, total=False):
    path: Required[Annotated[str, '产物工作空间相对路径']]
    bytes: Required[Annotated[int, '文件字节数']]
    artifact: Annotated[Artifact, '文件不超过发布上限时附带附件信息']
    recalculated: Annotated[bool, '是否已完成表格重算']

class Preview(TypedDict, total=False):
    page: Required[Annotated[int, '1起始页码']]
    path: Required[Annotated[str, '预览图片路径']]
    bytes: Required[Annotated[int, '图片字节数']]
    artifact: Annotated[Artifact, '可发布的预览附件']

class RenderResult(TypedDict, total=False):
    total_pages: Required[Annotated[int, '文档总页数']]
    previews: Required[Annotated[list[Preview], '本次渲染的页面']]
    vision: Required[Annotated[DynamicObject, '是否已把图片提交给当前视觉模型；queued=false 时含原因']]
    pdf: Annotated[FileResult, '先转换得到的 PDF 资料']

class PdfPage(TypedDict, total=False):
    page: Required[Annotated[int, '1起始页码']]
    text: Required[Annotated[str, '提取文本，扫描件可能为空']]
    tables: Annotated[list[list[list[str | None]]], '抽取的表格：表格/行/单元格，单元格可能为空']

class PdfRead(TypedDict, total=False):
    path: Required[Annotated[str, '源 PDF 路径']]
    total_pages: Required[Annotated[int, '总页数']]
    pages: Required[Annotated[list[PdfPage], '本页读取的页面']]
    next_page: Required[Annotated[int | None, '下一起始页，无后续为空']]

class FormField(TypedDict, total=False):
    name: Required[Annotated[str, '表单字段名']]
    type: Required[Annotated[str, 'PDF /FT 字段类型']]
    value: Required[Annotated[str, '当前文本值']]
    options: Required[Annotated[list[str], '可选项']]

class FormResult(TypedDict, total=False):
    fields: Required[Annotated[list[FormField], 'PDF 表单字段']]

class Block(TypedDict, total=False):
    index: Required[Annotated[int, '正文块序号']]
    type: Required[Annotated[str, 'paragraph/table']]
    style: Annotated[str, '段落样式名']
    text: Annotated[str, '段落文字']
    rows_total: Annotated[int, '表格总行数']
    columns_total: Annotated[int, '表格总列数']
    rows: Annotated[list[list[str]], '表格单元格文字']
    truncated: Required[Annotated[bool, '该块是否截断']]

class DocumentRead(TypedDict, total=False):
    path: Required[Annotated[str, '文档路径']]
    blocks: Required[Annotated[list[Block], '本页正文块']]
    total_blocks: Required[Annotated[int, '正文块总数']]
    next_offset: Required[Annotated[int | None, '下一页块偏移']]

class Cell(TypedDict, total=False):
    value: Required[Annotated[str | float | int | bool | None | DynamicObject, '单元格实际值；特殊日期/时长按工具约定转换']]
    formula: Annotated[str | DynamicObject, '公式文本或复杂公式元数据']

class Dimensions(TypedDict, total=False):
    rows: Required[Annotated[int, '最大行数']]
    columns: Required[Annotated[int, '最大列数']]

class SheetRead(TypedDict, total=False):
    path: Required[Annotated[str, '表格路径']]
    range: Required[Annotated[str, 'A1 读取范围']]
    rows: Required[Annotated[list[list[Cell]] | list[list[str]], 'XLSX 为单元格对象二维数组；CSV/TSV 为文本二维数组']]
    sheets: Annotated[list[str], '工作表名列表']
    sheet: Annotated[str, '实际工作表名']
    dimensions: Annotated[Dimensions, '工作表范围']
    values_are_text: Annotated[bool, 'CSV/TSV 模式为true']

class _SheetError(TypedDict, total=False):
    sheet: Annotated[str, '工作表名']
    cell: Annotated[str, '单元格坐标']
    value: Annotated[str, '错误文本']
    error: Annotated[str, 'Excel 错误文本，例如 #DIV/0!']
    formula: Annotated[str | DynamicObject, '相关公式']
SheetError: TypeAlias = Annotated[_SheetError, {'additionalProperties': True}]

class ErrorReport(TypedDict, total=False):
    scanned_cells: Required[Annotated[int, '已扫描单元格数']]
    complete: Required[Annotated[bool, '是否扫描完毕']]
    formula_cache_missing: Required[Annotated[int, '公式缓存缺失数量']]
    formula_blank_string_results: Required[Annotated[int, '公式空字符串结果数']]
    errors: Required[Annotated[list[SheetError], '错误列表']]
    errors_capped: Required[Annotated[bool, '错误列表是否达到100项上限']]

R_pdf_create: TypeAlias = FileResult
R_pdf_merge: TypeAlias = FileResult
R_document_create: TypeAlias = FileResult
R_document_replace: TypeAlias = FileResult
R_document_convert: TypeAlias = FileResult
R_spreadsheet_create: TypeAlias = FileResult
R_spreadsheet_update: TypeAlias = FileResult
R_spreadsheet_recalculate: TypeAlias = FileResult
R_pdf_render: TypeAlias = RenderResult
R_document_render: TypeAlias = RenderResult
R_spreadsheet_render: TypeAlias = RenderResult
R_pdf_read: TypeAlias = PdfRead
R_pdf_form: TypeAlias = FileResult | FormResult
R_document_read: TypeAlias = DocumentRead
R_spreadsheet_read: TypeAlias = SheetRead
R_spreadsheet_errors: TypeAlias = ErrorReport

RESULTS = {'pdf_create': R_pdf_create, 'pdf_merge': R_pdf_merge, 'document_create': R_document_create, 'document_replace': R_document_replace, 'document_convert': R_document_convert, 'spreadsheet_create': R_spreadsheet_create, 'spreadsheet_update': R_spreadsheet_update, 'spreadsheet_recalculate': R_spreadsheet_recalculate, 'pdf_render': R_pdf_render, 'document_render': R_document_render, 'spreadsheet_render': R_spreadsheet_render, 'pdf_read': R_pdf_read, 'pdf_form': R_pdf_form, 'document_read': R_document_read, 'spreadsheet_read': R_spreadsheet_read, 'spreadsheet_errors': R_spreadsheet_errors}
