# PDF 编程参考

运行环境已安装 reportlab、pdfplumber、pypdf、Pillow、Poppler。使用 `workspace_shell` 执行 Python，长任务用 `workspace_shell_start`，不用额外安装包。

## 快速构建

`pdf_create` 的 blocks 示例：

```json
[
  {"type":"heading","text":"项目进展","level":1},
  {"type":"paragraph","text":"截至本周的进展与下一步安排。"},
  {"type":"table","rows":[["项目","状态"],["文档","已完成"]]},
  {"type":"page_break"},
  {"type":"bullet","text":"下周完成复核"}
]
```

复杂内容用 reportlab.platypus 的 Paragraph、Table、PageBreak。文字进入 Paragraph 前使用 xml.sax.saxutils.escape；所有标题、表格与页码都指定中文字体。

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont('CJK', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', subfontIndex=0))
```

## 拆分与提取

```python
from pypdf import PdfReader, PdfWriter
reader = PdfReader('input.pdf')
writer = PdfWriter()
for index in [0, 2]:
    writer.add_page(reader.pages[index])
with open('output/pdf/extract.pdf', 'xb') as stream:
    writer.write(stream)
```

扫描件提取不了文字时使用渲染和图像模型，不声称完成 OCR。当前未内置 OCR 引擎。

## 手动渲染

```sh
pdftoppm -f 1 -l 1 -singlefile -scale-to 1400 -png input.pdf tmp/page-1
pdfinfo input.pdf
```

手动渲染只产生文件，模型不会自动看到。优先用 `pdf_render` 获得下一次请求的临时图像观察。

## 表单深入处理

先列出 reader.get_fields() 与每页 Annots 的 Widget，沿 Parent/Kids 检查全名、字段类型、值和 AP/N。相同名字并不证明两个对象属于同一字段。不能盲目 reattach_fields()，重复字段可能被掩盖。无法确认时停止填写，返回具体结构问题。

pypdf 的 update_page_form_field_values(None, values, auto_regenerate=False) 填写所有页；默认不 flatten。用户要求 flatten 时须重新核对所有现有值，绘制外观、移除 Widget、清除 AcroForm，再重新打开核对字段树与控件均已移除，最后渲染检查。签名文件不得自动走此流程。

加密文件需用户提供合适的可访问副本或明确的解密资料，不猜密码。操作不会证明原有数字签名仍有效。
