from xml.sax.saxutils import escape

from sakubot.plugin import Plugin
from sakubot.office_support import source, destination, save_new, result, bounded, render_pdf


class Extension(Plugin):
    name = 'pdf'

    def setup(self):
        for name in ('read', 'create', 'render', 'merge', 'form'):
            self.function(getattr(self, name), name='pdf_' + name)

    def read(self, path: str, start_page: int = 1, page_count: int = 3, tables: bool = False):
        """读取工作空间 PDF 的文字、页数和可选表格。页码从1开始，一次最多5页；扫描件没有文本时需要渲染识别，不能据此断言空白。表格提取不保证视觉布局。"""
        import pdfplumber
        file = source(self, path, {'.pdf'})
        if start_page < 1 or not 1 <= page_count <= 5:
            raise ValueError('起始页从1开始，每次读取1到5页')
        with pdfplumber.open(file) as pdf:
            if start_page > len(pdf.pages):
                raise ValueError('页码超出范围')
            rows = []
            for index in range(start_page - 1, min(len(pdf.pages), start_page - 1 + page_count)):
                page = pdf.pages[index]
                row = {'page': index + 1, 'text': page.extract_text() or ''}
                if tables:
                    row['tables'] = page.extract_tables()
                rows.append(row)
            return bounded({'path': path, 'total_pages': len(pdf.pages), 'pages': rows,
                'next_page': start_page + len(rows) if start_page + len(rows) <= len(pdf.pages) else None})

    def create(self, output: str, title: str, blocks: list[dict]):
        """创建排版 PDF，新文件保存在工作空间，不覆盖原件。blocks 中 type 支持 paragraph/heading/bullet/table/page_break；文字放 text，heading 可带 level=1或2，table 放 rows 二维数组。支持中文字体。完成后用 pdf_render 检查排版，最终用消息插件发送文件。

        Args:
            output(string): 新文件相对路径，以 .pdf 结尾。
            title(string): 文档标题。
            blocks(array): 结构化正文块，复杂图表可读取 Skill 后使用 reportlab 脚本。
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        target = destination(self, output, {'.pdf'})
        if len(blocks) > 1000:
            raise ValueError('正文块过多，请使用工作空间脚本分批构建')
        if 'SakuCJK' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('SakuCJK', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', subfontIndex=0))
            pdfmetrics.registerFontFamily('SakuCJK', normal='SakuCJK', bold='SakuCJK', italic='SakuCJK', boldItalic='SakuCJK')
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            style.fontName = 'SakuCJK'
            style.wordWrap = 'CJK'
            style.textColor = colors.HexColor('#17212b')
        styles['BodyText'].fontSize = 10.5
        styles['BodyText'].leading = 16
        styles['BodyText'].spaceAfter = 8
        paragraph = lambda value, style='BodyText': Paragraph(escape(str(value)).replace('\n', '<br/>'), styles[style])
        story = [paragraph(title, 'Title'), Spacer(1, 14)] if title else []
        for block in blocks:
            kind = block.get('type', 'paragraph')
            if kind == 'page_break':
                story.append(PageBreak())
            elif kind == 'table':
                rows = block.get('rows', [])
                if not rows or max(map(len, rows)) > 12:
                    raise ValueError('表格需非空，且最多12列')
                count = max(map(len, rows))
                cells = [[paragraph(value) for value in row] + [''] * (count - len(row)) for row in rows]
                table = Table(cells, colWidths=[(A4[0] - 104) / count] * count, repeatRows=1)
                table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8edf3')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, 0), 0.6, colors.HexColor('#9aa8b7')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7)]))
                story.extend([table, Spacer(1, 10)])
            elif kind in ('paragraph', 'heading', 'bullet'):
                text = block.get('text', '')
                style = 'Heading2' if block.get('level') == 2 else 'Heading1' if kind == 'heading' else 'BodyText'
                if kind != 'heading':
                    style = 'BodyText'
                story.append(paragraph(('• ' if kind == 'bullet' else '') + str(text), style))
            else:
                raise ValueError('未知正文块类型：' + str(kind))
        if not story:
            raise ValueError('文档不能为空')
        save_new(target, lambda staging: SimpleDocTemplate(str(staging), pagesize=A4,
            leftMargin=52, rightMargin=52, topMargin=48, bottomMargin=48, title=title).build(story))
        return result(self, target)

    async def render(self, invocation, path: str, pages: list[int] = None):
        """将 PDF 指定页面渲染为 PNG，返回预览附件与路径，每次最多4页。默认第1页。当前模型有图像能力时前两页作为一次性视觉观察进入下一次请求；vision.queued=false 时未进行目视检查。"""
        return await render_pdf(self, invocation, source(self, path, {'.pdf'}), pages if pages is not None else [1])

    def merge(self, paths: list[str], output: str):
        """按给定顺序合并1到20个工作空间 PDF，输出新文件；不会覆盖原件。交互表单、签名或复杂书签应先读取 Skill，不保证合并后签名仍有效。"""
        from pypdf import PdfWriter
        if not 1 <= len(paths) <= 20:
            raise ValueError('每次合并1到20个文件')
        target = destination(self, output, {'.pdf'})
        with PdfWriter() as writer:
            for path in paths:
                writer.append(source(self, path, {'.pdf'}))
            save_new(target, lambda staging: writer.write(str(staging)))
        return result(self, target)

    def form(self, path: str, output: str = '', values: dict = None):
        """读取普通 AcroForm 字段；提供 values 和新 output 时填写并保留交互性。values 的键必须是实际字段名，复选框使用字段导出值如 /Yes。拒绝已签名、XFA 或缺失字段结构的表单，不自动扁平化或修复。填写后核对字段值及外观，仍需 pdf_render 目视检查。"""
        from pypdf import PdfReader, PdfWriter
        file = source(self, path, {'.pdf'})
        reader = PdfReader(file)
        fields = reader.get_fields() or {}
        if values is None:
            return bounded({'fields': [{'name': name, 'type': str(row.get('/FT', '')), 'value': str(row.get('/V', '')),
                'options': [str(value) for value in row.get('/Opt', [])]} for name, row in fields.items()]})
        target = destination(self, output, {'.pdf'})
        if not fields or set(values) - set(fields):
            raise ValueError('字段不存在或表单结构缺失，请先读取字段')
        form = reader.trailer['/Root'].get('/AcroForm')
        if form and '/XFA' in form.get_object():
            raise ValueError('当前不支持 XFA 表单')
        if any(row.get('/FT') == '/Sig' and row.get('/V') for row in fields.values()):
            raise ValueError('已签名 PDF 不自动修改')
        if any(fields[name].get('/FT') == '/Sig' for name in values):
            raise ValueError('不能通过填写工具写入签名字段')
        with PdfWriter(clone_from=reader) as writer:
            writer.update_page_form_field_values(None, values, auto_regenerate=False)
            def write(staging):
                writer.write(str(staging))
                check = PdfReader(staging)
                actual = check.get_fields() or {}
                for name, value in values.items():
                    if name not in actual or str(actual[name].get('/V', '')) != str(value):
                        raise ValueError('填写后的逻辑字段值不一致，未输出文件')
                seen = set()
                for page in check.pages:
                    for ref in page.get('/Annots', []):
                        widget = ref.get_object()
                        if widget.get('/Subtype') != '/Widget':
                            continue
                        names, effective, node = [], None, widget
                        for _ in range(32):
                            if node.get('/T'):
                                names.append(str(node['/T']))
                            if effective is None and '/V' in node:
                                effective = node['/V']
                            if not node.get('/Parent'):
                                break
                            node = node['/Parent'].get_object()
                        name = '.'.join(reversed(names))
                        if name in values:
                            if str(effective) != str(actual[name].get('/V', '')) or not widget.get('/AP') or not widget['/AP'].get('/N'):
                                raise ValueError('字段控件值或外观不完整，未输出文件')
                            seen.add(name)
                if set(values) - seen:
                    raise ValueError('填写字段缺少可核对的页面控件，未输出文件')
            save_new(target, write)
        return result(self, target)
