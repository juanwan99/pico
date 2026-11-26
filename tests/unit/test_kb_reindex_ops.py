"""T-KB-ENGINE-ON: reindex-all peer guard + membership reindex path."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
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

    async def queue_and_wait():
        request = _Req()
        request.app = app
        out = await kb_reindex_all(request)
        await app.state.kb_reindex_task
        return out

    out = asyncio.run(queue_and_wait())
    assert out == {"ok": True, "queued": True, "mode": "incremental"}
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

    def __init__(self, ids: list[str | dict]) -> None:
        self.ids = ids
        self.calls: list[dict] = []

    def request(self, method, url, *, json=None, headers=None, timeout=8.0):
        assert method == "POST" and url.endswith("/documents/fetch")
        self.calls.append(dict(json or {}))
        offset = int(json["offset"])
        limit = int(json["limit"])
        page = self.ids[offset : offset + limit]
        return 200, {
            "results": [a if isinstance(a, dict) else {"artifact_id": a} for a in page],
            "total": len(self.ids),
        }


def test_meili_artifact_ids_pages_past_facet_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator import meili_kb

    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    ids = [f"a{i}" for i in range(250)]
    client = _FetchClient(ids)
    got = meili_kb.MeiliIndex(client).artifact_ids(page=100)
    assert got == set(ids)
    assert [c["offset"] for c in client.calls] == [0, 100, 200]


def test_artifact_ids_ignores_incomplete_artifacts():
    from pico_orchestrator import meili_kb

    client = _FetchClient([
        {"artifact_id": "complete", "seq": 2},
        {"artifact_id": "partial", "seq": 1},
        {"artifact_id": "complete", "seq": 0},
        {"artifact_id": "legacy"},
    ])
    assert meili_kb.MeiliIndex(client).artifact_ids(page=2) == {"complete", "legacy"}
    assert all(call["fields"] == ["artifact_id", "seq"] for call in client.calls)


class _Art:
    def __init__(
        self,
        aid: str,
        title: str,
        origin: str = "upload",
        *,
        kind: str = "material",
        run_id: str | None = None,
    ) -> None:
        self.id = aid
        self.kind = kind
        self.title = title
        self.origin = origin
        self.run_id = run_id
        self.content_encoding = "utf8"
        self.inline = "正文 " * 20
        self.created_at = None


class _Task:
    id = "t1"
    school_id = "school-1"
    membership_id = "m1"
    title = "edu-read · 旧.docx"


def _fake_session_factory(rows, reads):
    from app.db import ArtifactRow

    class _Result:
        def __init__(self, entries):
            self.entries = entries

        def all(self):
            return self.entries

        def one_or_none(self):
            if not self.entries:
                return None
            (entry,) = self.entries
            return entry

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            compiled = stmt.compile()
            if stmt.column_descriptions[0]["expr"] is ArtifactRow:
                # Even deferred inline data can be read by SQLite when the SELECT
                # projects later fields. Assert the actual compiled projection.
                projection = str(compiled).split("\nFROM ", 1)[0].removeprefix("SELECT ")
                assert {col.split(" AS ", 1)[0] for col in projection.split(", ")} == {
                    "artifacts.id", "artifacts.task_id", "artifacts.run_id",
                    "artifacts.kind", "artifacts.title",
                    "tasks.id", "tasks.school_id", "tasks.membership_id", "tasks.title",
                }
                return _Result(rows)
            columns = list(stmt.selected_columns.keys())
            if columns == ["origin"]:
                ids = {compiled.params["id_1"]}
                reads["origin"].update(ids)
            else:
                assert columns == ["id", "content_encoding", "created_at", "inline"]
                ids = set(compiled.params["id_1"])
                reads["body"].update(ids)
            return _Result([artifact for artifact, _ in rows if artifact.id in ids])

    return lambda: _Session


def _wire_rebuild(monkeypatch: pytest.MonkeyPatch, rows, known):
    from app import kb_rebuild

    chunked: list[str] = []
    reads: dict[str, set[str]] = {"origin": set(), "body": set()}

    def artifact_ids():
        if isinstance(known, Exception):
            raise known
        return known

    index = SimpleNamespace(
        wait_until_idle=AsyncMock(),
        upsert_rebuild_batch=AsyncMock(),
        artifact_ids=artifact_ids,
    )
    monkeypatch.setattr(kb_rebuild, "MeiliIndex", lambda: index)
    monkeypatch.setattr(kb_rebuild, "session_factory", _fake_session_factory(rows, reads))

    def _chunks(_p, *, artifact_id, **_k):
        chunked.append(artifact_id)
        return [{"id": f"{artifact_id}:0", "artifact_id": artifact_id}]

    monkeypatch.setattr(kb_rebuild, "material_chunk_docs", _chunks)
    return kb_rebuild, chunked, reads, index


def test_rebuild_incremental_skips_already_indexed(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(_Art("old", "旧.docx"), _Task()), (_Art("new", "新.docx"), _Task())]
    kb_rebuild, chunked, reads, _ = _wire_rebuild(monkeypatch, rows, {"old"})

    out = asyncio.run(kb_rebuild.rebuild_materials(None))
    assert out["mode"] == "incremental"
    assert out["indexed"] == 1 and out["unchanged"] == 1 and out["skipped"] == 0
    assert out["total"] == 2
    assert chunked == ["new"]
    assert reads == {"origin": {"new"}, "body": {"new"}}


def test_rebuild_force_rechunks_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(_Art("old", "旧.docx"), _Task()), (_Art("new", "新.docx"), _Task())]
    kb_rebuild, chunked, _, _ = _wire_rebuild(monkeypatch, rows, {"old"})

    out = asyncio.run(kb_rebuild.rebuild_materials(None, force=True))
    assert out["mode"] == "full"
    assert out["indexed"] == 2 and out["unchanged"] == 0
    assert sorted(chunked) == ["new", "old"]


async def test_rebuild_upload_uses_kb_text_and_skips_excerpt(monkeypatch: pytest.MonkeyPatch):
    from app import kb_rebuild

    title = "上传.docx"
    original = _Art("original", title, kind="edu_office")
    original.content_encoding = "base64"
    original.inline = "ZmlsZQ=="
    excerpt = _Art("excerpt", title, kind="edu_excerpt")
    kb_text = _Art("kb-text", title, kind="kb_text")
    kb_text.inline = "上传正文"
    binary_text = _Art("binary-text", title, kind="kb_text")
    binary_text.content_encoding = "base64"
    pico_text = _Art("pico-text", title, origin="pico", kind="kb_text", run_id="r1")
    rows = [
        (artifact, _Task()) for artifact in (original, excerpt, kb_text, binary_text, pico_text)
    ]
    _, _, reads, index = _wire_rebuild(monkeypatch, rows, {"kb-text", "binary-text"})
    chunk = {"artifact_id": original.id}

    def material_chunk_docs(_task, *, artifact_id, content, stored_text, **_):
        assert artifact_id == original.id
        assert content == b"file"
        assert stored_text == kb_text.inline
        return [chunk]

    monkeypatch.setattr(kb_rebuild, "material_chunk_docs", material_chunk_docs)
    out = await kb_rebuild.rebuild_materials()
    assert out["indexed"] == 1 and out["unchanged"] == 2 and out["skipped"] == 2
    assert reads == {"origin": {"original"}, "body": {"original", "kb-text", "binary-text"}}
    index.upsert_rebuild_batch.assert_awaited_once_with([chunk])


def test_rebuild_stops_when_index_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(_Art("old", "旧.docx"), _Task())]
    error = RuntimeError("meili documents/fetch http 500")
    kb_rebuild, chunked, reads, index = _wire_rebuild(monkeypatch, rows, error)

    with pytest.raises(RuntimeError, match="documents/fetch http 500"):
        asyncio.run(kb_rebuild.rebuild_materials())
    assert not chunked and reads == {"origin": set(), "body": set()}
    index.upsert_rebuild_batch.assert_not_awaited()


async def test_meili_rebuild_waits_for_a_slow_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator import meili_kb

    states = iter(["enqueued", *(["processing"] * 61), "succeeded"])
    calls = []

    class SlowMeili:
        has_older_task = True

        def request(self, method, url, **_):
            calls.append(method)
            if "/tasks?" in url:
                results = [{"uid": 10}] if self.has_older_task else []
                self.has_older_task = False
                return 200, {"results": results}
            if method == "POST":
                return 202, {"taskUid": 11}
            assert url.endswith("/tasks/11")
            return 200, {"status": next(states)}

    sleep = AsyncMock()
    monkeypatch.setattr(
        meili_kb,
        "asyncio",
        SimpleNamespace(
            to_thread=asyncio.to_thread, sleep=sleep, create_task=asyncio.create_task,
            shield=asyncio.shield, CancelledError=asyncio.CancelledError,
        ),
    )
    index = meili_kb.MeiliIndex(SlowMeili())
    monkeypatch.setattr(index, "ensure", lambda: None)

    await index.wait_until_idle()
    await index.upsert_rebuild_batch([{"chunk_id": "upload_0000"}])
    assert calls == ["GET", "GET", "POST", *(["GET"] * 63)]
    assert sleep.await_count == 63


@pytest.mark.parametrize("during_submission", [True, False])
async def test_rebuild_cancellation_waits_only_for_submission(
    monkeypatch: pytest.MonkeyPatch, during_submission: bool,
) -> None:
    from app.kb_rebuild import _Pace
    from pico_orchestrator.meili_kb import MeiliIndex

    posting = Event()
    allow_post = Event()
    polling = Event()
    allow_success = Event()

    class BusyMeili:
        def request(self, method, url, **_):
            if method == "POST":
                assert url.endswith("/documents")
                posting.set()
                assert allow_post.wait(5)
                return 202, {"taskUid": 42}
            assert method == "GET" and url.endswith("/tasks/42")
            polling.set()
            return 200, {"status": "succeeded" if allow_success.is_set() else "processing"}

    index = MeiliIndex(BusyMeili())
    monkeypatch.setattr(index, "ensure", lambda: None)
    push = asyncio.create_task(_Pace(per_min=600).push(index, [{"chunk_id": "doc_0"}]))
    try:
        assert await asyncio.to_thread(posting.wait, 2)
        if not during_submission:
            allow_post.set()
            assert await asyncio.to_thread(polling.wait, 2)
        push.cancel()
        if during_submission:
            await asyncio.sleep(0)
            assert not push.done()
            allow_post.set()
        done, _ = await asyncio.wait({push}, timeout=1)
        assert push in done, "cancellation waited for Meili task success"
        with pytest.raises(asyncio.CancelledError):
            await push
        assert polling.is_set() is not during_submission
    finally:
        allow_post.set()
        allow_success.set()
        await asyncio.gather(push, return_exceptions=True)


async def test_reindex_all_force_ack_and_health_while_meili_is_busy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import meili_kb

    rows = [(_Art("upload", "新.docx"), _Task())]
    kb_rebuild, _, _, _ = _wire_rebuild(monkeypatch, rows, {"upload"})
    monkeypatch.setattr(app.state, "kb_reindex_task", None, raising=False)
    started = Event()
    release = Event()

    class SlowMeili:
        def request(self, method, url, *, json=None, **_):
            if url.endswith("/health"):
                return 200, {"status": "available"}
            if "/tasks?" in url:
                return 200, {"results": []}
            if url.endswith("/documents"):
                assert method == "POST" and json[0]["artifact_id"] == "upload"
                return 202, {"taskUid": 11}
            assert url.endswith("/tasks/11")
            started.set()
            assert release.wait(5)
            return 200, {"status": "succeeded"}

    index = meili_kb.MeiliIndex(SlowMeili())
    monkeypatch.setattr(index, "ensure", lambda: None)
    monkeypatch.setattr(kb_rebuild, "MeiliIndex", lambda: index)
    monkeypatch.setattr(meili_kb, "MeiliIndex", lambda: index)
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:18765"
    ) as client:
        queued = await asyncio.wait_for(client.post("/v1/kb/reindex-all?force=1"), 1)
        assert queued.status_code == 202
        assert queued.json() == {"ok": True, "queued": True, "mode": "full"}

        try:
            assert await asyncio.to_thread(started.wait, 2)
            started_at = time.monotonic()
            health = await asyncio.wait_for(client.get("/health"), 1)
            assert health.status_code == 200 and health.json()["ok"] is True
            assert health.json()["meili_reachable"] is True
            assert time.monotonic() - started_at < 1
            running = app.state.kb_reindex_task
            incremental = await client.post("/v1/kb/reindex-all")
            assert incremental.status_code == 202
            assert incremental.json() == {
                "ok": True, "queued": True, "mode": "incremental", "already_running": True
            }
            assert (await client.post("/v1/kb/reindex-all?force=1")).status_code == 409
            assert app.state.kb_reindex_task is running and not running.done()
        finally:
            release.set()
            await app.state.kb_reindex_task


async def test_rebuild_caps_batch_size_and_stops_on_failed_task(monkeypatch: pytest.MonkeyPatch):
    rows = [(_Art("upload", "新.docx"), _Task())]
    kb_rebuild, _, _, index = _wire_rebuild(monkeypatch, rows, set())
    size = kb_rebuild._BATCH_SIZE
    monkeypatch.setattr(
        kb_rebuild, "material_chunk_docs",
        lambda *_args, **_kwargs: [{"seq": seq} for seq in range(2 * size + 1)],
    )
    index.upsert_rebuild_batch.side_effect = [None, RuntimeError("meili task canceled")]

    with pytest.raises(RuntimeError, match="task canceled"):
        await kb_rebuild.rebuild_materials()
    batches = [call.args[0] for call in index.upsert_rebuild_batch.await_args_list]
    assert [[doc["seq"] for doc in batch] for batch in batches] == [
        list(range(2 * size, size, -1)),
        list(range(size, 0, -1)),
    ]


async def test_rebuild_paces_by_chunk_count_and_meili_busy_time(monkeypatch: pytest.MonkeyPatch):
    from app import kb_rebuild

    now = 0.0
    starts = []
    durations = iter([5, 1, 0])

    async def sleep(delay):
        nonlocal now
        now += delay

    async def upsert(_docs):
        starts.append(now)
        await sleep(next(durations))

    monkeypatch.setattr(kb_rebuild, "time", SimpleNamespace(monotonic=lambda: now))
    monkeypatch.setattr(kb_rebuild, "asyncio", SimpleNamespace(sleep=sleep))
    index = SimpleNamespace(upsert_rebuild_batch=upsert)
    pace = kb_rebuild._Pace(per_min=600)
    docs = [{}] * 20
    await pace.push(index, docs)
    await sleep(1)  # Chunking between batches counts towards the idle interval.
    await pace.push(index, docs)
    await pace.push(index, docs)

    assert starts == [0, 10, 13]


@pytest.mark.parametrize("force", [False, True])
def test_rebuild_leaves_pico_drafts_out(monkeypatch: pytest.MonkeyPatch, force: bool) -> None:
    """pico#1298: Pico-made files never enter the library, old or new."""

    class _RunTask(_Task):
        title = "做一份浮力讲义"

    rows = [
        (_Art("up", "上传.docx"), _Task()),
        (_Art("legacy-up", "旧上传.docx", origin=""), _Task()),
        (_Art("draft", "讲义.docx", origin="pico", run_id="r1"), _Task()),
        (_Art("legacy-draft", "旧讲义.docx", origin=""), _RunTask()),
        (_Art("runless-draft", "草稿.docx", origin="pico"), _Task()),
    ]
    kb_rebuild, chunked, reads, _ = _wire_rebuild(monkeypatch, rows, set())

    out = asyncio.run(kb_rebuild.rebuild_materials(None, force=force))
    assert sorted(chunked) == ["legacy-up", "up"]
    assert reads == {
        "origin": {"legacy-up", "up", "runless-draft"},
        "body": {"legacy-up", "up"},
    }
    assert out["indexed"] == 2 and out["skipped"] == 3
