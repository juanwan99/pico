from __future__ import annotations

import base64
import io
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import issue_test_token
from app.main import app
from app.settings import get_settings


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    shared: list[str] = []
    cells_xml: list[str] = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, val in enumerate(row):
            idx = len(shared)
            shared.append(val)
            col = chr(ord("A") + c)
            parts.append(f'<c r="{col}{r}" t="s"><v>{idx}</v></c>')
        cells_xml.append(f'<row r="{r}">{"".join(parts)}</row>')
    sst = "".join(f"<si><t>{escape(s)}</t></si>" for s in shared)
    sheet_xml = (
        '<?xml version="1.0"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(cells_xml)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="课时" sheetId="1" r:id="rId1" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        "</sheets></workbook>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{sst}</sst>",
        )
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "edu-files.db"
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


def test_post_files_requires_bearer(client: TestClient) -> None:
    res = client.post("/v1/files", json={"filename": "a.csv", "content_b64": "YQ=="})
    assert res.status_code == 401


def test_post_and_get_xlsx_excerpt(client: TestClient) -> None:
    raw = _xlsx_bytes([["班", "周课时"], ["一班", "5"]])
    token = _token()
    res = client.post(
        "/v1/files",
        headers={"authorization": f"Bearer {token}"},
        json={
            "filename": "课时.xlsx",
            "content_b64": base64.b64encode(raw).decode("ascii"),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body["headline"] == "读到 2 行 / 2 列"
    assert body["id"]
    got = client.get(
        f"/v1/files/{body['id']}",
        headers={"authorization": f"Bearer {token}"},
    )
    assert got.status_code == 200
    assert got.json()["headline"] == "读到 2 行 / 2 列"


def test_post_pptx_persists_original_bytes(client: TestClient) -> None:
    from pptx import Presentation

    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[0])
    slide.shapes.title.text = "封面"
    buf = io.BytesIO()
    deck.save(buf)
    raw = buf.getvalue()
    token = _token()
    res = client.post(
        "/v1/files",
        headers={"authorization": f"Bearer {token}"},
        json={
            "filename": "封面.pptx",
            "content_b64": base64.b64encode(raw).decode("ascii"),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body["id"]
    assert "页" in body["headline"]


def test_foreign_membership_cannot_read(client: TestClient) -> None:
    raw = _xlsx_bytes([["a", "b"]])
    owner = _token()
    posted = client.post(
        "/v1/files",
        headers={"authorization": f"Bearer {owner}"},
        json={
            "filename": "课时.xlsx",
            "content_b64": base64.b64encode(raw).decode("ascii"),
        },
    )
    file_id = posted.json()["id"]
    other = issue_test_token(
        school_id="school-a",
        membership_id="m-other",
        scopes=["ai:read"],
        settings=get_settings(),
    )
    res = client.get(
        f"/v1/files/{file_id}",
        headers={"authorization": f"Bearer {other}"},
    )
    assert res.status_code == 404
