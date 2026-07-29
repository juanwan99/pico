from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_dev_token_and_me() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/dev/token",
        json={"school_id": "school-a", "membership_id": "m1"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["school_id"] == "school-a"


def test_agent_safety_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/meta/agent-safety")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["proof"]["dangerous_off"] is True
