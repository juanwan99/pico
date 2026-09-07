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
        ("docling", 503, "ingest.docling_missing"),
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
