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
    assert body["apps_web_present"] is False
    assert body["product_ui_ok"] is True
    assert "agent_pins" in body


def test_health_includes_git_sha() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert "git_sha" in r.json()
