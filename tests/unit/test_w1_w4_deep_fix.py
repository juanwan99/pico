"""T-FIX-W1-W4-DEEP: clarification no false-fail + sticky agent + structure min."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def test_sticky_delivery_continuation_forces_agent() -> None:
    """A2: same-session short answer after delivery ask stays force_agent + min≥1."""
    from app.openai_compat import _resolve_skill_for_prompt, _sticky_delivery_plan

    history = [
        {
            "role": "user",
            "content": (
                "请做一个可本地打开的单页 HTML 习惯追踪器，浏览器 file 打开可用，"
                "要有打卡与积分。生成可下载 html 文件。"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "开始之前我想确认两点：\n"
                "1）只要 Web 单页还是也要说明文档？\n"
                "2）积分规则用简单连续天数即可吗？\n"
                "请回复后我再写入文件。"
            ),
        },
    ]
    # Short clarification answer — alone would look like chat.
    reply = "Web 单页就好，积分用连续天数，开始做吧。"
    plan = _sticky_delivery_plan(reply, history)
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1

    skill, plan2 = _resolve_skill_for_prompt(reply, None, history=history)
    assert plan2.force_agent is True
    assert plan2.min_artifacts >= 1
    assert skill is not None
    assert skill.get("tools")  # pico-agent path


def test_sticky_does_not_force_pure_casual() -> None:
    """C1: 闲聊短答不误强制 agent。"""
    from app.openai_compat import _sticky_delivery_plan

    history = [
        {
            "role": "user",
            "content": "请生成一份可下载 Markdown 纪要 visit-notes.md。",
        },
        {"role": "assistant", "content": "已生成 visit-notes.md，可下载。"},
    ]
    plan = _sticky_delivery_plan("谢谢", history)
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_short_chat_still_not_forced() -> None:
    from pico_orchestrator.delivery_policy import analyze_delivery

    plan = analyze_delivery("你是什么模型")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


@pytest.mark.asyncio
async def test_finalize_clarification_not_false_fail(tmp_path, monkeypatch) -> None:
    """A1/A4: clarification turn with delivery skill must not deliverable_missing fail."""
    from app import db as db_mod
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run
    from app.settings import get_settings

    db_path = tmp_path / "clarify.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    task_id = new_id()
    run_id = new_id()
    prompt = (
        "请做一个可本地打开的单页 HTML 前端，浏览器打开可用，生成可下载 html 文件。"
    )
    clarify = (
        "开始之前我想先确认两点：\n"
        "1）你更希望单页还是多页布局？\n"
        "2）是否需要本地存储进度？\n"
        "请回复后我再落盘文件。"
    )
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-clarify",
                title="clarify-turn",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="pico-agent",
                token_usage_json=json.dumps(
                    {
                        "skill_snapshot": {
                            "name": "skill.engineering_delivery",
                            "tools": ["workspace_write_file", "generate_html_document"],
                        }
                    }
                ),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text=clarify,
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert not run.error
        reasons = [
            e.payload.get("reason")
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "run.status",
                    )
                )
            ).scalars()
            if e.payload
        ]
        assert "deliverable_missing_artifact" not in reasons


@pytest.mark.asyncio
async def test_finalize_chat_only_claim_still_fails(tmp_path, monkeypatch) -> None:
    """C1 / #375: chat-only delivery claim still fail-closed."""
    from app import db as db_mod
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run
    from app.settings import get_settings

    db_path = tmp_path / "chat-only.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    task_id = new_id()
    run_id = new_id()
    prompt = "请整理成一份可下载的 Markdown 文件 notes.md，本地打开能用。"
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-claim",
                title="chat-claim",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="pico-agent",
                token_usage_json=json.dumps(
                    {
                        "skill_snapshot": {
                            "name": "skill.engineering_delivery",
                            "tools": ["workspace_write_file"],
                        }
                    }
                ),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="文件 notes.md 已生成，请下载。",
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed"
        reasons = [
            e.payload.get("reason")
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "run.status",
                    )
                )
            ).scalars()
            if e.payload
        ]
        assert "deliverable_missing_artifact" in reasons
