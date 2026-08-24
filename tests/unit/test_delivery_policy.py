"""Thin delivery gates — no prompt-word task guessing."""

from __future__ import annotations

from pathlib import Path

from pico_orchestrator.delivery_policy import (
    count_user_artifacts,
    looks_like_clarification,
    looks_like_delivery_claim,
    no_guess_plan,
    normalize_artifact_title,
)

SERVICES = Path(__file__).resolve().parents[2] / "services"


def test_production_path_has_no_prompt_supervisor() -> None:
    hits: list[str] = []
    for path in SERVICES.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "analyze_delivery" in text or "_wants_deliverable_document" in text:
            hits.append(str(path.relative_to(SERVICES.parent)))
    assert hits == []


def test_no_guess_plan_ignores_delivery_wording() -> None:
    plan = no_guess_plan()
    assert plan.force_agent is False
    assert plan.min_artifacts == 0
    assert plan.instruction == ""
    assert plan.engineering is False
    assert plan.multi_deliverable is False


def test_normalize_extension_typo_mdd() -> None:
    """D4: .mdd → .md."""
    fixed, note = normalize_artifact_title("阶段3_本周行动_v2.mdd")
    assert fixed.endswith(".md")
    assert note is not None
    assert ".mdd" in note


def test_count_user_artifacts_skips_bookkeeping() -> None:
    rows = [
        ("file", "回复摘要", 10),
        ("file", "rules.md", 100),
        ("file", "schedule.md", 100),
        ("file", "rules.md", 100),
        ("table", "工具产物", 50),
    ]
    assert count_user_artifacts(rows) == 2


def test_looks_like_clarification_positive_and_negative() -> None:
    ask = (
        "开始之前我想先确认两点：\n"
        "1）你更希望 Web 单页还是多页？\n"
        "2）要不要积分与连续打卡？\n"
        "请回复后我再落盘可下载文件。"
    )
    assert looks_like_clarification(ask) is True
    claim = "已生成 tracker.html，请在结果区下载打开。"
    assert looks_like_clarification(claim) is False
    chat_only_code = "```file:tracker.html\n<html></html>\n```\n文件已写好。"
    assert looks_like_clarification(chat_only_code) is False


def test_looks_like_delivery_claim_is_assistant_not_user_table() -> None:
    assert looks_like_delivery_claim("文件 notes.docx 已生成，请下载。") is True
    assert looks_like_delivery_claim("17+25=42") is False
    assert looks_like_delivery_claim("这是一份活动安排的说明。") is False
