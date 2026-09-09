# PPT craft (python-pptx)

Use when the teacher asked for a real `.pptx`. This is craft, not a scene workflow.
Execute in `sandbox_office_lib` with `kind=pptx`.
To change a deck the teacher already has, pass `artifact_id` and start with `prs = load_deck()` (or `Presentation(INPUT_PATH)`).
The script runs in an isolated container with full Python (Pillow / matplotlib can render a chart PNG into the workdir and `add_picture` it). Empty `Presentation(); save_deck(prs)` fails.
Stock body bullets are not the ceiling. Free geometry uses shapes + RGBColor.

## Run — stock helpers (fine for a simple talk track)

```python
from pptx import Presentation, Inches, Pt, RGBColor

prs = Presentation()
add_title_slide(prs, "封面标题", "副题")
add_content_slide(prs, "要点", ["第一条", "第二条", "第三条"])
save_deck(prs)
```

## Run — free layout (when it must not look like Title-and-Content)

```python
from pptx import Presentation, Inches, Pt, RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor as RGB

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]
slide = prs.slides.add_slide(blank)

bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.1))
bar.fill.solid()
bar.fill.fore_color.rgb = RGB(0x1F, 0x4E, 0x79)
bar.line.fill.background()
title = slide.shapes.add_textbox(Inches(0.6), Inches(0.25), Inches(12), Inches(0.7))
tf = title.text_frame
tf.clear()
run = tf.paragraphs[0].add_run()
run.text = "本周经营风险与下周动作"
run.font.size = Pt(28)
run.font.bold = True
run.font.color.rgb = RGB(0xFF, 0xFF, 0xFF)

card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.6), Inches(5.8), Inches(4.8))
card.fill.solid()
card.fill.fore_color.rgb = RGB(0xF2, 0xF2, 0xF2)
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

if IMAGE_PATHS:
    slide.shapes.add_picture(IMAGE_PATHS[0], Inches(7.0), Inches(1.6), width=Inches(5.4))

save_deck(prs)
```

## Rules

- Widescreen 13.333×7.5 unless the teacher asked otherwise.
- Blank layout index 6 has no `shapes.title`. Do not write `slide.shapes.title.text` on a blank slide.
- Color blocks: `add_shape` + `fill.solid()` + `RGBColor`. Spec path cannot place these.
- Helpers `add_title_slide` / `add_content_slide` / `add_table` are injected. Aliases: `image=`, `prs=`, `IMAGE_PATHS[0]`.
- Pictures: `IMAGE_PATHS` from `image_artifact_ids`. `[image:…]` in body does not embed.
- Same title replaces the file the teacher opens.
- After save, read `observation.outline`. Zero slides or title-only walls are not done.

## Check

At least one slide with the teacher's title in the file. If they asked for cards / color blocks / full-bleed, the deck must not be a three-bullet stock layout. Wrong → rewrite with the same title.
