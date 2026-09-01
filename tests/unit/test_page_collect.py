"""T-PAGE-COLLECT-LAND: land envelope is named ids + artifact id, not invented."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import Principal, issue_test_token
from app.edu_school import LandBody, build_land_payload, land_generated_artifact
from app.page_collect import attach_page_collect, sanitize_collect_fields, sanitize_uuid_list
from app.settings import get_settings


ITEM_A = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
ITEM_B = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"
ART = "cccccccc-dddd-4eee-8fff-000000000000"


def test_sanitize_uuid_list_drops_junk() -> None:
    assert sanitize_uuid_list([ITEM_A, "nope", ITEM_A, ITEM_B]) == [ITEM_A, ITEM_B]
    assert sanitize_uuid_list("not-a-list") == []


def test_collect_fields_ref_must_be_named() -> None:
    fields = sanitize_collect_fields(
        [
            {"key": "q1", "ref": ITEM_A, "value_kind": "string"},
            {"key": "q2", "ref": "dddddddd-eeee-4fff-8aaa-111111111111", "value_kind": "string"},
            {"key": "", "value_kind": "string"},
            {"key": "q1", "value_kind": "string"},
        ],
        source_item_ids=[ITEM_A],
    )
    assert fields == [{"key": "q1", "value_kind": "string", "ref": ITEM_A}]


def test_attach_always_sets_source_item_ids() -> None:
    empty = attach_page_collect({})
    assert empty["source_item_ids"] == []
    assert "pico_artifact_id" not in empty
    filled = attach_page_collect(
        {},
        source_item_ids=[ITEM_A, "nope"],
        pico_artifact_id=ART,
        collect_fields=[{"key": "ans", "ref": ITEM_A}],
    )
    assert filled["source_item_ids"] == [ITEM_A]
    assert filled["pico_artifact_id"] == ART
    assert filled["collect_fields"][0]["key"] == "ans"


def test_build_land_payload_copies_named_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/page-collect.db")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    from app.db import init_db, session_factory
    from app.edu_school import remember_named_ids
    from app.settings import get_settings as gs

    gs.cache_clear()
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> dict:
        await init_db()
        factory = session_factory()
        async with factory() as session:
            await remember_named_ids(session, "school-a", "m-edu", "c-land", [ITEM_A, ITEM_B], "")
            return await build_land_payload(
                principal,
                LandBody(
                    conversation_id="c-land",
                    filename="页.html",
                    body_html="<p>灰</p>",
                    pico_artifact_id=ART,
                ),
                session,
            )

    payload = asyncio.run(_run())
    assert payload["source_item_ids"] == [ITEM_A, ITEM_B]
    assert payload["pico_artifact_id"] == ART
    assert payload["body_html"] == "<p>灰</p>"
    gs.cache_clear()


def test_build_land_payload_empty_named_is_honest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/page-collect-empty.db")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    from app.db import init_db, session_factory
    from app.settings import get_settings as gs

    gs.cache_clear()
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> dict:
        await init_db()
        factory = session_factory()
        async with factory() as session:
            return await build_land_payload(
                principal,
                LandBody(conversation_id="c-none", filename="页.html", body_html="<p>灰</p>"),
                session,
            )

    payload = asyncio.run(_run())
    assert payload["source_item_ids"] == []
    assert "pico_artifact_id" not in payload
    gs.cache_clear()


def test_land_generated_sends_named_and_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/page-collect-gen.db")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "https://edu.example")
    from app import edu_school as mod
    from app.db import init_db, session_factory
    from app.edu_school import remember_named_ids
    from app.settings import get_settings as gs

    gs.cache_clear()
    captured: dict = {}

    async def fake_call(principal, method, path, *, params=None, body=None, settings=None, write=False):
        _ = principal, method, params, settings, write
        captured["path"] = path
        captured["body"] = dict(body or {})
        return {
            "ok": True,
            "landed": True,
            "green": False,
            "kind": "page",
            "id": "eeeeeeee-ffff-4aaa-8bbb-222222222222",
            "field_id": ITEM_A,
            "title": "页",
            "publish_state": "draft",
        }

    monkeypatch.setattr(mod, "_edu_call", fake_call)
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> dict:
        await init_db()
        factory = session_factory()
        async with factory() as session:
            await remember_named_ids(session, "school-a", "m-edu", "c-xfer", [ITEM_B], "")
            return await land_generated_artifact(
                principal,
                title="页.html",
                content="<p>灰</p>",
                field_id=ITEM_A,
                conversation_id="c-xfer",
                artifact_id=ART,
                task_id=ITEM_A,
                session=session,
            )

    body = asyncio.run(_run())
    assert captured["path"] == "/v1/pico/membership/land"
    assert captured["body"]["source_item_ids"] == [ITEM_B]
    assert captured["body"]["pico_artifact_id"] == ART
    assert captured["body"]["pico_task_id"] == ITEM_A
    assert captured["body"]["filename"] == "页.html"
    assert body["landed"] is True
    assert body["green"] is False
    assert body["source_item_ids"] == [ITEM_B]
    assert body["pico_artifact_id"] == ART
    gs.cache_clear()


def test_land_http_echoes_empty_named(tmp_path, monkeypatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/page-collect-http.db")
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
    token = issue_test_token(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        settings=get_settings(),
    )
    with TestClient(app) as client:
        res = client.post(
            "/v1/edu/land",
            json={"filename": "页.html", "body_html": "<p>灰</p>", "conversation_id": "c1"},
            headers={"Authorization": f"Bearer {token}", "X-Pico-Membership-Id": "school-a:m-edu"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("configured") is False
    assert body.get("source_item_ids") == []
    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()
