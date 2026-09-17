from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.kb_chunker import chunk_text, expand_json_fields, expand_pipe_tables


def test_sections_become_parents_and_children_keep_heading() -> None:
    text = (
        "# 一、培训对象\n\n"
        "各县市区本级人工智能讲师团全体成员。\n\n"
        "局直属各学校遴选的骨干教师。\n\n"
        "# 二、培训安排\n\n"
        "2026年7月8日：荷塘区、局直属各学校，地点株洲景炎初级中学。\n"
    )
    chunks = chunk_text(text, title="培训通知.pdf")
    assert [c.heading for c in chunks] == ["一、培训对象", "二、培训安排"]
    assert chunks[0].parent_seq == 0 and chunks[1].parent_seq == 1
    assert "景炎" in chunks[1].text
    assert chunks[1].parent_text.startswith("二、培训安排")


def test_long_paragraph_splits_on_sentence_and_stays_under_limit() -> None:
    para = "".join(f"第{i}句话，内容是一些说明文字。" for i in range(80))
    chunks = chunk_text(para, title="长文", child_max=300)
    assert len(chunks) > 3
    # A trailing sliver may be merged into its predecessor (child_min slack).
    assert all(len(c.text) <= 300 + 120 for c in chunks)
    assert "".join(c.text for c in chunks).replace("\n", "") == para


def test_page_breaks_yield_page_numbers() -> None:
    text = "第一页的内容。\n\x0c\n第二页的内容。\n\x0c\n第三页的内容。"
    chunks = chunk_text(text, title="扫描件.pdf", child_max=12, child_min=1)
    pages = [c.page for c in chunks]
    assert pages == [1, 2, 3]
    assert all("\x0c" not in c.text for c in chunks)


def test_no_page_marker_means_page_is_none() -> None:
    chunks = chunk_text("只有一段。", title="x.docx")
    assert len(chunks) == 1
    assert chunks[0].page is None
    assert chunks[0].parent_text == "只有一段。"


def test_table_splits_one_logical_row_per_child() -> None:
    rows = "\n".join(f"| 学生{i} | {60 + i % 40} | 优 |" for i in range(8))
    chunks = chunk_text("| 姓名 | 分数 | 等级 |\n|---|---|---|\n" + rows, title="成绩.xlsx", child_max=400)
    assert len(chunks) == 8
    assert all("姓名" in c.text for c in chunks)
    only0 = [c for c in chunks if "姓名=学生0" in c.text]
    assert len(only0) == 1
    assert "姓名=学生1" not in only0[0].text


def test_wide_row_stays_in_one_chunk() -> None:
    header = "| " + " | ".join(f"列{i}" for i in range(12)) + " |"
    sep = "|" + "---|" * 12
    row = "| " + " | ".join(f"值{i}" for i in range(12)) + " |"
    chunks = chunk_text(f"{header}\n{sep}\n{row}", title="宽表.csv", child_max=80, child_min=1)
    assert len(chunks) == 1
    assert "列0=值0" in chunks[0].text and "列11=值11" in chunks[0].text


def test_csv_header_rides_with_each_bound_row() -> None:
    text = (
        "仓,件\n"
        "| 东仓,12 | 仓=东仓 | 件=12\n"
        "| 仓=东仓\n"
        "| 件=12\n"
        "| 西仓,3 | 仓=西仓 | 件=3\n"
        "| 仓=西仓\n"
        "| 件=3\n"
    )
    chunks = chunk_text(text, title="库存.csv", child_max=400, child_min=1)
    assert len(chunks) == 2
    east = [c for c in chunks if "仓=东仓" in c.text]
    assert len(east) == 1
    assert "仓,件" in east[0].text
    assert "仓=西仓" not in east[0].text


def test_expand_json_fields_binds_leaf_and_enum_lists() -> None:
    text = expand_json_fields(
        '{"table":"leave","fields":[{"name":"leave_type","enum":["事假","病假"]}]}'
    )
    assert "table=leave" in text
    assert "fields[0].name=leave_type" in text
    assert "fields[0].enum=事假 / 病假" in text
    assert text.startswith("{")


def test_expand_json_fields_leaves_prose_alone() -> None:
    assert expand_json_fields("请假类型写在正文里。") == "请假类型写在正文里。"
    assert expand_json_fields("{not json") == "{not json"


def test_chunk_text_json_document_exposes_field_lines() -> None:
    chunks = chunk_text(
        '{"leave_type":["事假","病假"],"note":"开始时间记 start_at"}',
        title="schema.json",
    )
    blob = "\n".join(c.text for c in chunks)
    assert "leave_type=事假 / 病假" in blob
    assert "note=开始时间记 start_at" in blob


def test_expand_pipe_tables_binds_every_data_row() -> None:
    text = expand_pipe_tables("| 仓 | 件 |\n|---|---|\n| 东仓 | 12 |\n段落。\n")
    assert "仓=东仓" in text and "件=12" in text
    assert "| 仓=东仓" in text.splitlines()
    assert "段落。" in text


def test_code_splits_on_def_not_cjk_period() -> None:
    one = "def one():\n    x = '" + ("句。" * 20) + "'\n    return x\n"
    two = "def two():\n    y = '" + ("段。" * 20) + "'\n    return y\n"
    chunks = chunk_text(one + two, title="mod.py", child_max=80, child_min=1)
    assert any("def one(" in c.text and "def two(" not in c.text for c in chunks)
    assert any("def two(" in c.text and "def one(" not in c.text for c in chunks)


def test_empty_and_cap() -> None:
    assert chunk_text("", title="空") == []
    many = "\n\n".join(f"段落{i}。" * 10 for i in range(1000))
    assert len(chunk_text(many, title="多", max_chunks=50)) == 50
