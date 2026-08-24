"""T-GROK-PATH: prompt() = teacher original; no scene if; no prompt word-list gate."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.delivery_policy import looks_like_delivery_claim
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import SubprocessTransport
from pico_orchestrator.true_pi.runtime import _compose_prompt, pico_system_text

TEACHER = "hello — please just tell me what 17 plus 25 is."


def test_compose_prompt_user_is_teacher_original() -> None:
    text = _compose_prompt(
        prompt=TEACHER,
        skill="use generate_docx_document and write a Word file now",
        min_arts=1,
        history=[
            {"role": "user", "content": "上一轮请做成 Word"},
            {"role": "assistant", "content": "已交培训通知.docx"},
        ],
        allowed_tools=["generate_docx_document", "kb_search"],
        system_prompt="You are Pico true-Pi harness",
    )
    assert text == TEACHER
    assert "Landing requirement" not in text
    assert "Skill instruction" not in text
    assert "Recent conversation" not in text
    assert "User request" not in text
    assert "generate_docx_document" not in text


def test_routing_never_sets_min_or_auto_skill_from_prompt_words() -> None:
    from app.openai_compat import (
        _caps_with_landing_min,
        _resolve_skill_for_prompt,
        _this_round_delivery_plan,
    )

    for prompt in (
        TEACHER,
        "做成可下载 Word",
        "请生成一份 PPT",
        "你好",
    ):
        plan = _this_round_delivery_plan(prompt)
        assert plan.force_agent is False
        assert plan.min_artifacts == 0
        skill, routed = _resolve_skill_for_prompt(prompt, None, history=None)
        assert skill is None
        assert routed.min_artifacts == 0
        caps = _caps_with_landing_min(
            RunCaps(),
            routed,
            {"name": "skill.deliverable", "tools": ["generate_docx_document"]},
        )
        assert caps.min_artifacts == 0


def test_sticky_does_not_inherit_prior_landing() -> None:
    from app.openai_compat import _sticky_delivery_plan

    history = [
        {"role": "user", "content": "做成可下载 Word"},
        {"role": "assistant", "content": "已生成 a.docx"},
    ]
    plan = _sticky_delivery_plan("ok thanks", history)
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_system_md_is_generic_not_scene_if(tmp_path: Path) -> None:
    body = pico_system_text()
    assert "This block is **SYSTEM**" in body
    assert "Being listed does **not** mean you must call them" in body
    assert "这是什么" not in body
    assert "课件" not in body
    assert "通知" not in body
    assert "Landing requirement" not in body
    t = SubprocessTransport(
        session_dir=tmp_path / "sess",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-sys",
        spawn_cwd=tmp_path / "sess",
        system_prompt_text=body,
    )
    home = t.prepare_agent_home()
    written = (home / "SYSTEM.md").read_text(encoding="utf-8")
    project = (tmp_path / "sess" / ".pi" / "SYSTEM.md").read_text(encoding="utf-8")
    assert written == project
    assert "这是什么" not in written


def test_assistant_claim_detector_is_not_a_user_prompt_table() -> None:
    assert looks_like_delivery_claim("文件 notes.docx 已生成，请下载。") is True
    assert looks_like_delivery_claim("17+25=42") is False
    assert looks_like_delivery_claim("这是一份活动安排的说明。") is False


def test_kimi_user_input_does_not_weld_skill() -> None:
    src = (ROOT / "services" / "orchestrator" / "pico_orchestrator" / "kimi_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "<pico_skill_instruction>" not in src
    assert "del skill_instruction" in src
