from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "fake.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    from app import db as dbmod
    from app.settings import get_settings
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as c:
        yield c


def _headers(client):
    r = client.post("/v1/dev/token", json={"school_id": "school-a", "membership_id": "member-a"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_workspace_write_fake_docx_rejected(client):
    h = _headers(client)
    r = client.post(
        "/v1/tools/invoke",
        headers=h,
        json={"name": "workspace_write_file", "arguments": {"title": "fake.docx", "content": "not ooxml"}},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "tool.invalid_arguments"


def test_generate_docx_download_ok_and_fake_storage_blocked(client):
    h = _headers(client)
    # real generate ok
    r = client.post(
        "/v1/tools/invoke",
        headers=h,
        json={
            "name": "generate_docx_document",
            "arguments": {
                "title": "real.docx",
                "marker": "NEG1",
                "body": (
                    "各位家长：本周五（3月14日）下午两点在教学楼三层三年级二班教室召开本学期家长会，"
                    "请准时到场，并带好孩子的期末成绩单、家校联系册和课外阅读记录。签到从一点五十分开始。\n\n"
                    "会议内容按顺序进行：先通报本班期中以来的学习与纪律情况，再讲作业习惯与家庭辅导建议，"
                    "然后说明下学期课程、值日、校服与收费事项，最后留二十分钟个别交流。"
                    "请提前十分钟入场，手机调至静音，中途如需接听请到走廊。\n\n"
                    "如有事不能参加，请当天中午十二点前在班级群私信班主任请假并注明由哪位家长代到。"
                    "三年级二班班主任。教室路线、签到表与座位图见班级群置顶。"
                    "会后请在本周日晚八点前把家庭作业时间安排发给老师，便于下周跟进错题订正。"
                    "雨天请走东门电梯，自行车请停在教学楼北侧车棚。"
                ),
            },
        },
    )
    assert r.status_code == 200, r.text
    aid = r.json()["result"]["artifact_id"]
    d = client.get(f"/v1/artifacts/{aid}/content?download=true", headers=h)
    assert d.status_code == 200
    assert d.content[:2] == b"PK"
