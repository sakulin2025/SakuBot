# 公式与版式参考

## 快速工具输入

```json
{
  "output":"output/spreadsheets/budget.xlsx",
  "sheets":[{
    "name":"预算",
    "rows":[["项目","数量","单价","金额"],["材料",2,15,{"formula":"=B2*C2"}]],
    "widths":[24,12,14,16],
    "freeze":"A2",
    "header":true
  }]
}
```

再调用 spreadsheet_update 设置需要的数字格式，生成另一个新文件；或直接在脚本中一次完成样式。最后对最终版本重算，不要把无缓存原件当作结果交付。

## openpyxl 脚本

通过 workspace_shell 运行保存到 tmp/ 的脚本，复杂耗时构建使用后台 Shell 机制。

```python
from pathlib import Path
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, Alignment

book = Workbook()
ws = book.active
ws.title = '进展'
for row in [['月份','完成数'],['一月',12],['二月',18],['三月',15]]:
    ws.append(row)
ws['A6'] = '总计'
ws['B6'] = '=SUM(B2:B4)'
ws.freeze_panes = 'A2'
ws.auto_filter.ref = 'A1:B4'
ws.column_dimensions['A'].width = 20
ws.column_dimensions['B'].width = 16
for row in ws:
    for cell in row:
        cell.font = Font(name='Noto Sans CJK SC', size=11)
        cell.alignment = Alignment(vertical='top')
chart = BarChart()
chart.add_data(Reference(ws, min_col=2, min_row=1, max_row=4), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=4))
chart.title = '月度进展'
ws.add_chart(chart, 'D2')
ws.sheet_properties.pageSetUpPr.fitToPage = True
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 0
ws.print_area = 'A1:M18'
Path('output/spreadsheets').mkdir(parents=True, exist_ok=True)
book.save('output/spreadsheets/progress.xlsx')
```

脚本直接写入以=开头字符串会创建公式，只有明确需要的公式才这样写。非可信外部文本需设置 cell.data_type='s'，不能盲目复制CSV公式。

## 计算与检查

openpyxl 的 `load_workbook(data_only=False)` 读取公式，`data_only=True` 读取既有缓存；前者不会更新后者。当前工具通过独立 LibreOffice profile 重新计算，再由 openpyxl 检查已保存缓存。不要伪造缓存或手工替换公式为结果。

对公式复制范围检查首项、中间项和末项；核对相对/绝对引用、单位、日期口径和分母。没有数据与0要分开。汇总需能追溯到实际明细；出现错误、重复记录、循环引用或不支持函数时应调查，不能隐藏错误后宣称通过。

用户需要情景切换、输入联动或可扩展表时，使用一个明确的输入或情景选择源，让构建和输出真实依赖它；不要堆叠静态结果冒充可重算模型。只有用户授权验证时，才在临时副本改变输入检查依赖，保留原件。

## 布局

- 简单任务可只用一张表，复杂任务才分输入、计算和输出；不额外添加装饰性空白标签页。
- 数值保存为数值，格式使用 Excel 标准代码：#,##0、0.0%、0.00%、yyyy-mm-dd；不要为了本地显示习惯交换格式中的逗号和小数点。
- 列宽、行高与实际文字匹配，避免 ####、遮挡、无意义大空白。不要用过小字体强塞。
- 图表引用实际数据，不用截图冒充可编辑原生图表；检查轴、单位、标签及数据范围。
- 财务、医疗、营销和科研有各自单位与精度要求；遵从用户模板，不将财务配色和模型结构强加给普通清单。
- 来源沿用已有输入页或输入区域旁的记录方式，不默认创建新来源页，不给每个普通单元格添加批注。

## 预览范围

在临时副本中设置 ws.print_area 后调用 spreadsheet_render。不要为预览而改变原件打印设置。跨多页的表格按 total_pages 检查；LibreOffice 的页面只是它自己的打印结果，不证明 Excel 完全一致。
