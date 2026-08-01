from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app
from app.settings import Settings, get_settings


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["edu_mode"] in {"fake", "live"}
    assert body["rate_limit"] == {
        "chat_rpm": 30,
        "chat_max_concurrent": 2,
        "key_scope": "membership_or_ip",
    }
    assert body["kimi_agent_runtime_enabled"] is False
    assert body["kimi_agent_canary_configured"] is False
    assert not any("secret" in key or "token" in key for key in body)


def test_health_exposes_only_non_sensitive_canary_state() -> None:
    membership_id = "private-member-id"
    settings = Settings(
        _env_file=None,
        pico_kimi_agent_runtime=True,
        pico_kimi_agent_canary_membership_ids=membership_id,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    body = response.json()
    assert body["kimi_agent_runtime_enabled"] is True
    assert body["kimi_agent_canary_configured"] is True
    assert membership_id not in response.text


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
    assert body["runtime"] == "kimi-agent"
    proof_path = Path(body["proof"]["agent_file"])
    assert proof_path == (
        ROOT / "services/orchestrator/agents/pico-kimi-runtime.yaml"
    ).resolve()
    assert body["proof"]["dangerous_off"] is True
    assert body["proof"]["violations"] == []
    assert body["proof"]["mcp_configured"] is False
    assert body["proof"]["tools"]
    assert all(
        tool.startswith("pico_orchestrator.kimi_tools:")
        for tool in body["proof"]["tools"]
    )


def test_agent_safety_endpoint_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def unsafe_proof(_agent_file: Path) -> dict:
        raise AssertionError("dangerous runtime tool")

    monkeypatch.setattr(
        "pico_orchestrator.safety.assert_dangerous_tools_off",
        unsafe_proof,
    )
    response = TestClient(app).get("/v1/meta/agent-safety")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "safety.check_failed"
