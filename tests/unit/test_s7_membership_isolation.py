from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


def _headers(mid: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer pico-dev",
        "X-Pico-Membership-Id": mid,
        "Content-Type": "application/json",
    }


def test_changes_isolated_by_membership() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/changes",
        headers=_headers("mem-a"),
        json={"title": "a-only", "summary": "s", "payload": {"k": 1}},
    )
    assert r.status_code == 200
    cid = r.json()["change"]["id"]

    rb = client.get("/v1/changes", headers=_headers("mem-b"))
    assert rb.status_code == 200
    ids_b = [c["id"] for c in rb.json().get("changes") or []]
    assert cid not in ids_b

    ra = client.get("/v1/changes", headers=_headers("mem-a"))
    assert ra.status_code == 200
    ids_a = [c["id"] for c in ra.json().get("changes") or []]
    assert cid in ids_a
