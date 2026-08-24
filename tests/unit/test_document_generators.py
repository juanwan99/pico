from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_PATH = (
    ROOT
    / "services"
    / "orchestrator"
    / "pico_orchestrator"
    / "document_generators.py"
)
_SPEC = importlib.util.spec_from_file_location("document_generators", _PATH)
_mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_mod)
build_docx_document = _mod.build_docx_document
build_html_document = _mod.build_html_document
build_pptx_document = _mod.build_pptx_document
build_xlsx_document = _mod.build_xlsx_document
KNOWN_CALC_CELL = _mod.KNOWN_CALC_CELL
MIN_DOCX_BODY_CHARS = _mod.MIN_DOCX_BODY_CHARS
MIN_PPTX_SLIDES = _mod.MIN_PPTX_SLIDES
docx_visible_text = _mod.docx_visible_text
office_shell_reason = _mod.office_shell_reason
pptx_slide_titles = _mod.pptx_slide_titles
require_docx_body = _mod.require_docx_body
require_pptx_body = _mod.require_pptx_body
DOCX_BODY_TOO_SHORT = _mod.DOCX_BODY_TOO_SHORT
PPTX_SLIDES_TOO_FEW = _mod.PPTX_SLIDES_TOO_FEW

# Real 题面 — not generator filler. Must already clear the body floor.
PARENT_NOTICE_BODY = (
    "各位家长：本周五（3月14日）下午两点在教学楼三层三年级二班教室召开本学期家长会，"
    "请准时到场，并带好孩子的期末成绩单、家校联系册和课外阅读记录。签到从一点五十分开始。\n\n"
    "会议内容按顺序进行：先通报本班期中以来的学习与纪律情况，再讲作业习惯与家庭辅导建议，"
    "然后说明下学期课程、值日、校服与收费事项，最后留二十分钟个别交流。"
    "请提前十分钟入场，手机调至静音，中途如需接听请到走廊。\n\n"
    "如有事不能参加，请当天中午十二点前在班级群私信班主任请假并注明由哪位家长代到。"
    "三年级二班班主任。教室路线、签到表与座位图见班级群置顶。"
    "会后请在本周日晚八点前把家庭作业时间安排发给老师，便于下周跟进错题订正。"
    "雨天请走东门电梯，自行车请停在教学楼北侧车棚。"
)
TRAINING_DECK_BODY = (
    "开场：本次教师培训要把课堂常规讲清，让新老师当周就能独立带班。\n\n"
    "---\n\n"
    "中段：三项课堂常规——候课、提问、收本。每项给出示范与反例，当堂演练。\n\n"
    "---\n\n"
    "收尾：下周跟进。教研组长听一节课，填写观察表后当面反馈，并约定第二次听课时间。"
)
PAD_PHRASES = ("一、事项说明", "不是空壳", "打开说明", "本课件不少于三页", "本文档主题")


def test_html_contains_marker_and_csp() -> None:
    marker = "P270_HTML_MARK"
    raw = build_html_document(title="demo.html", marker=marker, body="hello")
    text = raw.decode("utf-8")
    assert marker in text
    assert "Content-Security-Policy" in text
    assert "<script" not in text.lower()
    assert "http://evil" not in text


def test_html_multi_paragraph_body_for_courseware() -> None:
    marker = "MENDEL_HTML_MARK"
    body = "分离定律：一对相对性状。\n\n自由组合：两对独立遗传。"
    raw = build_html_document(title="mendel.html", marker=marker, body=body)
    text = raw.decode("utf-8")
    assert text.count("<p>") >= 3  # marker line + 2 body paragraphs
    assert "分离定律" in text
    assert "自由组合" in text
    assert "<script" not in text.lower()


def test_html_fragment_not_escaped_tag_wall() -> None:
    """#399 R2: fragment markup must stay real tags, not &lt;h2&gt; wall."""
    marker = "FRAG_HTML_MARK"
    body = "<h2>分离定律</h2>\n<p>一对等位基因在形成配子时分离。</p>\n<button type='button'>下一节</button>"
    raw = build_html_document(title="mendel-frag.html", marker=marker, body=body)
    text = raw.decode("utf-8")
    assert "<!DOCTYPE html>" in text
    assert "<h2>分离定律</h2>" in text
    assert "<button" in text.lower()
    assert "&lt;h2" not in text
    assert "&lt;button" not in text
    assert marker in text
    assert "script-src 'unsafe-inline'" in text


def test_html_full_document_body_not_source_wall() -> None:
    """H3 human-lens: full HTML page body must stay interactive, not escaped prose."""
    marker = "POMO_UI_MARK"
    body = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><title>t</title></head>
<body>
  <button id="start" type="button">开始</button>
  <button id="pause" type="button">暂停</button>
  <button id="reset" type="button">重置</button>
  <script>
    document.getElementById('start').onclick = function () {};
  </script>
</body></html>"""
    raw = build_html_document(title="timer.html", marker=marker, body=body)
    text = raw.decode("utf-8")
    assert "<button" in text.lower()
    assert "开始" in text
    # Must NOT escape the whole document into visible source wall.
    assert "&lt;button" not in text
    assert "&lt;script" not in text
    assert marker in text
    assert "script-src 'unsafe-inline'" in text
    # Remote scripts stripped.
    remote = build_html_document(
        title="x.html",
        marker="R1",
        body='<!DOCTYPE html><html><body><script src="https://evil.example/x.js"></script><button>ok</button></body></html>',
    ).decode("utf-8")
    assert "evil.example" not in remote


def test_prompt_fixtures_meet_floor_without_padding() -> None:
    assert _mod._visible_len(PARENT_NOTICE_BODY) >= MIN_DOCX_BODY_CHARS
    assert len(_mod._split_blocks(TRAINING_DECK_BODY)) >= MIN_PPTX_SLIDES


def test_docx_is_real_ooxml_zip() -> None:
    marker = "P270_DOCX_MARK"
    raw = build_docx_document(title="lesson.docx", marker=marker, body=PARENT_NOTICE_BODY)
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        assert "word/styles.xml" in names
        doc = zf.read("word/document.xml").decode("utf-8")
        assert marker in doc
    text = docx_visible_text(raw)
    assert marker in text
    assert "本周五" in text
    assert _mod._visible_len(text) >= MIN_DOCX_BODY_CHARS
    assert office_shell_reason(raw, ".docx") is None
    for phrase in PAD_PHRASES:
        assert phrase not in text


def test_xlsx_is_real_ooxml_with_known_cell() -> None:
    marker = "P270_XLSX_MARK"
    raw = build_xlsx_document(title="scores.xlsx", marker=marker, body=KNOWN_CALC_CELL)
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert KNOWN_CALC_CELL in sheet
        assert marker in sheet


def test_pptx_is_real_ooxml_with_slide() -> None:
    marker = "P270_PPTX_MARK"
    raw = build_pptx_document(title="slides.pptx", marker=marker, body=TRAINING_DECK_BODY)
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "ppt/presentation.xml" in names
        assert "ppt/slides/slide1.xml" in names
        assert "ppt/slides/slide2.xml" in names
        assert "ppt/slides/slide3.xml" in names
        slide = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert marker in slide
    titles = pptx_slide_titles(raw)
    assert len(titles) >= MIN_PPTX_SLIDES
    assert sum(1 for t in titles if t.strip()) >= MIN_PPTX_SLIDES
    assert office_shell_reason(raw, ".pptx") is None
    blob = " ".join(titles)
    assert "本课件不少于三页" not in blob


def test_docx_keeps_prompt_body_and_rejects_thin_zip() -> None:
    marker = "PARENT_MEETING"
    raw = build_docx_document(title="家长会通知.docx", marker=marker, body=PARENT_NOTICE_BODY)
    text = docx_visible_text(raw)
    assert "本周五（3月14日）下午两点" in text
    assert "期末成绩单" in text
    assert marker in text
    assert office_shell_reason(raw, ".docx") is None
    for phrase in PAD_PHRASES:
        assert phrase not in text

    thin = _thin_docx_zip("空壳", "MARK", "一行")
    assert office_shell_reason(thin, ".docx")


def test_short_body_is_not_padded_and_generate_fails() -> None:
    raw = build_docx_document(title="x.docx", marker="MARK", body="一行通知")
    text = docx_visible_text(raw)
    assert "一行通知" in text
    for phrase in PAD_PHRASES:
        assert phrase not in text
    assert office_shell_reason(raw, ".docx")
    with pytest.raises(ValueError, match="正文过短"):
        require_docx_body("一行通知")
    with pytest.raises(ValueError, match="不足三页"):
        require_pptx_body("只有一页")
    require_docx_body(PARENT_NOTICE_BODY)
    require_pptx_body(TRAINING_DECK_BODY)


def test_pptx_three_titled_slides_from_sections() -> None:
    body = "开场：培训目标\n\n---\n\n中段：三项课堂常规\n\n---\n\n收尾：下周跟进"
    raw = build_pptx_document(title="教师培训.pptx", marker="TRAIN3", body=body)
    titles = pptx_slide_titles(raw)
    assert len(titles) >= 3
    blob = " ".join(titles)
    assert "培训" in blob or "开场" in blob or "教师" in blob
    assert "本课件不少于三页" not in blob
    assert "说明" not in titles


def _thin_docx_zip(title: str, marker: str, body: str) -> bytes:
    from xml.sax.saxutils import escape

    heading = escape(title)
    paragraph = escape(body)
    marker_xml = escape(marker)
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{heading}</w:t></w:r></w:p>
    <w:p><w:r><w:t>标记：{marker_xml}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        zf.writestr("word/document.xml", document)
    return buf.getvalue()
