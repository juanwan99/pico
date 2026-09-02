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
    assert classify_land_kind("通知.pdf") == "material"
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
    assert body.get("source_item_ids") == []


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


def test_inject_includes_workspace_file_when_excerpt_present() -> None:
    out = inject_named_school_materials(
        "请看表",
        [
            {
                "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                "title": "课时表",
                "excerpt": "高一语文 5 节",
                "workspace_title": "课时表.xlsx",
                "workspace_artifact_id": "art-1",
            }
        ],
    )
    assert "高一语文 5 节" in out
    assert "本轮工作区文件名：课时表.xlsx" in out
    assert "art-1" in out


def test_named_item_text_reads_slices_and_nested() -> None:
    from app.edu_school import _named_item_bytes, _named_item_text

    assert _named_item_text({"slices": [{"excerpt": "三月开学"}]}) == "三月开学"
    assert _named_item_text({"item": {"body": "正文"}}) == "正文"
    assert _named_item_text({"excerpt": ""}) == ""
    blob = "A" * 80 + "=="
    assert _named_item_text({"content": blob}) == ""
    assert _named_item_bytes({"content": blob}) is not None


def test_promote_named_bind_copies_landing_ids(client) -> None:
    import asyncio

    from app.db import session_factory
    from app.edu_school import load_named_ids, promote_named_bind, remember_named_ids

    item = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    async def _run() -> None:
        from app.db import init_db

        await init_db()
        factory = session_factory()
        async with factory() as session:
            await remember_named_ids(session, "school-a", "m-edu", "", [item], "")
            got = await promote_named_bind(session, "school-a", "m-edu", "c-real")
            assert got == [item]
            assert await load_named_ids(session, "school-a", "m-edu", "c-real") == [item]

    asyncio.run(_run())


def test_excerpts_fill_from_item_when_bulk_excerpt_empty(client, monkeypatch) -> None:
    import asyncio

    from app import edu_school as mod
    from app.auth import Principal
    from app.db import session_factory
    from app.edu_school import excerpts_for_conversation, remember_named_ids

    item = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    async def fake_post(principal, path, *, body=None, settings=None):
        _ = principal, body, settings
        assert path == "/v1/pico/membership/excerpts"
        return {"items": [{"id": item, "title": "课时表", "excerpt": ""}]}

    async def fake_get(principal, path, *, params=None, settings=None):
        _ = principal, params, settings
        assert path.endswith(item)
        return {"id": item, "title": "课时表", "text": "一年级 42 人"}

    monkeypatch.setattr(mod, "_edu_post", fake_post)
    monkeypatch.setattr(mod, "_edu_get", fake_get)
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> None:
        from app.db import init_db

        await init_db()
        factory = session_factory()
        async with factory() as session:
            await remember_named_ids(session, "school-a", "m-edu", "c-real", [item], "")
            rows = await excerpts_for_conversation(principal, "c-real", session)
        assert len(rows) == 1
        assert "一年级 42 人" in rows[0]["excerpt"]
        assert rows[0]["unread"] is False
        injected = inject_named_school_materials("请看", rows)
        assert "一年级 42 人" in injected

    asyncio.run(_run())


def test_excerpts_office_bytes_go_through_file_pipeline(client, monkeypatch) -> None:
    import asyncio
    import base64

    from app import edu_school as mod
    from app.auth import Principal
    from app.db import session_factory
    from app.edu_school import excerpts_for_conversation, remember_named_ids

    item = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    payload = base64.b64encode("班,人数\n一班,42\n".encode()).decode("ascii")

    async def fake_post(principal, path, *, body=None, settings=None):
        _ = principal, path, body, settings
        return {"items": [{"id": item, "title": "人数表", "excerpt": ""}]}

    async def fake_get(principal, path, *, params=None, settings=None):
        _ = principal, path, params, settings
        return {
            "id": item,
            "title": "人数表",
            "filename": "人数表.csv",
            "content_b64": payload,
        }

    monkeypatch.setattr(mod, "_edu_post", fake_post)
    monkeypatch.setattr(mod, "_edu_get", fake_get)
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> None:
        from app.db import init_db

        await init_db()
        factory = session_factory()
        async with factory() as session:
            await remember_named_ids(session, "school-a", "m-edu", "c-csv", [item], "")
            rows = await excerpts_for_conversation(principal, "c-csv", session)
        assert rows[0]["workspace_title"] == "人数表.csv"
        assert rows[0]["workspace_artifact_id"]
        injected = inject_named_school_materials("请看", rows)
        assert "人数表.csv" in injected
        assert "artifact_id" in injected

    asyncio.run(_run())


def test_excerpts_still_lists_named_when_excerpts_http_fails(client, monkeypatch) -> None:
    import asyncio

    from app import edu_school as mod
    from app.auth import Principal
    from app.db import session_factory
    from app.edu_school import excerpts_for_conversation, remember_named_ids
    from fastapi import HTTPException

    item = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    async def fake_post(principal, path, *, body=None, settings=None):
        _ = principal, path, body, settings
        raise HTTPException(status_code=502, detail="down")

    async def fake_get(principal, path, *, params=None, settings=None):
        _ = principal, params, settings
        return {"id": item, "title": "课时表", "body": "全文明细"}

    monkeypatch.setattr(mod, "_edu_post", fake_post)
    monkeypatch.setattr(mod, "_edu_get", fake_get)
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> None:
        from app.db import init_db

        await init_db()
        factory = session_factory()
        async with factory() as session:
            await remember_named_ids(session, "school-a", "m-edu", "", [item], "")
            rows = await excerpts_for_conversation(principal, "c-from-landing", session)
        assert rows[0]["id"] == item
        assert "全文明细" in rows[0]["excerpt"]

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
