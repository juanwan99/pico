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


def _body_for_tool(tool: str, marker: str) -> str:
    """题面正文 for generate_*; short stubs now fail closed (no generator padding)."""
    if tool == "generate_docx_document":
        return (
            f"各位家长：本周五（3月14日）下午两点在教学楼三层三年级二班教室召开本学期家长会（{marker}），"
            "请准时到场，并带好孩子的期末成绩单、家校联系册和课外阅读记录。签到从一点五十分开始。\n\n"
            "会议内容按顺序进行：先通报本班期中以来的学习与纪律情况，再讲作业习惯与家庭辅导建议，"
            "然后说明下学期课程、值日、校服与收费事项，最后留二十分钟个别交流。"
            "请提前十分钟入场，手机调至静音，中途如需接听请到走廊。\n\n"
            "如有事不能参加，请当天中午十二点前在班级群私信班主任请假并注明由哪位家长代到。"
            "三年级二班班主任。教室路线、签到表与座位图见班级群置顶。"
            "会后请在本周日晚八点前把家庭作业时间安排发给老师，便于下周跟进错题订正。"
            "雨天请走东门电梯，自行车请停在教学楼北侧车棚。"
        )
    if tool == "generate_pptx_document":
        return (
            f"开场：{marker} 培训目标是把课堂常规讲清。\n\n---\n\n"
            "中段：候课、提问、收本三项示范。\n\n---\n\n"
            "收尾：下周听课跟进并约定第二次时间。"
        )
    return f"body for {marker}"


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
        {"title": title, "marker": marker, "body": _body_for_tool(tool, marker)},
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


def test_office_preview_returns_content_box_html(client) -> None:
    headers = _headers(client)
    created = _invoke(
        client,
        headers,
        "generate_pptx_document",
        {
            "title": "preview.pptx",
            "marker": "PREVIEW-BOX-1",
            "body": _body_for_tool("generate_pptx_document", "PREVIEW-BOX-1"),
        },
    )
    assert created.status_code == 200, created.text
    artifact_id = created.json()["result"]["artifact_id"]
    preview = client.get(
        f"/v1/artifacts/{artifact_id}/content?preview=1",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert "text/html" in (preview.headers.get("content-type") or "")
    assert preview.headers.get("x-pico-preview") == "office-content-box"
    body = preview.text
    assert "slide" in body
    assert "LibreOffice" not in body
    assert "Impress" not in body
    raw = client.get(
        f"/v1/artifacts/{artifact_id}/content?download=true",
        headers=headers,
    )
    assert raw.status_code == 200
    assert "application/vnd.openxmlformats" in (raw.headers.get("content-type") or "")


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
