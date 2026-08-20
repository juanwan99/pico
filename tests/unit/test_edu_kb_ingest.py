from __future__ import annotations

import base64
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
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client


def _token() -> str:
    return issue_test_token(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
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
