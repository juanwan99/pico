"""T-PICO-EDU-READ: named school materials only; no whole-school dump."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import issue_test_token
from app.edu_school import classify_land_kind, inject_named_school_materials, sanitize_field_id
from app.edu_sso import sanitize_display_name
from app.settings import get_settings


def test_inject_named_is_noop_when_nothing_checked() -> None:
    prompt = "根据学校文件总结"
    assert inject_named_school_materials(prompt, []) == prompt
    assert inject_named_school_materials(prompt, None) == prompt
    assert "已点名" not in inject_named_school_materials(prompt, [])


def test_inject_named_cites_checked_excerpts_only() -> None:
    prompt = "根据学校文件总结"
    out = inject_named_school_materials(
        prompt,
        [
            {
                "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                "title": "课时表",
                "excerpt": "高一语文 5 节",
            }
        ],
    )
    assert "课时表" in out
    assert "高一语文 5 节" in out
    assert "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee" in out
    assert out.endswith(prompt)
    assert "未勾选" in out


def test_display_name_rejects_hardcoded_school_account() -> None:
    assert sanitize_display_name("学校账号") == ""
    assert sanitize_display_name("  孙骏博  ") == "孙骏博"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/edu-named.db")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "")
    from app import db as dbmod
    from app.edu_school import router
    from app.settings import get_settings as gs

    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client
    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()


def _token() -> str:
    return issue_test_token(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        settings=get_settings(),
    )


def test_named_bind_roundtrip_does_not_store_bodies(client) -> None:
    item = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    put = client.put(
        "/v1/edu/named",
        json={"conversation_id": "c1", "ids": [item, "nope"]},
        headers={"Authorization": f"Bearer {_token()}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert put.status_code == 200, put.text
    assert put.json()["ids"] == [item]
    assert put.json()["dumped"] is False
    got = client.get(
        "/v1/edu/named",
        params={"conversation_id": "c1"},
        headers={"Authorization": f"Bearer {_token()}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert got.status_code == 200
    assert got.json()["ids"] == [item]


def test_named_bind_stores_field_id(client) -> None:
    field = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    put = client.put(
        "/v1/edu/named",
        json={"conversation_id": "c1", "ids": [], "field_id": field},
        headers={"Authorization": f"Bearer {_token()}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert put.status_code == 200, put.text
    assert put.json()["field_id"] == field
    got = client.get(
        "/v1/edu/named",
        params={"conversation_id": "c1"},
        headers={"Authorization": f"Bearer {_token()}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert got.json()["field_id"] == field


def test_classify_land_kind_routes_html_and_office() -> None:
    assert classify_land_kind("页.html") == "page"
    assert classify_land_kind("报告.docx") == "material"
    assert classify_land_kind("表.xlsx") == "material"
    assert classify_land_kind("图.png") == "skip"
    assert classify_land_kind("笔记.txt") is None
    assert sanitize_field_id("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
    assert sanitize_field_id("nope") == ""


def test_land_without_edu_base_does_not_pretend(client) -> None:
    res = client.post(
        "/v1/edu/land",
        json={"filename": "页.html", "body_html": "<p>灰</p>"},
        headers={"Authorization": f"Bearer {_token()}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("configured") is False
    assert body.get("landed") is False
    assert body.get("dumped") is False


def test_search_green_library_unconfigured_is_honest(monkeypatch) -> None:
    from app.auth import Principal
    from app.edu_school import search_green_library
    from app.settings import get_settings as gs

    monkeypatch.setenv("PICO_EDU_BASE_URL", "")
    monkeypatch.setenv("PICO_ENV", "development")
    gs.cache_clear()
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> None:
        data = await search_green_library(principal, query="校历")
        assert data["configured"] is False
        assert data["items"] == []
        assert data["dumped"] is False

    import asyncio

    asyncio.run(_run())
    gs.cache_clear()


def test_search_green_library_maps_membership_items(monkeypatch) -> None:
    from app import edu_school as mod
    from app.auth import Principal
    from app.edu_school import search_green_library

    async def fake_get(principal, path, *, params=None, settings=None):
        _ = principal, settings
        assert path == "/v1/pico/membership/search"
        assert params == {"q": "校历"}
        return {
            "configured": True,
            "dumped": False,
            "items": [
                {
                    "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    "title": "校历",
                    "excerpt": "三月开学",
                }
            ],
        }

    monkeypatch.setattr(mod, "_edu_get", fake_get)
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> None:
        data = await search_green_library(principal, query="校历")
        assert data["configured"] is True
        assert data["items"][0]["title"] == "校历"
        assert data["dumped"] is False

    import asyncio

    asyncio.run(_run())


def test_materials_without_edu_base_does_not_dump(client) -> None:
    res = client.get(
        "/v1/edu/materials",
        params={"q": "课时"},
        headers={"Authorization": f"Bearer {_token()}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("items") == []
    assert body.get("dumped") is False
    assert body.get("configured") is False
