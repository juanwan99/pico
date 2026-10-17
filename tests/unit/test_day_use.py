"""Thin day-use SYSTEM block — identity + recent titles only."""

from __future__ import annotations

import base64

from pico_orchestrator.day_use import (
    build_day_use_block,
    decode_display_name_header,
    normalize_recent_titles,
    sanitize_display_name,
)
from pico_orchestrator.true_pi.runtime import pico_system_text


def test_sanitize_rejects_school_account_and_edu_fallback() -> None:
    assert sanitize_display_name("学校账号") == ""
    assert sanitize_display_name("edu-aaaaaaaaaaaa") == ""
    assert sanitize_display_name("  孙骏博  ") == "孙骏博"


def test_decode_b64_header() -> None:
    raw = "孙骏博"
    tok = "b64:" + base64.b64encode(raw.encode("utf-8")).decode("ascii")
    assert decode_display_name_header(tok) == "孙骏博"
    assert decode_display_name_header("Alice") == "Alice"
    assert decode_display_name_header("b64:!!!") == ""


def test_normalize_skips_bookkeeping_and_caps() -> None:
    titles = normalize_recent_titles(
        ["回复摘要", "教案.docx", "教案.docx", "校历.md", "a", "b", "c", "d", "e", "f", "g", "h"],
        limit=8,
    )
    assert "回复摘要" not in titles
    assert titles[0] == "教案.docx"
    assert len(titles) == 8


def test_build_day_use_empty_when_nothing() -> None:
    assert build_day_use_block() == ""
    assert build_day_use_block(display_name="", recent_titles=[]) == ""


def test_build_day_use_has_name_and_titles() -> None:
    block = build_day_use_block(
        display_name="孙骏博",
        recent_titles=["教案.docx", "校历.md"],
    )
    assert "孙骏博" in block
    assert "教案.docx" in block
    assert "校历.md" in block
    assert "not a memory store" in block
    assert "Pi official compaction" in block


def test_pico_system_text_appends_day_use() -> None:
    body = pico_system_text(day_use=build_day_use_block(display_name="Alice"))
    assert "Alice" in body
    assert "Day-use context" in body
