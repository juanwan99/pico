"""M2 B2-B4 regressions: conversation binding, finalize parity, artifacts."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app  # noqa: E402
from pico_orchestrator.runner import RunResult  # noqa: E402


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
