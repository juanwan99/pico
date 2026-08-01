"""M2 B2-B4 regressions: conversation binding, finalize parity, artifacts."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import issue_test_token
from app.db import (
    ArtifactRow,
    ChangeProposalRow,
    EventRow,
    RunRow,
    TaskRow,
    init_db,
    new_id,
    session_factory,
)
from app.main import app
from app.openai_compat import (
    ChatCompletionRequest,
    ChatMessage,
    _finalize_run,
    chat_completions,
)
from app.settings import Settings, get_settings
from pico_orchestrator.runner import RunResult


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "m2-b2-b4.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")

    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None

    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, membership_id: str) -> dict[str, str]:
    response = client.post(
        "/v1/dev/token",
        json={"school_id": "school-a", "membership_id": membership_id},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _stub_provider(monkeypatch, text: str) -> None:
    async def fake_stream_chat(*_args, **_kwargs) -> AsyncIterator[str]:
        midpoint = max(1, len(text) // 2)
        yield text[:midpoint]
        yield text[midpoint:]

    monkeypatch.setattr("pico_orchestrator.provider.stream_chat", fake_stream_chat)


def _stub_agent(monkeypatch, result: RunResult) -> None:
    async def fake_run_agent_loop(*, emit, **_kwargs) -> RunResult:
        await emit("run.status", {"status": "running"})
        await emit("run.status", {"status": result.status})
        return result

    monkeypatch.setattr("pico_orchestrator.runner.run_agent_loop", fake_run_agent_loop)


def _complete(
    client: TestClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    stream: bool,
) -> str:
    response = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "test-direct-model",
            "stream": stream,
            "messages": [
                {
                    "role": "user",
                    "content": f"【Pico-Convo:{conversation_id}】\n创建 report.csv",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    if stream:
        assert "data: [DONE]" in response.text
    else:
        assert response.json()["choices"][0]["finish_reason"] == "stop"

    tasks = client.get(
        "/v1/tasks",
        headers=headers,
        params={"conversation_id": conversation_id},
    )
    assert tasks.status_code == 200, tasks.text
    rows = tasks.json()["tasks"]
    assert len(rows) == 1
    return rows[0]["id"]


def test_pending_conversation_rebind_is_membership_scoped(client, monkeypatch) -> None:
    _stub_provider(monkeypatch, "ok")
    member_a = _headers(client, "member-a")
    member_b = _headers(client, "member-b")
    pending_id = "pending_shared_client_id"
    real_id = "librechat_real_conversation"

    task_a = _complete(
        client,
        member_a,
        conversation_id=pending_id,
        stream=False,
    )
    task_b = _complete(
        client,
        member_b,
        conversation_id=pending_id,
        stream=False,
    )

    rebound = client.post(
        "/v1/tasks/rebind-conversation",
        headers=member_a,
        json={
            "from_conversation_id": pending_id,
            "to_conversation_id": real_id,
        },
    )
    assert rebound.status_code == 200, rebound.text
    assert rebound.json() == {
        "updated": 1,
        "from": pending_id,
        "to": real_id,
    }

    a_real = client.get("/v1/tasks", headers=member_a, params={"conversation_id": real_id})
    a_pending = client.get(
        "/v1/tasks",
        headers=member_a,
        params={"conversation_id": pending_id},
    )
    b_real = client.get("/v1/tasks", headers=member_b, params={"conversation_id": real_id})
    b_pending = client.get(
        "/v1/tasks",
        headers=member_b,
        params={"conversation_id": pending_id},
    )

    assert [task["id"] for task in a_real.json()["tasks"]] == [task_a]
    assert a_pending.json()["tasks"] == []
    assert b_real.json()["tasks"] == []
    assert [task["id"] for task in b_pending.json()["tasks"]] == [task_b]

    repeated = client.post(
        "/v1/tasks/rebind-conversation",
        headers=member_a,
        json={
            "from_conversation_id": pending_id,
            "to_conversation_id": real_id,
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["updated"] == 0


def test_conversation_filter_applies_before_account_task_limit(client) -> None:
    owner = _headers(client, "member-history-limit")
    outsider = _headers(client, "member-history-outsider")
    target_id = new_id()
    target_conversation_id = "conversation-older-than-account-window"

    async def seed_tasks() -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        factory = session_factory()
        async with factory() as session:
            session.add(
                TaskRow(
                    id=target_id,
                    school_id="school-a",
                    membership_id="member-history-limit",
                    title="需要从历史找回的任务",
                    conversation_id=target_conversation_id,
                    created_at=base,
                )
            )
            session.add_all(
                [
                    TaskRow(
                        id=new_id(),
                        school_id="school-a",
                        membership_id="member-history-limit",
                        title=f"更新任务 {index}",
                        conversation_id=f"newer-conversation-{index}",
                        created_at=base + timedelta(minutes=index + 1),
                    )
                    for index in range(55)
                ]
            )
            await session.commit()

    client.portal.call(seed_tasks)

    account_window = client.get("/v1/tasks", headers=owner)
    assert account_window.status_code == 200, account_window.text
    account_rows = account_window.json()["tasks"]
    assert len(account_rows) == 50
    assert target_id not in {task["id"] for task in account_rows}

    historical = client.get(
        "/v1/tasks",
        headers=owner,
        params={"conversation_id": target_conversation_id},
    )
    assert historical.status_code == 200, historical.text
    assert [task["id"] for task in historical.json()["tasks"]] == [target_id]

    hidden = client.get(
        "/v1/tasks",
        headers=outsider,
        params={"conversation_id": target_conversation_id},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["tasks"] == []


def test_proxy_membership_header_is_required_and_cannot_conflict(client) -> None:
    body = {
        "model": "test-direct-model",
        "stream": False,
        "messages": [{"role": "user", "content": "【Pico-User:forged】hello"}],
    }
    missing = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer pico-dev"},
        json=body,
    )
    assert missing.status_code == 403

    conflict = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer pico-dev",
            "X-Pico-Membership-Id": "real-member",
        },
        json=body,
    )
    assert conflict.status_code == 403


def test_non_stream_agent_reuses_one_run_and_preserves_failure(client, monkeypatch) -> None:
    _stub_agent(
        monkeypatch,
        RunResult(status="failed", final_text="", error="provider unavailable"),
    )
    owner = _headers(client, "member-agent-failure")
    conversation_id = "conversation-agent-failure"

    response = client.post(
        "/v1/chat/completions",
        headers=owner,
        json={
            "model": "pico-agent",
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": f"【Pico-Convo:{conversation_id}】\nhello",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"] == "provider unavailable"

    tasks = client.get(
        "/v1/tasks",
        headers=owner,
        params={"conversation_id": conversation_id},
    )
    rows = tasks.json()["tasks"]
    assert len(rows) == 1

    runs = client.get(f"/v1/tasks/{rows[0]['id']}/runs", headers=owner)
    run_rows = runs.json()["runs"]
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "failed"
    assert run_rows[0]["error"] == "provider unavailable"


def test_skill_write_s7_records_snapshot_and_existing_change_path(client, monkeypatch) -> None:
    _stub_agent(
        monkeypatch,
        RunResult(status="succeeded", final_text="建议把一班名称改为星辰一班。"),
    )
    owner = _headers(client, "member-skill-write-s7")
    conversation_id = "conversation-skill-write-s7"

    response = client.post(
        "/v1/chat/completions",
        headers=owner,
        json={
            "model": "test-direct-model",
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "【Pico-Convo:conversation-skill-write-s7】\n"
                        "【Pico-Skill:skill.write_s7】\n"
                        "提出一个班级改名申请"
                    ),
                }
            ],
        },
    )
    assert response.status_code == 200, response.text

    tasks = client.get(
        "/v1/tasks",
        headers=owner,
        params={"conversation_id": conversation_id},
    )
    task_id = tasks.json()["tasks"][0]["id"]
    runs = client.get(f"/v1/tasks/{task_id}/runs", headers=owner)
    run = runs.json()["runs"][0]
    snapshot = run["token_usage"]["skill_snapshot"]
    assert snapshot["id"] == "skill-write-s7"
    assert snapshot["tools"] == ["pico_propose_change"]
    assert snapshot["requires_s7"] is True

    changes = client.get(
        "/v1/changes",
        headers=owner,
        params={"task_id": task_id, "status": "proposed"},
    )
    assert changes.status_code == 200, changes.text
    rows = changes.json()["changes"]
    assert len(rows) == 1
    assert rows[0]["run_id"] == run["id"]
    assert rows[0]["payload"]["skill_snapshot"]["id"] == "skill-write-s7"

    events = client.get(f"/v1/runs/{run['id']}/events", headers=owner)
    event_types = [event["type"] for event in events.json()["events"]]
    assert "skill.snapshot" in event_types
    assert "change.proposed" in event_types


@pytest.mark.asyncio
async def test_direct_stream_aclose_finalizes_run_as_cancelled(tmp_path, monkeypatch) -> None:
    db = tmp_path / "stream-aclose.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")

    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()
    settings = Settings()

    async def slow_stream(*_args, **_kwargs) -> AsyncIterator[str]:
        yield "partial"
        await asyncio.Event().wait()

    monkeypatch.setattr("pico_orchestrator.provider.stream_chat", slow_stream)
    token = issue_test_token(
        school_id="school-a",
        membership_id="member-stream-close",
        settings=settings,
    )
    response = await chat_completions(
        ChatCompletionRequest(
            model="test-direct-model",
            stream=True,
            messages=[
                ChatMessage(
                    role="user",
                    content="【Pico-Convo:conversation-stream-close】hello",
                )
            ],
        ),
        authorization=f"Bearer {token}",
        x_conversation_id=None,
        x_workspace_id=None,
        x_pico_membership_id=None,
        settings=settings,
    )

    iterator = response.body_iterator
    await anext(iterator)
    partial = await anext(iterator)
    assert b"partial" in partial
    await iterator.aclose()

    factory = session_factory()
    async with factory() as session:
        from sqlalchemy import select

        task = (
            await session.execute(
                select(TaskRow).where(
                    TaskRow.conversation_id == "conversation-stream-close"
                )
            )
        ).scalar_one()
        run = (
            await session.execute(select(RunRow).where(RunRow.task_id == task.id))
        ).scalar_one()
        assert run.status == "cancelled"
        assert run.error == "stream disconnected"


@pytest.mark.asyncio
async def test_agent_stream_polls_ledger_cancel_request(tmp_path, monkeypatch) -> None:
    db = tmp_path / "agent-cancel-poll.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")

    from app import db as dbmod
    from sqlalchemy import select

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()
    settings = Settings()

    async def cancel_aware_runner(*, emit, is_cancelled, **_kwargs) -> RunResult:
        factory = session_factory()
        async with factory() as session:
            run = (await session.execute(select(RunRow))).scalar_one()
            run.cancel_requested = 1
            await session.commit()
        assert await is_cancelled() is True
        await emit("run.status", {"status": "cancelled"})
        return RunResult(status="cancelled", final_text="")

    monkeypatch.setattr(
        "pico_orchestrator.runner.run_agent_loop",
        cancel_aware_runner,
    )
    token = issue_test_token(
        school_id="school-a",
        membership_id="member-agent-cancel",
        settings=settings,
    )
    response = await chat_completions(
        ChatCompletionRequest(
            model="pico-agent",
            stream=True,
            messages=[ChatMessage(role="user", content="run until cancelled")],
        ),
        authorization=f"Bearer {token}",
        x_conversation_id="conversation-agent-cancel",
        x_workspace_id=None,
        x_pico_membership_id=None,
        settings=settings,
    )

    chunks = [chunk async for chunk in response.body_iterator]
    assert any(b"data: [DONE]" in chunk for chunk in chunks)

    factory = session_factory()
    async with factory() as session:
        run = (await session.execute(select(RunRow))).scalar_one()
        assert run.cancel_requested == 1
        assert run.status == "cancelled"


@pytest.mark.asyncio
async def test_finalize_is_idempotent_and_terminal_status_is_sticky(
    tmp_path,
    monkeypatch,
) -> None:
    db = tmp_path / "finalize-idempotent.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()

    task_id = new_id()
    run_id = new_id()
    factory = session_factory()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-finalize-idempotent",
                title="idempotent",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt="创建 stable.txt",
                model="test-direct-model",
            )
        )
        await session.commit()

    final_text = "done\n```file:stable.txt\nstable body\n```"
    await _finalize_run(
        run_id,
        status="succeeded",
        final_text=final_text,
        task_id=task_id,
    )
    await _finalize_run(
        run_id,
        status="succeeded",
        final_text=final_text,
        task_id=task_id,
    )
    await _finalize_run(
        run_id,
        status="failed",
        error="late failure",
        task_id=task_id,
    )

    async with factory() as session:
        from sqlalchemy import select

        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert run.error is None
        assert run.ended_at is not None

        artifacts = list(
            (
                await session.execute(
                    select(ArtifactRow).where(ArtifactRow.run_id == run_id)
                )
            )
            .scalars()
            .all()
        )
        assert {(row.kind, row.title) for row in artifacts} == {
            ("file", "stable.txt"),
            ("doc", "回复摘要"),
        }

        artifact_events = list(
            (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "artifact.created",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(artifact_events) == 2
        assert {event.payload["artifact_id"] for event in artifact_events} == {
            artifact.id for artifact in artifacts
        }


@pytest.mark.asyncio
async def test_finalize_cancel_request_wins_over_success_and_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    db = tmp_path / "finalize-cancel-wins.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    from app import db as dbmod
    from sqlalchemy import select

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()

    task_id = new_id()
    run_id = new_id()
    factory = session_factory()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-finalize-cancel",
                title="cancel wins",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt="创建 should-not-exist.txt",
                model="test-direct-model",
                cancel_requested=1,
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="done\n```file:should-not-exist.txt\nbody\n```",
        task_id=task_id,
    )

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "cancelled"
        assert run.error is None
        artifacts = list(
            (
                await session.execute(
                    select(ArtifactRow).where(ArtifactRow.run_id == run_id)
                )
            )
            .scalars()
            .all()
        )
        assert artifacts == []
        terminal_events = list(
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
        assert terminal_events[-1].payload == {"status": "cancelled"}


@pytest.mark.asyncio
async def test_unknown_skill_finalize_creates_no_artifact_or_change(
    tmp_path,
    monkeypatch,
) -> None:
    db = tmp_path / "unknown-skill-finalize.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    from app import db as dbmod
    from pico_orchestrator.skill_policy import snapshot_for_skill
    from sqlalchemy import select

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()

    task_id = new_id()
    run_id = new_id()
    snapshot = snapshot_for_skill("skill-reead")
    assert snapshot is not None
    factory = session_factory()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-unknown-skill",
                title="unknown skill",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt="创建 leaked.txt，内容为 should-not-exist",
                model="test-direct-model",
                token_usage_json=json.dumps({"skill_snapshot": snapshot}),
            )
        )
        await session.commit()

    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="```file:leaked.txt\nshould-not-exist\n```",
        task_id=task_id,
        user_prompt="创建 leaked.txt，内容为 should-not-exist",
    )

    async with factory() as session:
        artifacts = (
            await session.execute(select(ArtifactRow).where(ArtifactRow.run_id == run_id))
        ).scalars().all()
        changes = (
            await session.execute(
                select(ChangeProposalRow).where(ChangeProposalRow.run_id == run_id)
            )
        ).scalars().all()
        artifact_events = (
            await session.execute(
                select(EventRow).where(
                    EventRow.run_id == run_id,
                    EventRow.type == "artifact.created",
                )
            )
        ).scalars().all()

        assert artifacts == []
        assert changes == []
        assert artifact_events == []


@pytest.mark.parametrize("stream", [False, True], ids=["non-stream", "stream"])
def test_finalize_paths_expose_identical_run_and_artifact_contract(
    client,
    monkeypatch,
    stream: bool,
) -> None:
    file_body = "name,score\n张三,95\n李四,88"
    final_text = f"已生成：\n```file:report.csv\n{file_body}\n```"
    _stub_provider(monkeypatch, final_text)
    owner = _headers(client, f"member-finalize-{stream}")
    conversation_id = f"conversation-finalize-{stream}"

    task_id = _complete(
        client,
        owner,
        conversation_id=conversation_id,
        stream=stream,
    )

    detail = client.get(f"/v1/tasks/{task_id}", headers=owner)
    assert detail.status_code == 200, detail.text
    artifacts = detail.json()["artifacts"]
    assert {(item["kind"], item["title"]) for item in artifacts} == {
        ("file", "report.csv"),
        ("doc", "回复摘要"),
    }

    file_artifact = next(item for item in artifacts if item["kind"] == "file")
    assert file_artifact["inline"] == file_body
    assert file_artifact["run_id"]

    content = client.get(
        f"/v1/artifacts/{file_artifact['id']}/content",
        headers=owner,
    )
    assert content.status_code == 200, content.text
    assert content.text == file_body
    assert content.headers["content-type"].startswith("text/csv")
    assert content.headers["content-disposition"].startswith("inline;")

    download = client.get(
        f"/v1/artifacts/{file_artifact['id']}/content?download=true",
        headers=owner,
    )
    assert download.status_code == 200, download.text
    assert download.content == file_body.encode()
    assert download.headers["content-disposition"].startswith("attachment;")

    runs = client.get(f"/v1/tasks/{task_id}/runs", headers=owner)
    assert runs.status_code == 200, runs.text
    run_rows = runs.json()["runs"]
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "succeeded"
    assert run_rows[0]["error"] is None
    assert run_rows[0]["id"] == file_artifact["run_id"]

    events = client.get(f"/v1/runs/{run_rows[0]['id']}/events", headers=owner)
    assert events.status_code == 200, events.text
    artifact_events = [
        event for event in events.json()["events"] if event["type"] == "artifact.created"
    ]
    assert {(event["payload"]["kind"], event["payload"]["title"]) for event in artifact_events} == {
        ("file", "report.csv"),
        ("doc", "回复摘要"),
    }

    outsider = _headers(client, f"outsider-{stream}")
    hidden = client.get(f"/v1/tasks/{task_id}", headers=outsider)
    assert hidden.status_code == 404
    hidden_content = client.get(
        f"/v1/artifacts/{file_artifact['id']}/content",
        headers=outsider,
    )
    assert hidden_content.status_code == 404


def test_active_artifact_is_plain_text_inline_and_attachment_on_download(
    client,
    monkeypatch,
) -> None:
    file_body = "<script>window.localStorage.clear()</script>"
    _stub_provider(
        monkeypatch,
        f"已生成：\n```file:unsafe.html\n{file_body}\n```",
    )
    owner = _headers(client, "member-active-artifact")
    task_id = _complete(
        client,
        owner,
        conversation_id="conversation-active-artifact",
        stream=False,
    )

    detail = client.get(f"/v1/tasks/{task_id}", headers=owner)
    file_artifact = next(
        item for item in detail.json()["artifacts"] if item["kind"] == "file"
    )

    content = client.get(
        f"/v1/artifacts/{file_artifact['id']}/content",
        headers=owner,
    )
    assert content.status_code == 200, content.text
    assert content.text == file_body
    assert content.headers["content-type"].startswith("text/plain")
    assert content.headers["content-disposition"].startswith("inline;")
    assert content.headers["x-content-type-options"] == "nosniff"

    download = client.get(
        f"/v1/artifacts/{file_artifact['id']}/content?download=true",
        headers=owner,
    )
    assert download.status_code == 200, download.text
    assert download.content == file_body.encode()
    assert download.headers["content-type"].startswith("text/html")
    assert download.headers["content-disposition"].startswith("attachment;")
