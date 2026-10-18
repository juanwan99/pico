"""#1334: a turn given no tools makes no file claim — edu server text calls were failed by mistake."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

# Live shape (10-07 枫溪 AI 评分细则, 10-17 #3219 阅卷): text answer, no tools, says 已生成.
RUBRIC = "评分细则已生成如下：\n1. 化学式全对得 2 分；\n2. 配平错扣 1 分。"
REDELIVER = "已重新生成评分细则：第 3 空同义表达给分。"


async def _gate(tmp_path, monkeypatch, *, writers: bool | None, text: str):
    from app import db as db_mod
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate, mark_turn_writers
    from app.settings import get_settings
    from sqlalchemy import select

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'gate.db'}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()
    task_id, run_id = new_id(), new_id()
    async with factory() as session:
        session.add(TaskRow(id=task_id, school_id="school-a", membership_id="m-1334", title="细则"))
        session.add(RunRow(id=run_id, task_id=task_id, status="succeeded", prompt="细则", model="pico-fast"))
        await session.commit()
    if writers is not None:
        mark_turn_writers(writers)
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        await apply_delivery_gate(session, run, final_text=text, user_prompt="细则")
        await session.commit()
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        rows = (await session.execute(
            select(EventRow.payload_json).where(
                EventRow.run_id == run_id, EventRow.type == "delivery.summary"
            )
        )).scalars().all()
        return run, json.loads(rows[0])


@pytest.mark.asyncio
async def test_no_tools_turn_saying_generated_is_not_failed(tmp_path, monkeypatch) -> None:
    run, summary = await _gate(tmp_path, monkeypatch, writers=False, text=RUBRIC)
    assert run.status == "succeeded"
    assert summary["writers_visible"] is False


@pytest.mark.asyncio
async def test_no_tools_turn_saying_regenerated_is_not_failed(tmp_path, monkeypatch) -> None:
    run, _ = await _gate(tmp_path, monkeypatch, writers=False, text=REDELIVER)
    assert run.status == "succeeded"


@pytest.mark.asyncio
async def test_turn_with_tools_still_fails_an_empty_claim(tmp_path, monkeypatch) -> None:
    run, summary = await _gate(tmp_path, monkeypatch, writers=True, text=RUBRIC)
    assert run.status == "failed"
    assert summary["writers_visible"] is True


@pytest.mark.asyncio
async def test_unmarked_turn_keeps_the_old_judgement(tmp_path, monkeypatch) -> None:
    run, summary = await _gate(tmp_path, monkeypatch, writers=None, text=RUBRIC)
    assert run.status == "failed"
    assert summary["writers_visible"] is None


def test_turn_has_tools_rule() -> None:
    from app.openai_compat import _turn_has_tools

    # Direct chat never has tools, whatever the request lists.
    assert not _turn_has_tools(use_direct=True, skill_snapshot=None, request_tools=None)
    # edu server sends tools: [] → Pi turn with nothing visible.
    assert not _turn_has_tools(use_direct=False, skill_snapshot=None, request_tools=[])
    # No list = CORE, which has writer tools.
    assert _turn_has_tools(use_direct=False, skill_snapshot=None, request_tools=None)
    # #1334 ②: judged by writer tools — search only cannot land a file …
    assert not _turn_has_tools(use_direct=False, skill_snapshot=None, request_tools=["web_search"])
    assert _turn_has_tools(
        use_direct=False, skill_snapshot=None, request_tools=["web_search", "sandbox_office_lib"]
    )


def test_box_turn_can_write_with_any_tool(monkeypatch) -> None:
    from app.delivery_gate import turn_writers

    monkeypatch.delenv("PICO_RUNNER_URL", raising=False)
    assert not turn_writers(["web_search"], membership_id="m-1")
    monkeypatch.setenv("PICO_RUNNER_URL", "http://runner:8790")
    # … unless the turn runs in the box, which has Pi's own write / bash.
    assert turn_writers(["web_search"], membership_id="m-1")
    # Toolless stays no even in the box: edu 细则 / JSON calls (#1335's 19 misfires).
    assert not turn_writers([], membership_id="m-1")
