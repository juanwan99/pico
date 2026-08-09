from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


def test_meta_version_reports_product_shell() -> None:
    client = TestClient(app)
    r = client.get("/v1/meta/version")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "git_sha" in body
    assert body["product_ui"] == "librechat"
    assert body["product_ui_ok"] is True
    assert "agent_pins" in body


def test_health_includes_git_sha() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "git_sha" in body
    assert "phase" not in body


def test_meta_tip_is_minimal_public_probe() -> None:
    """G4: /v1/meta/tip returns only build identity fields."""
    client = TestClient(app)
    r = client.get("/v1/meta/tip")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "pico-api"
    assert "git_sha" in body
    # Must not leak canary / rate-limit / edu details on the public tip shape.
    assert "rate_limit" not in body
    assert "pi_agent_canary_membership_count" not in body
    assert "edu_mode" not in body
