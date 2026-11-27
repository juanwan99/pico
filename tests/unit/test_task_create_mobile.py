from __future__ import annotations

import base64
import io
import sqlite3
from uuid import UUID

import pytest
from app import db, run_service
from app.auth import issue_test_token
from app.main import app
from app.settings import get_settings
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "tasks.db"
    # Start with the old tasks schema and an existing task.
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE tasks (
                id VARCHAR(36) PRIMARY KEY, school_id VARCHAR(128), membership_id VARCHAR(128),
                title VARCHAR(512), conversation_id VARCHAR(128), workspace_id VARCHAR(36),
                created_at DATETIME, updated_at DATETIME
            );
            INSERT INTO tasks (id, school_id, membership_id, title)
            VALUES ('old-task', 'school-a', 'teacher-a', '旧任务');
        """)
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    get_settings.cache_clear()
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_Session", None)

    async def no_background(*_args):
        pass

    monkeypatch.setattr(run_service, "start_run_background", no_background)
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def _headers(school="school-a", member="teacher-a", scopes=None):
    token = issue_test_token(school_id=school, membership_id=member, scopes=scopes)
    return {"Authorization": f"Bearer {token}"}


def _upload(client, headers, filename="photo.png"):
    if filename.endswith(".png"):
        buf = io.BytesIO()
        Image.new("RGB", (2, 2)).save(buf, format="PNG")
        raw = buf.getvalue()
    else:
        raw = b"notes"
    response = client.post(
        "/v1/files",
        headers=headers,
        json={"filename": filename, "content_b64": base64.b64encode(raw).decode()},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _tasks(client, headers, **params):
    response = client.get("/v1/tasks", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["tasks"]


@pytest.mark.parametrize("upload_fields", [{}, {"upload_ids": []}])
def test_mobile_task_persists_source_and_uuid(client, upload_fields):
    headers = _headers()
    response = client.post(
        "/v1/tasks", headers=headers, json={"prompt": "整理会议纪要", "source": "mobile", **upload_fields}
    )
    assert response.status_code == 200, response.text
    task = response.json()["task"]
    cid = task["conversation_id"]
    assert cid is not None and UUID(cid).version == 4
    assert task["source"] == "mobile"
    assert _tasks(client, headers, conversation_id=cid)[0]["source"] == "mobile"
    detail = client.get(f"/v1/tasks/{task['id']}", headers=headers).json()["task"]
    assert detail["source"] == "mobile"
    assert detail["conversation_id"] == cid
    assert _tasks(client, _headers(member="teacher-b"), conversation_id=cid) == []
    assert _tasks(client, _headers(school="school-b"), conversation_id=cid) == []


@pytest.mark.parametrize("upload_fields", [{}, {"upload_ids": []}])
def test_legacy_task_keeps_null_conversation(client, upload_fields):
    headers = _headers()
    response = client.post("/v1/tasks", headers=headers, json={"prompt": "整理", **upload_fields})
    assert response.status_code == 200, response.text
    task, run = response.json()["task"], response.json()["run"]
    assert task["conversation_id"] is None
    assert run["task_id"] == task["id"]
    assert run["status"] == "queued"
    assert run["prompt"] == task["title"] == "整理"


def test_task_schema_migrates_existing_rows(client):
    task = client.get("/v1/tasks/old-task", headers=_headers()).json()["task"]
    assert task["title"] == "旧任务"
    assert task["source"] is None
    assert task["conversation_id"] is None


@pytest.mark.parametrize("invalid", ["other-member", "other-school", "non-image", "missing", "nine"])
def test_invalid_upload_rejects_whole_task(client, invalid):
    headers = _headers()
    good = _upload(client, headers)
    invalid_ids = {
        "other-member": lambda: [_upload(client, _headers(member="teacher-b"))],
        "other-school": lambda: [_upload(client, _headers(school="school-b"))],
        "non-image": lambda: [_upload(client, headers, "notes.txt")],
        "missing": lambda: ["missing-upload-id"],
        "nine": lambda: [_upload(client, headers, f"photo-{i}.png") for i in range(8)],
    }[invalid]()
    before = _tasks(client, headers)
    response = client.post(
        "/v1/tasks",
        headers=headers,
        json={"prompt": "整理", "source": "mobile", "upload_ids": [good, *invalid_ids]},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "upload.invalid"
    if invalid != "nine":
        assert invalid_ids[-1] in response.json()["detail"]["message"]
    assert _tasks(client, headers) == before


def test_eight_photos_are_all_bound(client):
    headers = _headers()
    ids = [_upload(client, headers, f"photo-{i}.png") for i in range(8)]
    response = client.post(
        "/v1/tasks",
        headers=headers,
        json={"prompt": "整理", "source": "mobile", "upload_ids": ids},
    )
    assert response.status_code == 200, response.text
    cid = response.json()["task"]["conversation_id"]
    assert cid
    items = client.get("/v1/artifacts", headers=headers, params={"conversation_id": cid})
    assert {item["id"] for item in items.json()["artifacts"]} == set(ids)


def test_upload_requires_mobile_source(client):
    headers = _headers()
    photo = _upload(client, headers)
    before = _tasks(client, headers)
    response = client.post("/v1/tasks", headers=headers, json={"prompt": "整理", "upload_ids": [photo]})
    assert response.status_code == 400, response.text
    assert _tasks(client, headers) == before


@pytest.mark.parametrize("source", ["desktop", "", None, 1])
def test_invalid_source_is_bad_request(client, source):
    headers = _headers()
    before = _tasks(client, headers)
    response = client.post("/v1/tasks", headers=headers, json={"prompt": "整理", "source": source})
    assert response.status_code == 400, response.text
    assert _tasks(client, headers) == before


def test_read_only_principal_cannot_create_mobile_task(client):
    headers = _headers(scopes=["ai:read"])
    response = client.post("/v1/tasks", headers=headers, json={"prompt": "整理", "source": "mobile"})
    assert response.status_code == 403, response.text
    assert [task["id"] for task in _tasks(client, headers)] == ["old-task"]
