# Excel craft (openpyxl)

Use when the teacher asked for a real `.xlsx`. This is craft, not a scene workflow.
Use `csv`, `pandas`, `statistics`, or `datetime` when working with source data. A blank `Workbook()` is an empty shell.
A whole draft dumped in A1 is not a spreadsheet.

## Run

```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

# New file only. Existing file: see Edit existing — do not start a blank Workbook().
wb = Workbook()
ws = wb.active
ws.title = "汇总"

ws["A1"] = "分组"
ws["B1"] = "人数"
ws["C1"] = "占比"
header = Font(bold=True)
for col in ("A", "B", "C"):
    ws[f"{col}1"].font = header

ws["A2"] = "甲"
ws["B2"] = 12
ws["A3"] = "乙"
ws["B3"] = 8
ws["B4"] = "=SUM(B2:B3)"
ws["C2"] = "=B2/$B$4"
ws["C3"] = "=B3/$B$4"
ws["C2"].number_format = "0.0%"
ws["C3"].number_format = "0.0%"

ws.column_dimensions["A"].width = 14
ws.column_dimensions["B"].width = 10
ws.column_dimensions["C"].width = 10

detail = wb.create_sheet("明细")
detail["A1"] = "分组"
detail["B1"] = "人数"
detail["A2"] = "甲"
detail["B2"] = 12
detail["A3"] = "乙"
detail["B3"] = 8

wb.save(output_path)
```

## Edit existing

```python
from openpyxl import load_workbook

wb = load_workbook(input_path)
ws = wb.active
ws["B2"] = 95          # named cell only
# Other sheets, columns, formulas, charts, column widths stay.
wb.save(output_path)
```

Do not `wb = Workbook()` then retype the grid. That drops formulas, charts, and number formats.

## Rules

- Numbers live in cells as numbers (`12`), not the string `"12"`, unless the teacher asked for text.
- Formulas start with `=`. Do not hard-code a total that a formula should compute.
- One fact per cell. Headers on row 1. Do not put a markdown table into A1.
- Multi-sheet: `wb.create_sheet("名")`. Cross-sheet refs like `=明细!B2` are allowed.
- Column widths: `ws.column_dimensions["A"].width = …`.
- Dates: real date objects or ISO text the teacher gave — do not invent.
- Edit the named cell (`ws["B2"]`) to preserve other sheets, formulas, and styles.

## Check

At least one numeric cell (not a title wall). If the teacher named groups and counts, those values are in the grid. Wrong → rewrite with the same title.
In the workspace, also render the pages and look at them before you answer (Workspace rules: first, last, pages with tables / pictures; at most 8).
