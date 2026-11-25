# Word craft (python-docx)

Use when the teacher asked for a real `.docx`. This is craft, not a scene workflow.
Write actual content before saving. A blank `Document()` is an empty shell.

## Run

```python
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# New file only. Existing file: see Edit existing — do not start a blank Document().
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

# To embed a picture, pass its actual path to doc.add_picture(path, width=Inches(5.2)).

doc.save(output_path)
```

## Edit existing

```python
from docx import Document

doc = Document(input_path)
# Change the named paragraph / cell only. Other paragraphs, tables, header, styles stay.
for p in doc.paragraphs:
    if "春游" in p.text:
        for run in p.runs:
            if "春游" in run.text:
                run.text = run.text.replace("春游", "秋游")
doc.save(output_path)
```

Do not `doc = Document()` then copy text out. That drops styles, headers, and images.

## Rules

- Headings: `add_heading(..., level=1..3)`. Do not fake a heading with bold-only body text when a heading is needed.
- Paragraphs: one idea per paragraph. Blank lines in source are not pages.
- Tables: real `add_table`; put values in cells. A screenshot of a table is not a table.
- Header/footer: `section.header` / `section.footer`. Page numbers are footer text unless you attach a PAGE field; do not claim a field you did not add.
- Lists: `doc.add_paragraph("项", style="List Bullet")` or `List Number`.
- East-Asian font: set `w:eastAsia` on the run or Normal style. Latin `font.name` alone will not pick 宋体.
- Fonts: name the font the teacher's computer has — 宋体 / 黑体 / 楷体 / 仿宋 / 微软雅黑 for Chinese, Calibri / Times New Roman / Arial for Latin. Here they render with installed look-alikes (same style, Regular + Bold), so previews match. Do not name other fonts.
- Pictures: embed a real image, such as a PNG you render for the document.
- Edit runs in place (`p.runs`, table cells) to preserve existing formatting and content.

## Check

Check the saved `.docx` for the heading, the teacher's facts in the body, and populated table cells. If wrong, save the corrected file under the same name.
In the workspace, also render the pages and look at them before you answer (Workspace rules: first, last, pages with tables / pictures; at most 8).
