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
    """T-GROK-PATH: prior-turn HTML ask must not stick onto a short reply."""
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
    reply = "Web 单页就好，积分用连续天数，开始做吧。"
    plan = _sticky_delivery_plan(reply, history)
    assert plan.force_agent is False
    assert plan.min_artifacts == 0

    skill, plan2 = _resolve_skill_for_prompt(reply, None, history=history)
    assert plan2.force_agent is False
    assert plan2.min_artifacts == 0
    assert skill is None


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
    from app.openai_compat import _this_round_delivery_plan

    plan = _this_round_delivery_plan("你是什么模型")
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
    prompt = "请做成可下载 Word，notes.docx，本地打开能用。"
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


@pytest.mark.asyncio
async def test_fail_closed_status_event_carries_user_message(
    tmp_path, monkeypatch
) -> None:
    """#404: fail-closed run.status event exposes user_message so the timeline
    shows the real reason instead of the generic retry fallback."""
    from app import db as db_mod
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run
    from app.settings import get_settings

    db_path = tmp_path / "fail-closed-um.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    task_id = new_id()
    run_id = new_id()
    prompt = "请做成可下载 Word，notes.docx，本地打开能用。"
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
        assert run.error
        status_events = (
            await session.execute(
                select(EventRow).where(
                    EventRow.run_id == run_id,
                    EventRow.type == "run.status",
                )
            )
        ).scalars().all()
        failed_events = [
            e for e in status_events if e.payload and e.payload.get("status") == "failed"
        ]
        assert failed_events, "expected a failed run.status event"
        for event in failed_events:
            assert event.payload.get("user_message") == run.error
            assert event.payload.get("user_message")  # non-empty


@pytest.mark.asyncio
async def test_apply_delivery_gate_min_artifacts_fail_closed(
    tmp_path, monkeypatch
) -> None:
    """Gate fails closed on a chat-only file claim with zero artifacts."""
    from app import db as db_mod
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate
    from app.settings import get_settings

    db_path = tmp_path / "gate-min.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    prompt = (
        "请分别交付 3 个独立 HTML 文件：复盘.html 整改清单.html 执行通知.html。"
        "材料：本季度新签客户18家但续费率降到71%。"
    )
    task_id = new_id()
    run_id = new_id()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-gate-min",
                title="cell",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="succeeded",
                prompt=prompt,
                model="pico-agent",
                token_usage_json=json.dumps(
                    {
                        "skill_snapshot": {
                            "name": "skill.engineering_delivery",
                            "tools": ["generate_html_document"],
                        }
                    }
                ),
            )
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        await apply_delivery_gate(
            session,
            run,
            final_text="文件已生成，请下载。",
            user_prompt=prompt,
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error and "声称已交文件" in run.error
        failed_events = [
            e
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "run.status",
                    )
                )
            ).scalars()
            if e.payload and e.payload.get("status") == "failed"
        ]
        assert failed_events
        event = failed_events[-1]
        assert event.payload.get("reason") == "deliverable_missing_artifact"
        assert event.payload.get("user_message") == run.error
        summary = [
            e
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "delivery.summary",
                    )
                )
            ).scalars()
        ]
        assert summary, "expected delivery.summary event on the gate path"


@pytest.mark.asyncio
async def test_execute_run_applies_delivery_gate(tmp_path, monkeypatch) -> None:
    """Retry / REST path must apply the same chat-only-claim fail-closed gate."""
    from types import SimpleNamespace

    from app import db as db_mod
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.run_service import _execute_run
    from app.settings import get_settings
    from pico_orchestrator import runtime as pico_runtime
    from pico_orchestrator.run_types import RunResult

    db_path = tmp_path / "retry-gate.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    prompt = (
        "请分别交付 3 个独立 HTML 文件：复盘.html 整改清单.html 执行通知.html。"
        "材料：本季度新签客户18家但续费率降到71%。完成后只用人话说明。"
    )
    task_id = new_id()
    run_id = new_id()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-retry",
                title="cell",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="queued",
                prompt=prompt,
                model="",
                token_usage_json=json.dumps(
                    {
                        "skill_snapshot": {
                            "name": "skill.engineering_delivery",
                            "tools": ["generate_html_document"],
                        }
                    }
                ),
            )
        )
        await session.commit()

    async def fake_runtime(**kwargs):
        return RunResult(
            status="succeeded",
            final_text="文件已生成，请下载。",
        )

    monkeypatch.setattr(pico_runtime, "run_agent_runtime", fake_runtime)

    principal = SimpleNamespace(school_id="school-a", membership_id="member-retry")
    await _execute_run(run_id, principal)

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed", "retry path must fail closed on a file claim with no file"
        assert run.error and "声称已交文件" in run.error
        failed_events = [
            e
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "run.status",
                    )
                )
            ).scalars()
            if e.payload and e.payload.get("status") == "failed"
        ]
        assert any(
            e.payload.get("reason") == "deliverable_missing_artifact"
            and e.payload.get("user_message") == run.error
            for e in failed_events
        )
        summary = [
            e
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "delivery.summary",
                    )
                )
            ).scalars()
        ]
        assert summary, "retry path must emit delivery.summary like the interactive path"
