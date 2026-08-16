"""T-SHELL-AI-PROPOSE-JSON: sidebar marker vs workbench delivery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.delivery_policy import analyze_delivery
from pico_orchestrator.edu_sidebar import JSON_ONLY_OUTPUT, is_json_only_propose


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


def test_workbench_write_plan_still_delivery() -> None:
    plan = analyze_delivery("请写一份可下载的活动方案.md，用工具落盘")
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1


def test_sidebar_json_without_bypass_still_false_positive() -> None:
    # Documents why openai_compat must short-circuit before analyze_delivery.
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
    leaked = analyze_delivery(body)
    assert leaked.force_agent is True
    assert is_json_only_propose(body) is True
