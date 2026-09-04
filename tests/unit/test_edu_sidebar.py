"""T-SHELL-AI-PROPOSE-JSON: sidebar marker vs workbench delivery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.edu_sidebar import (
    EDU_SIDEBAR_DEFAULT_TOOLS,
    HONEST_MISS_SUMMARY,
    JSON_ONLY_OUTPUT,
    SIDEBAR_WORKBENCH_HINT,
    asked_from_sidebar_prompt,
    edu_sidebar_tool_ceiling,
    honest_miss_json,
    inject_web_hits,
    is_json_only_propose,
    shape_web_hits,
    sidebar_chat_only,
    with_sidebar_workbench_hint,
)


def test_marker_in_json_body_only() -> None:
    asked = "把高中英语周课时改成 5"
    assert is_json_only_propose(asked) is False
    body = json.dumps(
        {"asked": asked, "output": JSON_ONLY_OUTPUT, "affordances": [{"id": "x"}]},
        ensure_ascii=False,
    )
    assert is_json_only_propose(body) is True
    assert is_json_only_propose("请写一份方案包") is False
    assert is_json_only_propose("hello", output_header=JSON_ONLY_OUTPUT) is True
    assert is_json_only_propose("hello", output_header="json") is False
    assert is_json_only_propose("hello", output_header=object()) is False


def test_json_only_does_not_use_fuzzy_chinese() -> None:
    # Workbench wording must not trip the sidebar switch.
    assert is_json_only_propose("改周课时") is False
    assert is_json_only_propose("不要走交付") is False


def test_workbench_write_plan_does_not_guess_route() -> None:
    from app.openai_compat import _this_round_delivery_plan

    plan = _this_round_delivery_plan("请写一份可下载的活动方案.md，用工具落盘")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_sidebar_json_is_chat_only_not_a_word_list_gate() -> None:
    body = json.dumps(
        {
            "asked": "把高中英语周课时改成 5",
            "output": JSON_ONLY_OUTPUT,
            "affordances": [
                {
                    "id": "input:lesson:l1:weekly_lessons",
                    "label": "英语 周课时",
                    "command": "scheduling.lessons.upsert",
                    "params": {"weekly_lessons": 4, "project_id": "p"},
                }
            ],
        },
        ensure_ascii=False,
    )
    assert is_json_only_propose(body) is True


def test_sidebar_web_hits_inject_and_honest_miss() -> None:
    asked = json.dumps({"asked": "今天几号", "output": JSON_ONLY_OUTPUT}, ensure_ascii=False)
    assert asked_from_sidebar_prompt(asked) == "今天几号"
    miss = shape_web_hits({"retrieved": False, "honest_miss": True, "sources": [], "message": "未检索到可用来源"})
    assert miss["retrieved"] is False
    assert miss["honest_miss"] is True
    injected = json.loads(inject_web_hits(asked, miss))
    assert injected["webHits"]["honest_miss"] is True
    dumped = json.loads(honest_miss_json(miss))
    assert dumped["mutations"] == []
    assert "没查到" in dumped["summary"] or "未检索" in dumped["summary"]
    assert HONEST_MISS_SUMMARY
    hit = shape_web_hits(
        {
            "retrieved": True,
            "sources": [{"title": "日历", "url": "https://example.com/d", "snippet": "2026年8月17日"}],
        }
    )
    assert hit["retrieved"] is True
    assert hit["sources"][0]["url"].startswith("https://")
    empty_src = shape_web_hits({"retrieved": True, "sources": []})
    assert empty_src["honest_miss"] is True


def test_sidebar_enters_pi_helpers() -> None:
    assert sidebar_chat_only(edu_sidebar=True, json_only=False) is False
    assert sidebar_chat_only(edu_sidebar=True, json_only=True) is True
    assert edu_sidebar_tool_ceiling(None) is None
    assert edu_sidebar_tool_ceiling([]) is None
    assert edu_sidebar_tool_ceiling(["web_search", "web_fetch"]) is None
    assert "generate_html_document" in EDU_SIDEBAR_DEFAULT_TOOLS
    assert "generate_image" in EDU_SIDEBAR_DEFAULT_TOOLS
    assert "generate_pptx_document" in EDU_SIDEBAR_DEFAULT_TOOLS
    hinted = with_sidebar_workbench_hint("附属，不是用户要求")
    assert SIDEBAR_WORKBENCH_HINT in hinted
    assert "不得调用" not in hinted
    assert "同一套手" in hinted
    assert "inspect_document" in hinted
    assert "工具结果回来后再决定下一手" in hinted
    assert with_sidebar_workbench_hint(hinted) == hinted


def test_sidebar_progress_rides_content() -> None:
    from pico_orchestrator.workbench_progress import sidebar_progress_delta

    assert (
        sidebar_progress_delta(
            "tool.call",
            {"tool": "inspect_document", "step_line": "正在读文档结构"},
        )
        == "正在读文档结构"
    )
    assert (
        sidebar_progress_delta("tool.result", {"tool": "inspect_document", "ok": True})
        == "已读文档结构"
    )
    assert "没读成" in sidebar_progress_delta(
        "tool.result",
        {"tool": "inspect_document", "ok": False, "user_message": "不是真 Excel"},
    )
    assert sidebar_progress_delta("thinking.delta", {"text": "内部"}) == ""
    src = (ROOT / "services" / "api" / "app" / "openai_compat.py").read_text(
        encoding="utf-8"
    )
    assert "sidebar_progress_delta" in src
    assert 'if edu_sidebar:' in src
