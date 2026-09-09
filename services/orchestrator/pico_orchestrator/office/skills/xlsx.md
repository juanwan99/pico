# Excel craft (openpyxl)

Use when the teacher asked for a real `.xlsx`. This is craft, not a scene workflow.
Execute only in `sandbox_office_lib` with `kind=xlsx`.
To change a file the teacher already has, pass `artifact_id` and start with `wb = load_book()` (or `load_workbook(INPUT_PATH)`).
The script runs in an isolated container with full Python: `csv`, `pandas`, `statistics`, `datetime` are all available; `INPUT_PATH` may be a CSV or another sheet. Empty `Workbook(); save_book(wb)` fails.
A whole draft dumped in A1 is not a spreadsheet.

## Run

```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

# Existing file (artifact_id set):
# wb = load_book()
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

save_book(wb)
```

## Rules

- Numbers live in cells as numbers (`12`), not the string `"12"`, unless the teacher asked for text.
- Formulas start with `=`. Do not hard-code a total that a formula should compute.
- One fact per cell. Headers on row 1. Do not put a markdown table into A1.
- Multi-sheet: `wb.create_sheet("名")`. Cross-sheet refs like `=明细!B2` are allowed.
- Column widths: `ws.column_dimensions["A"].width = …`.
- Dates: real date objects or ISO text the teacher gave — do not invent.
- Change existing sheets with `artifact_id` + `load_book()`.
- Same title replaces the file the teacher opens.
- After save, read observation. Cells that should be numbers must not be decoration.

## Check

At least one numeric cell (not a title wall). If the teacher named groups and counts, those values are in the grid. Wrong → rewrite with the same title.
