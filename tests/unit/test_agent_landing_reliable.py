"""T-AGENT-LANDING-RELIABLE: chat-only must not count as file delivery success."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def test_count_write_tool_successes_only_write_tools() -> None:
    from pico_orchestrator.pi_runtime import count_write_tool_successes

    results = [
        ("workspace_list_files", {"files": []}),
        ("workspace_write_file", {"title": "a.md", "bytes": 12}),
        ("generate_html_document", {"title": "b.html"}),
        ("workspace_write_file", {"error": "nope"}),
    ]
    assert count_write_tool_successes(results) == 2
    assert count_write_tool_successes([]) == 0
    assert count_write_tool_successes(None) == 0


def test_run_caps_min_artifacts_default_zero() -> None:
    from pico_orchestrator.run_types import RunCaps

    assert RunCaps().min_artifacts == 0
    assert RunCaps(min_artifacts=2).min_artifacts == 2


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
async def test_finalize_markdown_delivery_chat_only_fails(tmp_path, monkeypatch) -> None:
    """L3: delivery intent + no file → must not stay succeeded."""
    from app.db import EventRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run

    factory = await _boot_db(tmp_path, monkeypatch, "landing-chat-only.db")
    task_id = new_id()
    run_id = new_id()
    prompt = (
        "请整理成一份可下载的 Markdown 文件（建议 landing-notes.md），"
        "本地打开能用。不要只聊天复述。"
    )
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-land",
                title="landing-chat",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="test-model",
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
        final_text="文件 landing-notes.md 已生成，请下载。",  # chat-only claim
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error is not None
        assert "可下载" in run.error or "落盘" in run.error
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
async def test_finalize_markdown_delivery_with_file_succeeds(
    tmp_path, monkeypatch
) -> None:
    """L3: delivery intent + real file → succeeded."""
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.openai_compat import _finalize_run

    factory = await _boot_db(tmp_path, monkeypatch, "landing-with-file.db")
    task_id = new_id()
    run_id = new_id()
    prompt = (
        "请整理成一份可下载的 Markdown 文件（建议 landing-notes.md），"
        "本地打开能用。"
    )
    body = b"# notes\n\n- [ ] action\n"
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-land2",
                title="landing-ok",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="test-model",
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
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="file",
                title="landing-notes.md",
                inline=body.decode(),
                content_encoding="utf8",
                byte_size=len(body),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="已生成 landing-notes.md，可在结果区下载。",
        task_id=task_id,
        user_prompt=prompt,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert not run.error
