"""T-KB-ENGINE-ON: reindex-all peer guard + membership reindex path."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import _ops_reindex_peer_allowed, app, kb_reindex_all


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("localhost", True),
        ("::ffff:127.0.0.1", True),
        ("172.20.109.183", False),
        ("8.8.8.8", False),
        ("evil.example", False),
        ("", False),
    ],
)
def test_ops_reindex_peer_allowed(host: str, allowed: bool) -> None:
    assert _ops_reindex_peer_allowed(host) is allowed


def test_reindex_all_allows_eth0_hairpin_on_loopback_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rebuild = AsyncMock(return_value={"ok": True, "indexed": 2, "skipped": 1, "total": 3})
    monkeypatch.setattr("app.main.rebuild_materials", rebuild)

    class _Client:
        host = "172.20.109.183"

    class _Req:
        def __init__(self) -> None:
            self.client = _Client()
            self.scope = {"server": ("127.0.0.1", 18765)}

    out = asyncio.run(kb_reindex_all(_Req()))  # type: ignore[arg-type]
    assert out["ok"] is True
    assert out["indexed"] == 2
    rebuild.assert_awaited_once_with(None, force=False)


def test_reindex_all_rejects_public_peer_on_open_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rebuild = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr("app.main.rebuild_materials", rebuild)

    class _Client:
        host = "8.8.8.8"

    class _Req:
        def __init__(self) -> None:
            self.client = _Client()
            self.scope = {"server": ("0.0.0.0", 18765)}

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


# ---- incremental reindex (#1006 步 1) ------------------------------------------------


class _FetchClient:
    """Fake Meili: /documents/fetch pages over the given artifact ids."""

    def __init__(self, ids: list[str], *, status: int = 200) -> None:
        self.ids = ids
        self.status = status
        self.calls: list[dict] = []

    def request(self, method, url, *, json=None, headers=None, timeout=8.0):
        assert method == "POST" and url.endswith("/documents/fetch")
        self.calls.append(dict(json or {}))
        if self.status != 200:
            return self.status, {"message": "boom"}
        offset = int(json["offset"])
        limit = int(json["limit"])
        page = self.ids[offset : offset + limit]
        return 200, {"results": [{"artifact_id": a} for a in page], "total": len(self.ids)}


def test_meili_artifact_ids_pages_past_facet_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator import meili_kb

    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    ids = [f"a{i}" for i in range(250)]
    client = _FetchClient(ids)
    got = meili_kb.MeiliIndex(client).artifact_ids(page=100)
    assert got == set(ids)
    assert [c["offset"] for c in client.calls] == [0, 100, 200]


def test_indexed_artifact_ids_returns_none_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import meili_kb

    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    assert meili_kb.indexed_artifact_ids(client=_FetchClient([], status=500)) is None


class _Art:
    def __init__(self, aid: str, title: str) -> None:
        self.id = aid
        self.kind = "material"
        self.title = title
        self.content_encoding = "utf8"
        self.inline = "正文 " * 20
        self.created_at = None


class _Task:
    id = "t1"
    school_id = "school-1"
    membership_id = "m1"


def _fake_session_factory(rows):
    class _Result:
        def all(self):
            return rows

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            return _Result()

    return lambda: _Session


def _wire_rebuild(monkeypatch: pytest.MonkeyPatch, rows, known):
    from app import kb_rebuild

    chunked: list[str] = []
    monkeypatch.setattr(kb_rebuild, "session_factory", _fake_session_factory(rows))
    monkeypatch.setattr(kb_rebuild, "indexed_artifact_ids", lambda: known)
    monkeypatch.setattr(kb_rebuild, "is_lab_school", lambda _s: False)
    monkeypatch.setattr(kb_rebuild, "is_material", lambda **_k: True)
    monkeypatch.setattr(kb_rebuild, "upsert_documents", lambda docs, **_k: True)

    def _chunks(_p, *, artifact_id, **_k):
        chunked.append(artifact_id)
        return [{"id": f"{artifact_id}:0", "artifact_id": artifact_id}]

    monkeypatch.setattr(kb_rebuild, "material_chunk_docs", _chunks)
    return kb_rebuild, chunked


def test_rebuild_incremental_skips_already_indexed(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(_Art("old", "旧.docx"), _Task()), (_Art("new", "新.docx"), _Task())]
    kb_rebuild, chunked = _wire_rebuild(monkeypatch, rows, {"old"})

    out = asyncio.run(kb_rebuild.rebuild_materials(None))
    assert out["mode"] == "incremental"
    assert out["indexed"] == 1 and out["unchanged"] == 1 and out["skipped"] == 0
    assert out["total"] == 2
    assert chunked == ["new"]


def test_rebuild_force_rechunks_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(_Art("old", "旧.docx"), _Task()), (_Art("new", "新.docx"), _Task())]
    kb_rebuild, chunked = _wire_rebuild(monkeypatch, rows, {"old"})

    out = asyncio.run(kb_rebuild.rebuild_materials(None, force=True))
    assert out["mode"] == "full"
    assert out["indexed"] == 2 and out["unchanged"] == 0
    assert sorted(chunked) == ["new", "old"]


def test_rebuild_falls_back_to_full_when_index_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [(_Art("old", "旧.docx"), _Task())]
    kb_rebuild, chunked = _wire_rebuild(monkeypatch, rows, None)

    out = asyncio.run(kb_rebuild.rebuild_materials(None))
    assert out["mode"] == "full"
    assert out["indexed"] == 1 and chunked == ["old"]


def test_reindex_all_force_query_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    rebuild = AsyncMock(return_value={"ok": True, "mode": "full"})
    monkeypatch.setattr("app.main.rebuild_materials", rebuild)

    class _Client:
        host = "127.0.0.1"

    class _Req:
        def __init__(self) -> None:
            self.client = _Client()
            self.scope = {"server": ("127.0.0.1", 18765)}

    asyncio.run(kb_reindex_all(_Req(), force=True))  # type: ignore[arg-type]
    rebuild.assert_awaited_once_with(None, force=True)
    rebuild.reset_mock()
    asyncio.run(kb_reindex_all(_Req()))  # type: ignore[arg-type]
    rebuild.assert_awaited_once_with(None, force=False)
