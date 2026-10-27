# PDF、文档和表格技能移植（0.19.0）

> 0.20.0 更新：基础能力改由系统自动提供；PDF、Word、表格现合并为一个 office 文档处理插件。当前架构见 [系统能力与扩展](system-and-extensions.md)。

将当前会话的 pdf、documents、spreadsheets 工作流程移植成三个 SakuBot 内置插件，使用公共 Plugin API 注册工具和只读 Skill。不是复制 Codex 专用运行时、云端连接或引用指令；没有新增平台/会话权限控制。

| 插件 | 工具 |
| --- | --- |
| PDF | pdf_read、pdf_create、pdf_render、pdf_merge、pdf_form |
| 文档 | document_read、document_create、document_replace、document_convert、document_render |
| 表格 | spreadsheet_read、spreadsheet_create、spreadsheet_update、spreadsheet_recalculate、spreadsheet_errors、spreadsheet_render |

每个插件自带 SKILL.md 和编程参考，含工作空间输出约定、读写示例、内容/版式检查、格式限制与附件交付流程。没有配置项和额外管理页面；可在现有插件页启停，在能力页查看 Skill 和函数。人格的显式插件可见性保持原设置。

## 依赖与文件

镜像包含 python-docx、openpyxl、reportlab、pdfplumber、pypdf、Pillow 及其锁定依赖。系统增加 LibreOffice Writer/Calc、Poppler、Liberation、Noto CJK 和文泉驿字体。没有从原 Codex 依赖目录复制二进制或 Node 专用库。

源文件位于工作空间，基础工具保留原件并要求新输出名。成品默认 output/pdf、output/documents、output/spreadsheets；预览位于 output/previews。附件沿用框架20 MiB上限，大文件返回本地路径供后续处理。工具结果限制在消息预算内，读取过大时要求缩小范围。

LibreOffice 每次转换使用独立临时 profile，最多并行两个进程，禁用宏与外链更新；超时/取消终止进程组。转换结果通过完整临时文件写完后再发布，避免半文件和覆盖已有文件。

## 视觉观察

公共插件接口 `plugin.preview_images(invocation, paths, note=...)` 把最多两张本地预览图压缩后，作为下一次模型请求的临时观察。当前模型需有图像能力；否则返回 queued=false，工具和 Skill 明确禁止宣称目视检查通过。PNG 原图和附件仍可查看。

图像观察不加入 Agent 历史或压缩摘要；追踪仅保留预览文件路径，不写入 base64。请求预算按图像成本估算，避免把传输用 base64 当作文本 Token；裁剪历史时保留原任务，不能用后来的图片观察替代任务边界。

## 范围与局限

- PDF：静态文本/表格提取、基础排版、渲染、合并及普通 AcroForm 填写。表单重开核对字段/控件/外观，不自动扁平化、修复结构、修改签名或支持 XFA。未内置 OCR，扫描件通过图像模型阅读。
- Word：本地 DOCX 读写、普通 run 保真替换，LibreOffice 转换旧格式和 PDF 预览。高级批注、修订、字段等在 Skill 中指引 OOXML 处理，基础替换工具遇到相关结构会拒绝，不伪装成已支持全部操作。不连接 Google Docs。
- 表格：XLSX 读写、CSV/TSV 读取、显式公式/日期类型、引擎重算、缓存错误检查、打印预览。XLS/ODS 可转换为 XLSX。openpyxl 可能损失不支持的对象，LibreOffice 不保证 Excel 专有函数/数据表/宏兼容；不以静态值掩盖差异。不连接 Google Sheets。

本次按用户要求不运行测试，只构建并检查部署加载；没有生成或发送测试文档，没有执行文档渲染验收或公式重算测试。Agent 实际处理文件时仍应按用户要求完成适用的输出检查。

## 参考接口

- [python-docx](https://python-docx.readthedocs.io/en/latest/user/quickstart.html)
- [openpyxl](https://openpyxl.readthedocs.io/en/stable/tutorial.html)
- [pypdf 表单](https://pypdf.readthedocs.io/en/stable/user/forms.html)
- [LibreOffice 转换过滤器](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html)
