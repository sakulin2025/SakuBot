---
name: Word 文档制作与编辑
description: 创建、读取或修改 DOCX、处理段落和表格、转换旧 Word 文档，以及渲染预览或导出 PDF 时使用。
---
# Word 文档制作与编辑

本技能使用 python-docx、OOXML、LibreOffice 与 Poppler，文件在共享工作空间内。默认成品保存在 `output/documents/`，脚本放 `tmp/`，预览放 `output/previews/`。保留原件，用新输出名。

## 工作流

1. 先确定读者、用途、交付格式及是否有模板。已有文档先 `document_read`，不为了改一处而重写全文。旧 DOC/ODT/RTF 用 `document_convert` 另存 DOCX。
2. 新建普通文档用 `document_create`，复杂排版和图表先阅读 [编程与编辑参考](references/python.md)。编辑简单文字用 `document_replace`，原文必须唯一匹配；复杂 OOXML、批注或修订不能用整段赋值替代。
3. `document_render` 将文件转换成 PDF 并渲染指定页。模型有图像能力时收到前两页临时观察；检查 `vision` 状态。按 `total_pages` 分批覆盖需要审查的页面。
4. 检查表格、段落间距、标题层级、页边距、孤行、裁切、字体和页码；修订后检查最新版。内容修改也要核对原文事实、范围与单位。
5. 用 `message_send` 或 `workspace_publish` 发送最终 DOCX；用户需要 PDF 时另行转换并检查。不要默认附带脚本、临时 PDF 或预览图。

## 基础函数

- `document_read(path,offset=0,limit=30)`：按正文顺序读取段落/表格，含样式及分页信息。页眉、页脚、批注、修订不保证包含在正文提取中。
- `document_create(output,title,blocks)`：paragraph、heading、bullet、table、page_break。标题采用原生 Title 样式，默认 A4 和中文字体。
- `document_replace(path,output,changes)`：唯一原文匹配，保留普通 run 格式，跨 run 替换继承起始 run 格式；不跨段落。
- `document_convert(path,output)`：输出 PDF、DOCX 或 UTF-8 TXT；转换不是无损承诺。
- `document_render(path,pages=[1])`：页面预览和可选的临时视觉观察。

## 写作与版式

标题具体、明确；开头交代主题、用途和读者需要知道的结论。使用原生标题层级、段落、列表、表格，不用空格或空行模拟布局。沿用用户模板与现有风格；新文档无模板时保持克制统一。正文应自然连贯，信息不足不编造来源、经历或承诺。

长表重复表头，设置合理列宽，不用过小字体强塞。图片保持比例，避免裁切和布局重叠。交付前检查全部相关页；没有图像能力时明确当前只做了结构处理，不能声称已目视验收。

## 范围

支持本地 Word 文件操作；不内置 Google Docs 云端连接、在线协作或 Codex 专用导入工具。高级批注/修订需按参考处理完整 OOXML 关系；基础 replace 工具不会擅自接受修订或删除批注。
