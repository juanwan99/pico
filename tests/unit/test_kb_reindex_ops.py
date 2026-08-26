"""T-KB-ENGINE-ON: reindex-all peer guard + membership reindex path."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import _ops_reindex_peer_allowed, app  # noqa: E402


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("localhost", True),
        ("172.20.109.183", True),  # host-network hairpin eth0
        ("10.0.0.8", True),
        ("192.168.1.9", True),
        ("8.8.8.8", False),
        ("evil.example", False),
        ("", False),
    ],
)
def test_ops_reindex_peer_allowed(host: str, allowed: bool) -> None:
    assert _ops_reindex_peer_allowed(host) is allowed


def test_reindex_all_allows_private_hairpin(monkeypatch: pytest.MonkeyPatch) -> None:
    rebuild = AsyncMock(return_value={"ok": True, "indexed": 2, "skipped": 1, "total": 3})
    monkeypatch.setattr("app.main.rebuild_materials", rebuild)

    class _Client:
        host = "172.20.109.183"

    class _Req:
        client = _Client()

    import asyncio

    from app.main import kb_reindex_all

    out = asyncio.run(kb_reindex_all(_Req()))  # type: ignore[arg-type]
    assert out["ok"] is True
    assert out["indexed"] == 2
    rebuild.assert_awaited_once_with(None)


def test_reindex_all_rejects_public_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    rebuild = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr("app.main.rebuild_materials", rebuild)

    class _Client:
        host = "8.8.8.8"

    class _Req:
        client = _Client()

    import asyncio

    from fastapi import HTTPException

    from app.main import kb_reindex_all

    with pytest.raises(HTTPException) as exc:
        asyncio.run(kb_reindex_all(_Req()))  # type: ignore[arg-type]
    assert exc.value.status_code == 403
    rebuild.assert_not_awaited()


def test_health_includes_meili_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pico_orchestrator.meili_kb.health_fields",
        lambda: {
            "meili_configured": True,
            "meili_reachable": True,
            "meili_embedder": False,
            "kb_mode": "keyword",
        },
    )
    body = TestClient(app).get("/health").json()
    assert body["meili_configured"] is True
    assert body["meili_reachable"] is True
    assert body["meili_embedder"] is False
    assert body["kb_mode"] == "keyword"
