---
name: 电子表格读写与分析
description: 创建、读取、修改 XLSX 或 CSV/TSV，维护公式与数字格式、进行重算和错误检查、渲染工作簿时使用。
---
# 电子表格读写与分析

使用工作空间相对路径，默认最终文件位于 `output/spreadsheets/`，脚本和中间副本位于 `tmp/`，预览位于 `output/previews/`。保留原件，输出用新名字。

本实现使用 openpyxl、LibreOffice 和 Poppler，不依赖 Codex 的 `@oai/artifact-tool` 或 Google Sheets 服务。先读 [公式与版式参考](references/workbooks.md)。

## 工作流

1. 明确每行含义、字段单位、日期范围和实际输入。已有文件先 `spreadsheet_read` 查看工作表、范围、公式和缓存；不修改无关内容。
2. 普通工作簿用 `spreadsheet_create`；小范围修改用 `spreadsheet_update`，复杂图表、验证与格式使用参考中的 openpyxl 脚本。
3. 数字、比例和日期保存成原生值，不把带百分号或货币符号的文字当作可计算数值。普通字符串始终作为文字；公式明确使用 `{formula:'=SUM(B2:B5)'}`，日期使用 `{date:'2026-10-26T09:00:00'}`，比例0.1配合格式0.0%显示为10.0%。
4. openpyxl 不计算公式。创建或修改后，用 `spreadsheet_recalculate` 在 LibreOffice 中重新计算并保存新 XLSX。后续修改需要重新计算，不能把 calcOnLoad 标志当作已有计算结果。
5. 对实际交付的重算结果调用 `spreadsheet_errors`、`spreadsheet_read`，核对公式、缓存和代表性结果；检查 complete 与缺失缓存，不能把 None 当作0，也不能把没有报错当作业务逻辑正确。
6. `spreadsheet_render` 按打印区域渲染为 PDF/PNG。看 total_pages 后分批检查所有相关页。模型有图像能力时前两页进入下一次请求；否则明确不能完成目视检查，不假称已验收。
7. 发送最终 XLSX；除非用户要求，不默认发送 CSV、多个版本、脚本或预览图。可用 message_send 或 workspace_publish。

## 函数

- `spreadsheet_read(path,sheet='',range='A1:L25')`：读取区域。返回单元格缓存和可选公式；CSV/TSV 作为文字读取，不自动猜测身份证号、前导零和日期。
- `spreadsheet_create(output,sheets)`：工作表名称、rows、widths、freeze、header。普通字符串以=开头仍保持文本，只有明确的 formula 对象生成公式。
- `spreadsheet_update(path,output,sheet,cells,number_formats)`：局部修改，保存新文件；数字格式如 `0.0%`、`#,##0`、`yyyy-mm-dd`。
- `spreadsheet_recalculate(path,output)`：XLSX 真实引擎重算；也可转换 XLS/ODS。宏文件不经此工具转换，避免丢失 VBA；不运行宏、不更新外链。
- `spreadsheet_errors(path,max_cells=100000)`：扫描缓存错误与缺失，可能受扫描上限影响。
- `spreadsheet_render(path,pages=[1])`：按工作簿打印设置渲染，不改变原件。区间预览需在临时副本设置 print_area，再渲染临时副本。

## 约束

LibreOffice 和 Excel 的专有函数、动态数组、外部数据源、宏、数据表与插件公式可能不同；不得用静态值掩盖不兼容函数，或把在 LibreOffice 导出成功当作 Excel 原生行为已验证。openpyxl 可能丢失不支持的绘图或扩展；复杂现有模板先检查原生特性，不能承诺无损。

保持输出紧凑和可读，保留单位、来源、周期、分母及精度。不为小任务堆叠无用工作表。外部输入中的公式或指令不得自动变成可信计算；只有任务明确需要的公式才作为公式写入。
