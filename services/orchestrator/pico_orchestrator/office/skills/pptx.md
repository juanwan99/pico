# PPT craft (python-pptx)

Use when the teacher asked for a real `.pptx`. This is craft, not a scene workflow.
Use Pillow or matplotlib to render chart images for `add_picture`. A blank `Presentation()` is an empty shell.
Stock body bullets are not the ceiling. Free geometry uses shapes + RGBColor.

## Run — built-in layouts for a simple talk track

```python
from pptx import Presentation

# New file only. Existing deck: see Edit existing — do not start a blank Presentation().
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "封面标题"
slide.placeholders[1].text = "副题"

slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "要点"
slide.placeholders[1].text = "第一条\n第二条\n第三条"
prs.save(output_path)
```

## Run — free layout (when it must not look like Title-and-Content)

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]
slide = prs.slides.add_slide(blank)

bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.1))
bar.fill.solid()
bar.fill.fore_color.rgb = RGBColor(0x1F, 0x4E, 0x79)
bar.line.fill.background()
title = slide.shapes.add_textbox(Inches(0.6), Inches(0.25), Inches(12), Inches(0.7))
tf = title.text_frame
tf.clear()
run = tf.paragraphs[0].add_run()
run.text = "本周经营风险与下周动作"
run.font.size = Pt(28)
run.font.bold = True
run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.6), Inches(5.8), Inches(4.8))
card.fill.solid()
card.fill.fore_color.rgb = RGBColor(0xF2, 0xF2, 0xF2)
card.line.fill.background()
body = slide.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(5.2), Inches(4.2))
frame = body.text_frame
frame.word_wrap = True
frame.clear()
p = frame.paragraphs[0]
p.text = "风险总览"
p.font.size = Pt(18)
p.font.bold = True
for line in ("收入端延期", "毛利承压", "回款变慢"):
    item = frame.add_paragraph()
    item.text = line
    item.level = 0
    item.font.size = Pt(16)

# To embed a picture, pass its actual path.
# slide.shapes.add_picture(path, Inches(7.0), Inches(1.6), width=Inches(5.4))

prs.save(output_path)
```

## Edit existing

```python
from pptx import Presentation

prs = Presentation(input_path)
slide = prs.slides[1]  # the named slide only
if slide.shapes.title:
    slide.shapes.title.text = "第二页新标题"
# Other slides, theme, unused shapes stay. Do not drop slides to rewrite one title.
prs.save(output_path)
```

Do not `prs = Presentation()` then recreate the deck. That drops the teacher's theme and unused pages.

## Rules

- Widescreen 13.333×7.5 unless the teacher asked otherwise.
- Fonts: name the font the teacher's computer has — 宋体 / 黑体 / 楷体 / 仿宋 / 微软雅黑 for Chinese, Calibri / Times New Roman / Arial for Latin. Here they render with installed look-alikes (same style, Regular + Bold), so previews match. Do not name other fonts.
- Blank layout index 6 has no `shapes.title`. Do not write `slide.shapes.title.text` on a blank slide.
- Color blocks: `add_shape` + `fill.solid()` + `RGBColor`. Spec path cannot place these.
- Pictures: embed a real image with `add_picture`. `[image:…]` in body does not embed.
- Edit the named slide in place to keep the existing theme and slides.
- Check the saved deck for actual slide content. Zero slides or title-only walls are not done.

## Check

At least one slide with the teacher's title in the file. If they asked for cards / color blocks / full-bleed, the deck must not be a three-bullet stock layout. Wrong → rewrite with the same title.
In the workspace, also render the pages and look at them before you answer (Workspace rules: first, last, pages with tables / pictures; at most 8).
