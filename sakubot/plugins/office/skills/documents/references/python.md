# DOCX 编程与编辑参考

## 结构化输入

```json
[
  {"type":"paragraph","text":"本报告说明项目现状与下周安排。"},
  {"type":"heading","level":1,"text":"当前进展"},
  {"type":"table","rows":[["任务","负责人"],["复核","张三"]]},
  {"type":"bullet","text":"确认交付日期"}
]
```

## 高级创建

python-docx 已安装。把脚本保存在工作空间 tmp/，由 workspace_shell 运行。需要图表、复杂图片、节、页眉、页脚或精确表格尺寸时使用库原生对象。

```python
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt
from docx.oxml.ns import qn

doc = Document()
style = doc.styles['Normal']
style.font.name = 'Noto Sans CJK SC'
style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), 'Noto Sans CJK SC')
style.font.size = Pt(11)
doc.add_heading('工作安排', 0)
doc.add_paragraph('本周完成资料整理并安排复核。')
Path('output/documents').mkdir(parents=True, exist_ok=True)
doc.save('output/documents/plan.docx')
```

完成后调用 document_render；直接在终端生成 PNG 不会自动给模型视觉输入。

## 编辑保真

读取段落及 run，修改已定位的文字。不要用 paragraph.text 整段替换，因为它会丢失 run 格式、超链接、字段等结构。document_replace 只处理普通段落中的唯一匹配；用户要求复杂编辑时先检查 zip 内 word/document.xml、styles.xml 与相关关系文件。

对需要保留原样的内容，谨慎处理节、页眉页脚、批注、脚注、书签、图片和目录。只修改获授权部分。字段文字显示不代表它在 Word 中会正确更新，转换 PDF 后也要核对。

## 批注与修订

批注需要 comments.xml、document.xml 中范围标记及 document.xml.rels 的关系项，必要时还涉及现代批注扩展。不能只插入一段可见的“批注”文字冒充真实批注。

修订需要 w:ins/w:del 等 OOXML 节点与作者/日期/唯一 ID；删除文字使用 w:delText。不要在用户只要求编辑时擅自接受、清除已有修订。没有可靠处理完整关系的实现时，说明当前范围而不伪造成功。

## 转换与渲染

LibreOffice 使用独立临时 profile、关闭宏与外链更新；不改变源文件。不同引擎的字体替换和分页仍可能不同，LibreOffice 渲染不证明 Microsoft Word 完全一致。

最终文件使用 message_send 的 path 发送。文件路径仅在容器工作空间内有效，不是远端下载链接。
