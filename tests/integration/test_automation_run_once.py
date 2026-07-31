"""Integration coverage for the real automation run-once path."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import ANY, AsyncMock

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

os.environ["PICO_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test-pico.db"
os.environ["PICO_JWT_SECRET"] = "test-secret-at-least-32-bytes-long!!"
os.environ["PICO_ENV"] = "development"

from app import run_service
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "automation.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    monkeypatch.setattr(run_service, "start_run_background", AsyncMock())

    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, member: str = "m1") -> dict[str, str]:
    response = client.post(
        "/v1/dev/token",
        json={"school_id": "school-a", "membership_id": member},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_run_once_creates_project_task_and_run_without_rescheduling(client: TestClient):
    owner = _headers(client)
    created = client.post(
        "/v1/automations",
        headers=owner,
        json={
            "name": "项目周报",
            "prompt": "汇总项目进展并保存产物",
            "schedule_kind": "periodic",
            "schedule": {"time": "09:00"},
            "workspace_id": "project-1",
        },
    )
    assert created.status_code == 200, created.text
    automation = created.json()["automation"]
    original_next_run = automation["next_run_at"]

    response = client.post(f"/v1/automations/{automation['id']}/run", headers=owner)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["automation"]["last_run_at"] is not None
    assert payload["automation"]["next_run_at"] == original_next_run
    assert payload["task"]["title"] == "[自动] 项目周报"
    assert payload["task"]["workspace_id"] == "project-1"
    assert payload["run"]["task_id"] == payload["task"]["id"]
    assert payload["run"]["status"] == "queued"
    run_service.start_run_background.assert_awaited_once_with(payload["run"]["id"], ANY)

    tasks = client.get("/v1/tasks", headers=owner)
    assert tasks.status_code == 200
    assert any(task["id"] == payload["task"]["id"] for task in tasks.json()["tasks"])

    outsider = _headers(client, member="m2")
    denied = client.post(f"/v1/automations/{automation['id']}/run", headers=outsider)
    assert denied.status_code == 404
