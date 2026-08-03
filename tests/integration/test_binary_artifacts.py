from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "binary-artifacts.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")

    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, membership_id: str = "member-a") -> dict[str, str]:
    response = client.post(
        "/v1/dev/token",
        json={"school_id": "school-a", "membership_id": membership_id},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _invoke(client: TestClient, headers: dict[str, str], name: str, arguments: dict):
    return client.post(
        "/v1/tools/invoke",
        headers=headers,
        json={"name": name, "arguments": arguments},
    )


@pytest.mark.parametrize(
    "tool,title,marker,ext,mime_part,zip_paths",
    [
        (
            "generate_html_document",
            "lesson.html",
            "P270_I_HTML",
            ".html",
            "text/html",
            None,
        ),
        (
            "generate_docx_document",
            "lesson.docx",
            "P270_I_DOCX",
            ".docx",
            "wordprocessingml",
            ("[Content_Types].xml", "word/document.xml"),
        ),
        (
            "generate_pptx_document",
            "lesson.pptx",
            "P270_I_PPTX",
            ".pptx",
            "presentationml",
            ("[Content_Types].xml", "ppt/presentation.xml", "ppt/slides/slide1.xml"),
        ),
    ],
)
def test_generate_and_download_bytes_safe(
    client, tool, title, marker, ext, mime_part, zip_paths
) -> None:
    headers = _headers(client)
    created = _invoke(
        client,
        headers,
        tool,
        {"title": title, "marker": marker, "body": f"body for {marker}"},
    )
    assert created.status_code == 200, created.text
    result = created.json()["result"]
    artifact_id = result["artifact_id"]
    assert result["title"].endswith(ext)
    assert result["content_encoding"] in {"utf8", "base64"}
    if ext in {".docx", ".pptx"}:
        assert result["content_encoding"] == "base64"
    assert result["byte_size"] > 0
    assert len(result["content_sha256"]) == 64

    content = client.get(
        f"/v1/artifacts/{artifact_id}/content?download=true",
        headers=headers,
    )
    assert content.status_code == 200, content.text
    raw = content.content
    assert hashlib.sha256(raw).hexdigest() == result["content_sha256"]
    assert len(raw) == result["byte_size"]
    assert mime_part in (content.headers.get("content-type") or "")

    if zip_paths:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
            for path in zip_paths:
                assert path in names
            # Marker lives inside compressed parts — verify via parse, not raw ZIP bytes.
            blob = b"".join(zf.read(name) for name in zf.namelist())
            assert marker.encode("utf-8") in blob
    else:
        assert marker.encode("utf-8") in raw

    task = client.get(f"/v1/tasks/{result['task_id']}", headers=headers)
    assert task.status_code == 200
    art = task.json()["artifacts"][0]
    assert art["id"] == artifact_id
    assert art["content_sha256"] == result["content_sha256"]
    if result["content_encoding"] == "base64":
        assert art["inline"] is None


def test_text_workspace_write_still_utf8(client) -> None:
    headers = _headers(client)
    created = _invoke(
        client,
        headers,
        "workspace_write_file",
        {"title": "note.txt", "content": "hello-utf8", "kind": "file"},
    )
    assert created.status_code == 200, created.text
    result = created.json()["result"]
    assert result["content_encoding"] == "utf8"
    content = client.get(
        f"/v1/artifacts/{result['artifact_id']}/content?download=true",
        headers=headers,
    )
    assert content.content == b"hello-utf8"
