"""#850: restating files already on this chat is not fake-green."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


@pytest.mark.asyncio
async def test_delivery_gate_skips_fail_when_conversation_already_has_files(
    tmp_path, monkeypatch
) -> None:
    from app import db as db_mod
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate
    from app.settings import get_settings

    db_path = tmp_path / "gate-prior.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    prior_task = new_id()
    prior_run = new_id()
    follow_task = new_id()
    follow_run = new_id()
    cid = "convo-850-keep"
    html = b"<html><body>ok</body></html>"
    async with factory() as session:
        session.add(
            TaskRow(
                id=prior_task,
                school_id="school-a",
                membership_id="member-prior",
                title="first",
                conversation_id=cid,
            )
        )
        session.add(
            RunRow(
                id=prior_run,
                task_id=prior_task,
                status="succeeded",
                prompt="先出图片模式课件",
                model="pico-fast",
            )
        )
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=prior_task,
                run_id=prior_run,
                kind="html",
                title="春天来了.html",
                inline=html.decode(),
                content_encoding="utf8",
                byte_size=len(html),
            )
        )
        session.add(
            TaskRow(
                id=follow_task,
                school_id="school-a",
                membership_id="member-prior",
                title="做完了吗",
                conversation_id=cid,
            )
        )
        session.add(
            RunRow(
                id=follow_run,
                task_id=follow_task,
                status="succeeded",
                prompt="做完了吗",
                model="pico-fast",
            )
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, follow_run)
        assert run is not None
        await apply_delivery_gate(
            session,
            run,
            final_text="做完了，两份文件均已生成：春天来了.html 请在结果区下载。",
            user_prompt="做完了吗",
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, follow_run)
        assert run is not None
        assert run.status == "succeeded"
        assert run.error is None


@pytest.mark.asyncio
async def test_delivery_gate_still_fails_when_conversation_has_no_files(
    tmp_path, monkeypatch
) -> None:
    from app import db as db_mod
    from app.db import RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate
    from app.settings import get_settings

    db_path = tmp_path / "gate-empty.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    task_id = new_id()
    run_id = new_id()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-empty",
                title="claim",
                conversation_id="convo-empty",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="succeeded",
                prompt="做个网页",
                model="pico-fast",
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
            user_prompt="做个网页",
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error and "声称已交文件" in run.error
