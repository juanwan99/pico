from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "packages" / "field-kb-ingest"))

from app.auth import issue_test_token
from app.edu_kb_ingest import MAX_BYTES
from app.main import app
from app.settings import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "edu-kb.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_HOOK_SERVICE_TOKEN", "kb-test-hook-token")
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client


def _token(scopes=None, school="school-a") -> str:
    return issue_test_token(
        school_id=school,
        membership_id="m-edu",
        scopes=scopes if scopes is not None else ["ai:run", "ai:read"],
        settings=get_settings(),
    )


def test_max_bytes_is_20mb():
    assert MAX_BYTES == 20 * 1024 * 1024


def test_ingest_requires_bearer(client: TestClient) -> None:
    res = client.post("/v1/kb/ingest", json={"title": "a", "text": "hello"})
    assert res.status_code == 401


def test_ingest_ocr_missing_code(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod

    def fake_bytes(**kwargs):
        return {
            "ok": False,
            "unread": True,
            "code": "ocr_missing",
            "error": "No OCR engine found",
            "slices": [],
        }

    monkeypatch.setattr(ingest_mod, "ingest_bytes", fake_bytes)
    raw = b"%PDF-1.3 scan"
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": "通知.pdf",
            "filename": "通知.pdf",
            "content_b64": base64.b64encode(raw).decode("ascii"),
        },
    )
    assert res.status_code == 503, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "ocr_missing"


def test_ingest_unsupported_format_is_415_with_human_line(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod

    def fake_bytes(**kwargs):
        return {
            "ok": False,
            "unread": True,
            "code": "unsupported_format",
            "error": "这种格式（.xyz）知识库读不了。支持：docx / xlsx / pptx / md / html / PDF / png / jpg。",
            "slices": [],
        }

    monkeypatch.setattr(ingest_mod, "ingest_bytes", fake_bytes)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": "笔记",
            "filename": "笔记.xyz",
            "content_b64": base64.b64encode(b"\xd0\xcf\x11\xe0").decode(),
        },
    )
    assert res.status_code == 415, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "unsupported_format"
    assert "读不了" in detail["message"]


def test_ingest_wps_converts_then_indexes(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod

    seen = {}

    async def fake_convert(filename: str, data: bytes) -> bytes:
        seen["name"] = filename
        assert data[:2] != b"PK"
        return b"PK\x03\x04converted-ooxml"

    def fake_bytes(**kwargs):
        seen["ingest_name"] = kwargs.get("filename")
        return {
            "ok": True,
            "engine": "docling",
            "tags": ["docling"],
            "markdown": "通知正文一段",
            "slices": [{"title": "通知", "excerpt": "通知正文一段", "tags": ["docling"]}],
        }

    monkeypatch.setattr(
        "pico_orchestrator.office.convert.convert_legacy_office_bytes",
        fake_convert,
    )
    monkeypatch.setattr(ingest_mod, "ingest_bytes", fake_bytes)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": "通知",
            "filename": "通知.wps",
            "content_b64": base64.b64encode(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1OLE").decode(),
        },
    )
    assert res.status_code == 200, res.text
    assert seen["name"].endswith(".wps")
    assert seen["ingest_name"].endswith(".docx")
    body = res.json()
    assert body["ok"] is True
    assert body["engine"] == "docling"


def test_ingest_legacy_convert_fail_is_422(client: TestClient, monkeypatch) -> None:
    from pico_orchestrator.office.convert import LegacyOfficeConvertError

    async def boom(filename: str, data: bytes) -> bytes:
        raise LegacyOfficeConvertError("旧版文档转不开")

    monkeypatch.setattr(
        "pico_orchestrator.office.convert.convert_legacy_office_bytes",
        boom,
    )
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": "通知",
            "filename": "通知.wps",
            "content_b64": base64.b64encode(b"\xd0\xcf\x11\xe0OLE").decode(),
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "file.legacy_unconvertible"
    assert "旧格式" in detail["message"]


def test_ingest_ok_passes_ocr_tags(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod

    monkeypatch.setattr(
        ingest_mod,
        "ingest_bytes",
        lambda **kwargs: {
            "ok": True,
            "engine": "rapidocr",
            "tags": ["pdfium", "empty-layer", "ocr"],
            "slices": [{"title": "扫描卷", "excerpt": "胰岛素调节血糖", "tags": ["ocr"]}],
        },
    )
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": "扫描卷",
            "filename": "扫描卷.pdf",
            "content_b64": base64.b64encode(b"%PDF-1.3").decode(),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["engine"] == "rapidocr"
    assert "ocr" in body["tags"]


def test_ingest_empty_does_not_return_filename(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod

    def fake_bytes(**kwargs):
        return {
            "ok": False,
            "unread": True,
            "code": "empty",
            "error": "empty",
            "slices": [],
        }

    monkeypatch.setattr(ingest_mod, "ingest_bytes", fake_bytes)
    title = "关于组织开展株洲市中小学教师人工智能素养市级培训的通知(1).pdf"
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": title,
            "filename": title,
            "content_b64": base64.b64encode(b"%PDF-1.3").decode("ascii"),
        },
    )
    assert res.status_code == 400, res.text
    body = res.json()
    assert body["detail"]["code"] == "empty"
    assert title not in str(body)


def test_ingest_ok_slices(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod

    def fake_bytes(**kwargs):
        return {
            "ok": True,
            "engine": "docling",
            "slices": [{"title": "通知", "excerpt": "培训对象 人工智能素养", "tags": ["docling"]}],
        }

    monkeypatch.setattr(ingest_mod, "ingest_bytes", fake_bytes)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={
            "kind": "material",
            "title": "通知.pdf",
            "filename": "通知.pdf",
            "content_b64": base64.b64encode(b"%PDF-1.3").decode("ascii"),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert "人工智能素养" in body["slices"][0]["excerpt"]


def test_file_too_large_413() -> None:
    from app.edu_kb_ingest import _decode
    from fastapi import HTTPException

    huge = base64.b64encode(b"a" * (MAX_BYTES + 1)).decode("ascii")
    with pytest.raises(HTTPException) as caught:
        _decode(huge)
    assert caught.value.status_code == 413
    assert caught.value.detail["code"] == "file.too_large"
    assert "20MB" in caught.value.detail["message"]


def _usage_rows(tmp_path):
    with sqlite3.connect(tmp_path / "edu-kb.db") as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM usage_events")]


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("school_run", [False, True])
def test_ingest_usage_success_and_payer(client, monkeypatch, tmp_path, binary, school_run):
    import ingest as ingest_mod

    result = {"ok": True, "slices": [{"title": "note", "excerpt": "hello"}]}
    monkeypatch.setattr(ingest_mod, "ingest_bytes", lambda **kwargs: result)
    monkeypatch.setattr(ingest_mod, "ingest_text", lambda **kwargs: result)
    scopes = ["ai:run", "ai:read"] + (["ai:school-run"] if school_run else [])
    headers = {"authorization": f"Bearer {_token(scopes)}"}
    payload = {"kind": "notice", "bill_to": "member" if school_run else "school"}
    if binary:
        payload["content_b64"] = base64.b64encode(b"hello").decode("ascii")
    else:
        payload["text"] = "hello"
    for attempt in range(2):
        if binary and attempt:
            payload["content_b64"] += "\n"
        response = client.post("/v1/kb/ingest", headers=headers, json=payload)
        assert response.status_code == 200, response.text
        rows = _usage_rows(tmp_path)
        assert len(rows) == 1
    row = rows[0]
    digest = hashlib.sha256(b"hello").hexdigest()
    assert row["idempotency_key"] == f"kb_ingest:school-a:notice:{digest}:{digest}"
    assert (row["kind"], row["source"], row["tokens_unknown"]) == ("api", "kb_ingest", 1)
    assert all(row[key] is None for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    assert json.loads(row["extra_json"])["bill_to"] == ("school" if school_run else "member")

    exported = client.get(
        "/v1/internal/usage/export",
        headers={"authorization": "Bearer kb-test-hook-token"},
    )
    assert exported.status_code == 200, exported.text
    event = exported.json()["events"][0]
    assert event["points"] is None
    assert event["tokens_unknown"] is True
    teacher = client.get("/v1/usage/events", headers=headers)
    assert teacher.status_code == 200, teacher.text
    events = teacher.json()["events"]
    assert len(events) == (0 if school_run else 1)
    if events:
        assert events[0]["points"] is None
        assert "total_tokens" not in events[0]
    for surface in (response.json(), exported.json(), teacher.json()):
        assert '"price"' not in json.dumps(surface)


def test_ingest_usage_distinct_item_ids_same_content(client, monkeypatch, tmp_path):
    import ingest as ingest_mod

    monkeypatch.setattr(
        ingest_mod, "ingest_text", lambda **kwargs: {"ok": True, "slices": [{"excerpt": "hello"}]}
    )
    headers = {"authorization": f"Bearer {_token()}"}
    for item_id in ("item-a", "item-b"):
        response = client.post(
            "/v1/kb/ingest",
            headers=headers,
            json={"kind": "material", "item_id": item_id, "text": "hello"},
        )
        assert response.status_code == 200, response.text
    rows = _usage_rows(tmp_path)
    assert len(rows) == 2
    digest = hashlib.sha256(b"hello").hexdigest()
    keys = {row["idempotency_key"] for row in rows}
    assert keys == {
        f"kb_ingest:school-a:material:item-a:{digest}",
        f"kb_ingest:school-a:material:item-b:{digest}",
    }


@pytest.mark.parametrize(
    "failure,status,code",
    [
        ("empty", 400, "empty"),
        ("ocr_missing", 503, "ocr_missing"),
        ("hf_offline", 503, "hf_offline"),
        ("docling", 503, "docling_missing"),
        ("exception", 422, "ingest.failed"),
        ("http", 422, "extract.invalid"),
        ("decode", 400, "file.invalid"),
        ("too_large", 413, "file.too_large"),
        ("import", 503, "ingest.unavailable"),
    ],
)
def test_ingest_failure_records_before_response_and_deduplicates(
    client, monkeypatch, tmp_path, failure, status, code,
):
    import ingest as ingest_mod
    from fastapi import HTTPException

    def fail(**kwargs):
        if failure == "docling":
            raise ModuleNotFoundError("docling")
        if failure == "exception":
            raise ValueError("bad document")
        if failure == "http":
            raise HTTPException(422, {"code": "extract.invalid"})
        return {"ok": False, "code": failure, "slices": []}

    monkeypatch.setattr(ingest_mod, "ingest_text", fail)
    if failure == "import":
        monkeypatch.setitem(sys.modules, "ingest", None)
    payload = {"kind": "material", "text": "same content"}
    if failure == "decode":
        payload = {"kind": "material", "content_b64": "a"}
    if failure == "too_large":
        monkeypatch.setattr("app.edu_kb_ingest.MAX_BYTES", 1)
        payload = {"kind": "material", "content_b64": base64.b64encode(b"large").decode()}
    for _ in range(2):
        response = client.post(
            "/v1/kb/ingest", headers={"authorization": f"Bearer {_token()}"}, json=payload,
        )
        assert response.status_code == status, response.text
        assert response.json()["detail"]["code"] == code
        rows = _usage_rows(tmp_path)
        assert len(rows) == 1
        assert rows[0]["source"] == "kb_ingest"
        assert rows[0]["tokens_unknown"] == 1


def test_ingest_unavailable_without_principal_skips_usage(client, monkeypatch, tmp_path):
    from app.edu_kb_ingest import IngestIn, post_kb_ingest
    from fastapi import HTTPException

    monkeypatch.setitem(sys.modules, "ingest", None)
    with pytest.raises(HTTPException) as caught:
        client.portal.call(post_kb_ingest, IngestIn(text="hello"), None)
    assert caught.value.status_code == 503
    assert _usage_rows(tmp_path) == []


def test_ingest_ledger_failure_does_not_break_success(client, monkeypatch):
    import ingest as ingest_mod
    from app import usage_ledger

    monkeypatch.setattr(
        ingest_mod, "ingest_text", lambda **kwargs: {"ok": True, "slices": [{"excerpt": "hello"}]},
    )

    async def unavailable(**kwargs):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(usage_ledger, "_record_usage_event_inner", unavailable)
    response = client.post(
        "/v1/kb/ingest", headers={"authorization": f"Bearer {_token()}"}, json={"text": "hello"},
    )
    assert response.status_code == 200, response.text


def test_search_uses_principal_not_body_and_returns_chunks(client, monkeypatch) -> None:
    captured: dict = {}

    def fake_search(query, *, school_id, membership_id, limit, include_school=False, client=None, rerank_ok=True):
        captured["query"] = query
        captured["school_id"] = school_id
        captured["membership_id"] = membership_id
        captured["limit"] = limit
        captured["include_school"] = include_school
        _ = client
        return {
            "hybrid": False,
            "hits": [
                {
                    "chunk_id": "art-1_0000",
                    "artifact_id": "art-1",
                    "material_id": "art-1",
                    "title": "通知.pdf",
                    "heading": "培训安排",
                    "page": 2,
                    "text": "7月8日在景炎初级中学。",
                    "parent_text": "培训安排\n7月8日在景炎初级中学。",
                    "school_id": school_id,
                    "membership_id": membership_id,
                }
            ],
        }

    monkeypatch.setattr("app.edu_kb_ingest.search_materials", fake_search)
    res = client.post(
        "/v1/kb/search",
        headers={"authorization": f"Bearer {_token()}"},
        json={"query": "培训在哪", "limit": 5, "scope": "school"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert captured["school_id"] == "school-a"
    assert captured["membership_id"] == "m-edu"
    assert captured["query"] == "培训在哪"
    assert body["hits"][0]["heading"] == "培训安排"
    assert body["hits"][0]["page"] == 2
    assert body["mode"] == "keyword"
    assert captured["include_school"] is True
    assert body["include_school"] is True


def test_search_school_keeps_other_teacher_school_hit(client, monkeypatch) -> None:
    def fake_search(query, *, school_id, membership_id, limit, include_school=False, client=None, rerank_ok=True):
        _ = query, limit, client
        return {
            "hybrid": False,
            "hits": [
                {
                    "chunk_id": "edu-1_0000",
                    "artifact_id": "edu-1",
                    "material_id": "edu-1",
                    "title": "通知",
                    "heading": "培训",
                    "page": 1,
                    "text": "景炎",
                    "parent_text": "景炎",
                    "scope": "school",
                    "school_id": school_id,
                    "membership_id": "uploader-other",
                }
            ],
        }

    monkeypatch.setattr("app.edu_kb_ingest.search_materials", fake_search)
    res = client.post(
        "/v1/kb/search",
        headers={"authorization": f"Bearer {_token()}"},
        json={"query": "培训", "limit": 5, "scope": "school"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["count"] == 1
    assert res.json()["hits"][0]["artifact_id"] == "edu-1"


def test_ingest_writes_school_chunks(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod
    from app import edu_kb_ingest as kb

    captured: dict = {}

    monkeypatch.setattr(
        ingest_mod,
        "ingest_text",
        lambda **kwargs: {
            "ok": True,
            "engine": "text",
            "slices": [{"title": "通知", "excerpt": "培训在景炎初级中学。"}],
        },
    )

    def fake_upsert(docs, *, client=None, replace_artifact=True):
        captured["docs"] = docs
        captured["replace"] = replace_artifact
        _ = client
        return True

    monkeypatch.setattr(kb, "upsert_documents", fake_upsert)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={"title": "通知", "text": "培训在景炎初级中学。", "item_id": "edu-item-1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["item_id"] == "edu-item-1"
    assert body["indexed"] is True
    assert body["chunk_count"] >= 1
    assert captured["replace"] is True
    assert captured["docs"][0]["scope"] == "school"
    assert captured["docs"][0]["artifact_id"] == "edu-item-1"
    assert captured["docs"][0]["school_id"] == "school-a"


def test_ingest_indexes_full_markdown_not_eight_slices(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod
    from app import edu_kb_ingest as kb

    captured: dict = {}
    later = "行间距：固定值20磅。全文用宋体。"
    monkeypatch.setattr(
        ingest_mod,
        "ingest_text",
        lambda **kwargs: {
            "ok": True,
            "engine": "docling",
            "slices": [{"title": "附件", "excerpt": "附件1 文稿格式"}],
            "markdown": "# 附件1\n\n稿件内容一般应包括使用教材。\n\n" + later,
        },
    )

    def fake_upsert(docs, *, client=None, replace_artifact=True):
        captured["blob"] = " ".join(str(d.get("text") or "") for d in docs)
        _ = client, replace_artifact
        return True

    monkeypatch.setattr(kb, "upsert_documents", fake_upsert)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={"title": "附件", "text": "ignored", "item_id": "docx-full"},
    )
    assert res.status_code == 200, res.text
    assert later in captured["blob"]


def test_ingest_skips_noise_title(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod
    from app import edu_kb_ingest as kb

    called = {"n": 0}

    monkeypatch.setattr(
        ingest_mod,
        "ingest_text",
        lambda **kwargs: {
            "ok": True,
            "engine": "text",
            "slices": [{"title": "回复摘要", "excerpt": "不该进库"}],
        },
    )

    def boom(*args, **kwargs):
        called["n"] += 1
        return True

    monkeypatch.setattr(kb, "upsert_documents", boom)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={"title": "回复摘要", "text": "不该进库", "item_id": "noise-1"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["indexed"] is False
    assert res.json()["skip_reason"] == "noise"
    assert called["n"] == 0


def test_ingest_skips_lab_school_in_production(client: TestClient, monkeypatch) -> None:
    import ingest as ingest_mod
    from app import edu_kb_ingest as kb

    monkeypatch.setenv("PICO_ENV", "production")
    called = {"n": 0}
    monkeypatch.setattr(
        ingest_mod,
        "ingest_text",
        lambda **kwargs: {
            "ok": True,
            "engine": "text",
            "slices": [{"title": "hello", "excerpt": "world"}],
        },
    )
    monkeypatch.setattr(kb, "upsert_documents", lambda *a, **k: called.__setitem__("n", 1) or True)
    res = client.post(
        "/v1/kb/ingest",
        headers={"authorization": f"Bearer {_token()}"},
        json={"title": "hello", "text": "world", "item_id": "lab-1"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["indexed"] is False
    assert res.json()["skip_reason"] == "lab"
    assert called["n"] == 0


def test_kb_item_status(client: TestClient, monkeypatch) -> None:
    from app import edu_kb_ingest as kb

    monkeypatch.setattr(kb, "count_material", lambda *a, **k: 4)
    res = client.get(
        "/v1/kb/items/edu-item-1",
        headers={"authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["item_id"] == "edu-item-1"
    assert body["chunk_count"] == 4
    assert body["ready"] is True
    assert body["scope"] == "school"
