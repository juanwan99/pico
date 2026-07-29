"""L2: SSE stream endpoint shape + cancel path."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


def _token(client: TestClient, member: str = "member-l2") -> str:
    r = client.post(
        "/v1/dev/token",
        json={"school_id": "school-a", "membership_id": member},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_stream_requires_auth() -> None:
    client = TestClient(app)
    r = client.get("/v1/runs/nonexistent/stream")
    assert r.status_code in (401, 403, 422)


def test_stream_404_for_foreign_or_missing() -> None:
    client = TestClient(app)
    tok = _token(client, "member-l2-404")
    r = client.get(
        "/v1/runs/does-not-exist/stream",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 404


def test_cancel_and_stream_end() -> None:
    """Cancel marks terminal; SSE must end with stream.end (no hang)."""
    client = TestClient(app)
    tok = _token(client, "member-l2-stream")
    h = {"Authorization": f"Bearer {tok}"}
    created = client.post(
        "/v1/tasks",
        headers=h,
        json={"title": "l2-stream", "prompt": "ping"},
    )
    assert created.status_code == 200, created.text
    run_id = created.json()["run"]["id"]

    cancel = client.post(f"/v1/runs/{run_id}/cancel", headers=h, json={})
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["run"]["id"] == run_id

    with client.stream(
        "GET",
        f"/v1/runs/{run_id}/stream",
        headers={**h, "Accept": "text/event-stream"},
        timeout=15.0,
    ) as res:
        assert res.status_code == 200
        assert "text/event-stream" in (res.headers.get("content-type") or "")
        chunks: list[str] = []
        for line in res.iter_lines():
            if line:
                chunks.append(line)
            if "stream.end" in "\n".join(chunks):
                break
            if len(chunks) > 80:
                break
        text = "\n".join(chunks)
        assert "stream.end" in text
