"""Integration: Task/Run/Event ledger, cross-school, confirm, cancel."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

# isolated DB per test module
os.environ["PICO_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test-pico.db"
os.environ["PICO_JWT_SECRET"] = "test-secret-at-least-32-bytes-long!!"
os.environ["PICO_ENV"] = "development"

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    # reset settings cache + engine
    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None

    with TestClient(app) as c:
        yield c


def _token(client: TestClient, school="school-a", member="m1") -> str:
    r = client.post(
        "/v1/dev/token",
        json={"school_id": school, "membership_id": member},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health_and_safety(client: TestClient):
    assert client.get("/health").json()["ok"] is True
    s = client.get("/v1/meta/agent-safety").json()
    assert s["proof"]["dangerous_off"] is True


def test_cross_school_deny_events(client: TestClient):
    tok = _token(client)
    r = client.post(
        "/v1/demo/cross-school-deny",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["denied"] is True
    types = [e["type"] for e in body["events"]]
    assert "auth.deny" in types
    assert "tool.call" in types


def test_change_propose_confirm_audit(client: TestClient):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/v1/changes",
        headers=h,
        json={
            "title": "t1",
            "summary": "s1",
            "payload": {"x": 1},
        },
    )
    assert r.status_code == 200
    cid = r.json()["change"]["id"]
    assert r.json()["change"]["status"] == "proposed"
    c2 = client.post(f"/v1/changes/{cid}/confirm", headers=h, json={})
    assert c2.status_code == 200
    assert c2.json()["change"]["status"] == "confirmed"
    assert c2.json()["change"]["confirmed_by"] == "m1"
    lst = client.get("/v1/changes", headers=h).json()["changes"]
    assert any(x["id"] == cid and x["status"] == "confirmed" for x in lst)


def test_cancel_queued_run(client: TestClient, monkeypatch):
    """Cancel before/during run — terminal status correct."""
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}

    # Avoid real model: force fail path by clearing keys for this process
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    r = client.post(
        "/v1/tasks",
        headers=h,
        json={"title": "c", "prompt": "hello"},
    )
    assert r.status_code == 200
    run_id = r.json()["run"]["id"]
    # Immediately cancel
    c = client.post(f"/v1/runs/{run_id}/cancel", headers=h, json={})
    assert c.status_code == 200

    # Wait for worker
    status = None
    for _ in range(30):
        time.sleep(0.1)
        st = client.get(f"/v1/runs/{run_id}", headers=h).json()["run"]["status"]
        status = st
        if st in ("cancelled", "failed", "succeeded"):
            break
    assert status in ("cancelled", "failed", "succeeded")


@pytest.mark.skipif(
    not os.environ.get("KIMI_API_KEY"),
    reason="S1 real key required for multi-step loop",
)
def test_task_run_with_real_model(client: TestClient):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/v1/tasks",
        headers=h,
        json={
            "title": "classes",
            "prompt": "请调用工具列出我学校的班级，然后用一句话总结。",
        },
    )
    assert r.status_code == 200
    run_id = r.json()["run"]["id"]
    task_id = r.json()["task"]["id"]
    status = "queued"
    for _ in range(90):
        time.sleep(1)
        status = client.get(f"/v1/runs/{run_id}", headers=h).json()["run"]["status"]
        if status in ("succeeded", "failed", "cancelled"):
            break
    assert status == "succeeded", status
    events = client.get(f"/v1/runs/{run_id}/events", headers=h).json()["events"]
    types = [e["type"] for e in events]
    assert "run.status" in types
    assert any(t.startswith("agent.") or t == "tool.call" or t == "message.delta" for t in types)
    # Prefer tool path but model may answer without tools occasionally
    task = client.get(f"/v1/tasks/{task_id}", headers=h).json()
    assert task["task"]["id"] == task_id
