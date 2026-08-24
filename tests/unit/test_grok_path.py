"""T-GROK-PATH: prompt() = teacher original; no auto delivery weld."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import SubprocessTransport
from pico_orchestrator.true_pi.runtime import _compose_prompt, pico_system_text

NOTICE_WHAT = (
    "关于开展2026年秋季教师岗位培训的通知\n"
    "各科室、各位老师：\n"
    "根据学校工作安排，定于2026年9月5日在报告厅举办秋季教师岗位培训。"
    "请携带笔记本准时参加。\n"
    "这是什么"
)


def test_compose_prompt_user_is_teacher_original() -> None:
    teacher = NOTICE_WHAT
    text = _compose_prompt(
        prompt=teacher,
        skill="use generate_docx_document and write a Word file now",
        min_arts=1,
        history=[
            {"role": "user", "content": "上一轮请做成 Word"},
            {"role": "assistant", "content": "已交培训通知.docx"},
        ],
        allowed_tools=["generate_docx_document", "kb_search"],
        system_prompt="You are Pico true-Pi harness",
    )
    assert text == teacher
    assert "Landing requirement" not in text
    assert "Skill instruction" not in text
    assert "Recent conversation" not in text
    assert "User request" not in text
    assert "generate_docx_document" not in text


def test_notice_what_is_this_does_not_force_delivery() -> None:
    from app.openai_compat import (
        _caps_with_landing_min,
        _resolve_skill_for_prompt,
        _this_round_delivery_plan,
    )

    plan = _this_round_delivery_plan(NOTICE_WHAT)
    assert plan.force_agent is False
    assert plan.min_artifacts == 0

    skill, routed = _resolve_skill_for_prompt(NOTICE_WHAT, None, history=None)
    assert skill is None
    assert routed.force_agent is False
    assert routed.min_artifacts == 0

    caps = _caps_with_landing_min(
        RunCaps(),
        routed,
        {"name": "skill.deliverable", "tools": ["generate_docx_document"]},
    )
    assert caps.min_artifacts == 0


def test_named_word_sets_post_run_min_without_auto_skill() -> None:
    from app.openai_compat import _resolve_skill_for_prompt

    ask = "把上面的培训通知做成可下载 Word"
    skill, plan = _resolve_skill_for_prompt(ask, None, history=None)
    assert skill is None
    assert plan.min_artifacts >= 1


def test_insult_does_not_inherit_prior_word_landing() -> None:
    from app.openai_compat import _sticky_delivery_plan

    history = [
        {"role": "user", "content": "做成可下载 Word，培训通知.docx"},
        {"role": "assistant", "content": "已生成培训通知.docx"},
    ]
    plan = _sticky_delivery_plan("你是煞笔", history)
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_system_md_is_system_not_teacher(tmp_path: Path) -> None:
    body = pico_system_text()
    assert "This block is **SYSTEM**" in body
    assert "这是什么" in body
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
    assert "This block is **SYSTEM**" in written
    assert written == project
    assert NOTICE_WHAT not in written


def test_system_md_does_not_force_kb_on_notice_words() -> None:
    body = pico_system_text()
    assert "must** call `kb_search` first" not in body
    assert "Do not `kb_search` just because the paste looks like" in body
