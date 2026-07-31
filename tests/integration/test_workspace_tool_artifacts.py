from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "workspace-tools.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
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


def _invoke(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    arguments: dict,
):
    return client.post(
        "/v1/tools/invoke",
        headers=headers,
        json={"name": name, "arguments": arguments},
    )


def test_workspace_tool_artifact_round_trip_and_membership_isolation(client) -> None:
    owner = _headers(client, "member-a")
    outsider = _headers(client, "member-b")

    created = _invoke(
        client,
        owner,
        "workspace_write_file",
        {"title": "track-a.json", "content": '{"answer": 42}', "kind": "json"},
    )
    assert created.status_code == 200, created.text
    artifact_id = created.json()["result"]["artifact_id"]
    task_id = created.json()["result"]["task_id"]

    listed = _invoke(client, owner, "workspace_list_files", {"limit": 10})
    assert listed.status_code == 200, listed.text
    assert listed.json()["result"]["artifacts"][0]["artifact_id"] == artifact_id

    read = _invoke(
        client, owner, "workspace_read_file", {"artifact_id": artifact_id}
    )
    assert read.status_code == 200, read.text
    assert read.json()["result"]["artifact"]["content"] == '{"answer": 42}'

    task = client.get(f"/v1/tasks/{task_id}", headers=owner)
    assert task.status_code == 200, task.text
    assert task.json()["artifacts"][0]["id"] == artifact_id
    content = client.get(f"/v1/artifacts/{artifact_id}/content", headers=owner)
    assert content.status_code == 200
    assert content.text == '{"answer": 42}'

    outsider_list = _invoke(client, outsider, "workspace_list_files", {})
    assert outsider_list.status_code == 200
    assert outsider_list.json()["result"] == {"artifacts": [], "count": 0}
    denied = _invoke(
        client, outsider, "workspace_read_file", {"artifact_id": artifact_id}
    )
    assert denied.status_code == 400
    assert denied.json()["detail"]["code"] == "artifact.not_found"
    assert client.get(f"/v1/artifacts/{artifact_id}/content", headers=outsider).status_code == 404


def test_existing_s7_propose_tool_is_preserved(client) -> None:
    headers = _headers(client, "member-a")
    response = _invoke(
        client,
        headers,
        "pico_propose_change",
        {"title": "Keep S7", "summary": "No direct write", "payload": {"x": 1}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["proposal"]["status"] == "proposed"
