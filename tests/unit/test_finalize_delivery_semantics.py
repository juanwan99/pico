"""E4: _finalize_run success semantics — single-unit vs true multi fail-closed.

Must exercise finalize itself (not only delivery_policy heuristics).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


async def _boot_db(tmp_path, monkeypatch, name: str):
    from app import db as db_mod
    from app.db import init_db
    from app.settings import get_settings

    db_path = tmp_path / name
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await init_db()
    return db_mod.session_factory()


@pytest.mark.asyncio
async def test_finalize_single_unit_one_file_not_fail_closed(tmp_path, monkeypatch) -> None:
    """Single-unit prompt + ≥1 user file → succeeded (G1; must not fail-closed)."""
    from app.db import ArtifactRow, EventRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run

    factory = await _boot_db(tmp_path, monkeypatch, "finalize-single.db")
    task_id = new_id()
    run_id = new_id()
    prompt = (
        "请生成一份可离线互动 HTML：城市骑行安全入门，"
        "含三段图文与自测题，浏览器本地打开可用。"
    )
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-e4-single",
                title="single-unit",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="test-model",
            )
        )
        body = b"<html><body>ok</body></html>"
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="html",
                title="riding-safety.html",
                inline=body.decode(),
                content_encoding="utf8",
                byte_size=len(body),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="已生成 riding-safety.html，请下载本地打开。",
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert run.error is None
        summaries = list(
            (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "delivery.summary",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(summaries) == 1
        payload = summaries[0].payload
        assert payload.get("ok") is True
        assert payload.get("artifact_count", 0) >= 1
        assert payload.get("multi_deliverable") is False


@pytest.mark.asyncio
async def test_finalize_true_multi_short_delivery_fail_closed(tmp_path, monkeypatch) -> None:
    """True multi intent + fewer files than min → fail-closed (delivery_min_artifacts)."""
    from app.db import ArtifactRow, EventRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run

    factory = await _boot_db(tmp_path, monkeypatch, "finalize-multi.db")
    task_id = new_id()
    run_id = new_id()
    prompt = (
        "请分别交付 3 个独立 HTML 文件：\n"
        "1) 活动规则说明.html\n"
        "2) 志愿者排班表.html\n"
        "3) 居民通知短讯合集.html\n"
        "禁止合并成一个文件。"
    )
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-e4-multi",
                title="multi-short",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="test-model",
            )
        )
        # Only one user file — short of min ≥3.
        body = b"# rules only\n"
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="file",
                title="rules.md",
                inline=body.decode(),
                content_encoding="utf8",
                byte_size=len(body),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="先交了规则说明。",
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error is not None
        assert "独立文件" in run.error or "多产物" in run.error
        status_events = list(
            (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "run.status",
                    )
                )
            )
            .scalars()
            .all()
        )
        reasons = [e.payload.get("reason") for e in status_events if e.payload]
        assert "delivery_min_artifacts" in reasons


@pytest.mark.asyncio
async def test_finalize_markdown_office_notes_not_office_binary_fail(
    tmp_path, monkeypatch
) -> None:
    """O1: Markdown visit notes with size>0 must succeed (not HTML/Word-only gate)."""
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run

    factory = await _boot_db(tmp_path, monkeypatch, "finalize-md-ok.db")
    task_id = new_id()
    run_id = new_id()
    prompt = (
        "根据以下材料，请整理成一份可下载的「客户拜访纪要」Markdown 文件"
        "（visit-notes.md）。材料含 pdf/docx 提及。单文件即可。"
    )
    body = b"# visit notes\n- [ ] action\n"
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-e4-md",
                title="md-notes",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="test-model",
            )
        )
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="file",
                title="visit-notes.md",
                inline=body.decode(),
                content_encoding="utf8",
                byte_size=len(body),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="已生成 visit-notes.md，请下载。",
        task_id=task_id,
        user_prompt=prompt,
    )
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert run.error is None


@pytest.mark.asyncio
async def test_finalize_true_multi_full_delivery_succeeds(tmp_path, monkeypatch) -> None:
    """True multi + enough independent files → remains succeeded."""
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run

    factory = await _boot_db(tmp_path, monkeypatch, "finalize-multi-ok.db")
    task_id = new_id()
    run_id = new_id()
    prompt = (
        "请分别交付 3 个独立 HTML 文件：\n"
        "1) 活动规则说明.html\n"
        "2) 志愿者排班表.html\n"
        "3) 居民通知短讯合集.html\n"
        "禁止合并成一个文件。"
    )
    titles = ["rules.md", "schedule.md", "notices.md"]
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-e4-multi-ok",
                title="multi-ok",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="test-model",
            )
        )
        for title in titles:
            body = f"# {title}\ncontent\n".encode()
            session.add(
                ArtifactRow(
                    id=new_id(),
                    task_id=task_id,
                    run_id=run_id,
                    kind="file",
                    title=title,
                    inline=body.decode(),
                    content_encoding="utf8",
                    byte_size=len(body),
                )
            )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="三份文件已就绪。",
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert run.error is None
