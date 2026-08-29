"""T-SANDBOX-PERSIST: kill session, file stays; ACL; reopen body."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from sandbox_worker.runtime import RUNTIME


class _FakeOffice:
    def __init__(self, filename: str, document: bytes) -> None:
        self.filename = filename
        self.document = document
        self.url = f"sandbox://writer/{filename}"

    async def title(self) -> str:
        return f"LibreOffice Writer · {self.filename}"

    async def h1(self) -> str:
        return self.filename

    async def screenshot_png(self) -> bytes:
        from pico_orchestrator.sandbox_s2 import encode_rgb_png
        from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_WIDTH

        return encode_rgb_png(
            VIEWPORT_WIDTH,
            VIEWPORT_HEIGHT,
            bytes((240, 240, 240)) * (VIEWPORT_WIDTH * VIEWPORT_HEIGHT),
        )

    async def click(self, x: int, y: int) -> None:
        return None

    async def type_text(self, text: str, *, password: bool) -> None:
        return None

    async def close(self) -> None:
        return None

    async def render(self, names) -> None:
        self.names = names


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "persist.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")

    async def fake_office(*, kind: str, filename: str, document: bytes):
        _ = kind
        return _FakeOffice(filename, document)

    import sandbox_worker.runtime as runtime_mod

    monkeypatch.setattr(runtime_mod, "open_office", fake_office)
    RUNTIME._sessions.clear()

    from app import db as dbmod
    from app.main import app
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client
    RUNTIME._sessions.clear()


def _headers(client: TestClient, membership_id: str, school_id: str = "school-a") -> dict[str, str]:
    response = client.post(
        "/v1/dev/token",
        json={"school_id": school_id, "membership_id": membership_id},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_t1_t2_t3_persist_after_destroy(client) -> None:
    unique = "persist-t1-unique.docx"
    marker = "PERSIST-BODY-UNIQUE"
    owner = _headers(client, "member-a")
    other = _headers(client, "member-b")

    opened = client.post(
        "/v1/sandbox/sessions",
        headers=owner,
        json={"kind": "writer", "filename": unique, "body": marker},
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body.get("view") == "content-box"
    assert body.get("artifact_id")
    assert "LibreOffice" not in str(body.get("human_copy") or "")
    assert not str(body.get("session_id") or "").startswith("sbox_")

    disk = client.get("/v1/sandbox/disk", headers=owner)
    assert disk.status_code == 200, disk.text
    names = [f["name"] for f in disk.json().get("files") or []]
    assert unique in names

    files = client.post(
        "/v1/sandbox/sessions",
        headers=owner,
        json={"kind": "files"},
    )
    assert files.status_code == 200, files.text
    assert any(f["name"] == unique for f in files.json().get("files") or [])
    sid = files.json()["session_id"]
    assert sid.startswith("sbox_")

    closed = client.delete(f"/v1/sandbox/sessions/{sid}", headers=owner)
    assert closed.status_code == 200, closed.text
    assert closed.json()["destroyed"] is True
    assert closed.json()["persist"] is True
    gone = client.get(f"/v1/sandbox/sessions/{sid}", headers=owner)
    assert gone.status_code == 404
    still = client.get("/v1/sandbox/disk", headers=owner)
    assert unique in [f["name"] for f in still.json().get("files") or []]

    reopen = client.post(
        "/v1/sandbox/sessions",
        headers=owner,
        json={"kind": "writer", "filename": unique},
    )
    assert reopen.status_code == 200, reopen.text
    assert reopen.json().get("view") == "content-box"
    assert unique in (reopen.json().get("title") or reopen.json().get("filename") or "")
    from pico_orchestrator.sandbox_persist import read_owner_disk_file

    persisted = read_owner_disk_file("school-a", "member-a", unique)
    assert persisted[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(persisted)) as zf:
        xml = zf.read("word/document.xml")
    assert marker.encode() in xml

    other_disk = client.get("/v1/sandbox/disk", headers=other)
    assert other_disk.status_code == 200, other_disk.text
    other_names = [f["name"] for f in other_disk.json().get("files") or []]
    assert unique not in other_names

    files_again = client.post(
        "/v1/sandbox/sessions",
        headers=owner,
        json={"kind": "files"},
    )
    stolen = client.get(
        f"/v1/sandbox/sessions/{files_again.json()['session_id']}", headers=other
    )
    assert stolen.status_code in {403, 404}

    wipe = client.post("/v1/sandbox/disk/clear", headers=owner, json={"confirm": False})
    assert wipe.status_code == 400
    wiped = client.post("/v1/sandbox/disk/clear", headers=owner, json={"confirm": True})
    assert wiped.status_code == 200, wiped.text
    empty = client.get("/v1/sandbox/disk", headers=owner)
    assert unique not in [f["name"] for f in empty.json().get("files") or []]
