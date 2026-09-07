# Word craft (python-docx)

Use when the teacher asked for a real `.docx`. This is craft, not a scene workflow.
Execute only in `sandbox_office_lib` with `kind=docx`.
To change a file the teacher already has, pass `artifact_id` and start with `doc = load_doc()` (or `Document(INPUT_PATH)`). Do not rebuild with `generate_docx_document`.
`generate_docx_document` is blank-template only.
Do not import os. Do not use a shell. Empty `Document(); save_doc(doc)` fails.

## Run

```python
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# Existing file (artifact_id set):
# doc = load_doc()
doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.27)
section.page_height = Inches(11.69)
section.left_margin = Cm(2.5)
section.right_margin = Cm(2.5)
section.top_margin = Cm(2.2)
section.bottom_margin = Cm(2.2)

style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(11)
style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

doc.add_heading("标题", level=1)
p = doc.add_paragraph("正文第一段。老师点名要的事实写在这里，不要空壳。")
p.paragraph_format.space_after = Pt(8)

head = section.header.paragraphs[0]
head.text = "页眉 · 单位名"
foot = section.footer.paragraphs[0]
foot.text = "第 页"

table = doc.add_table(rows=2, cols=3)
table.style = "Table Grid"
table.rows[0].cells[0].text = "项"
table.rows[0].cells[1].text = "说明"
table.rows[0].cells[2].text = "备注"
table.rows[1].cells[0].text = "交付"
table.rows[1].cells[1].text = "真 Word"
table.rows[1].cells[2].text = "可打开"

if IMAGE_PATHS:
    doc.add_picture(IMAGE_PATHS[0], width=Inches(5.2))

save_doc(doc)
```

## Rules

- Headings: `add_heading(..., level=1..3)`. Do not fake a heading with bold-only body text when a heading is needed.
- Paragraphs: one idea per paragraph. Blank lines in source are not pages.
- Tables: real `add_table`; put values in cells. A screenshot of a table is not a table.
- Header/footer: `section.header` / `section.footer`. Page numbers are footer text unless you attach a PAGE field; do not claim a field you did not add.
- Lists: `doc.add_paragraph("项", style="List Bullet")` or `List Number`.
- East-Asian font: set `w:eastAsia` on the run or Normal style. Latin `font.name` alone will not pick 宋体.
- Pictures: only `IMAGE_PATHS[i]` from `image_artifact_ids`. Do not invent a host path.
- Same title replaces the file the teacher opens. Change existing files with `artifact_id` + `load_doc()`, not `generate_docx_document`.
- After save, the tool observation is what landed. `ok` is not finished.

## Check

Open the bytes in your head against the observation: heading present, body has the teacher's facts, table cells are not empty, file is `.docx`. If wrong, call `sandbox_office_lib` again with the same title.
