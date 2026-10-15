"""pico#1298: files Pico makes are drafts, not library material.

They are written with origin "pico" and never projected into the school
library; kb_search drops drafts indexed before this change. The teacher's own
uploads keep landing in the library as before.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import Principal
from app.db import is_teacher_material


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'p.db'}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    from app import db as dbmod
    from app.settings import get_settings

    dbmod._engine = None
    dbmod._Session = None
    get_settings.cache_clear()
    asyncio.run(dbmod.init_db())
    yield dbmod
    dbmod._engine = None
    dbmod._Session = None
    get_settings.cache_clear()


def _principal() -> Principal:
    return Principal(
        school_id="school-a",
        membership_id="m-a",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )


def test_is_teacher_material() -> None:
    assert is_teacher_material("upload", "anything")
    assert not is_teacher_material("pico", "edu-read · a.docx")
    assert is_teacher_material("", "edu-read · a.docx")  # before #1298
    assert not is_teacher_material("", "做一份浮力讲义")  # before #1298


def test_pico_write_is_a_draft_and_upload_is_material(ledger, monkeypatch) -> None:
    from app import edu_files
    from app.artifact_store import LedgerArtifactStore, pico_draft_ids

    projected: list[str] = []

    def record(_principal: Any, *, artifact_id: str, **_kw: Any) -> bool:
        projected.append(artifact_id)
        return True

    monkeypatch.setattr("pico_orchestrator.meili_kb.project_material_artifact", record)
    monkeypatch.setattr(edu_files, "project_material_artifact", record)

    async def _go() -> tuple[str, str]:
        store = LedgerArtifactStore(ledger.session_factory())
        made = await store.write(_principal(), title="讲义.docx", content=b"PK\x03\x04", kind="docx")
        up = await edu_files.persist_edu_file(
            _principal(),
            filename="校历.md",
            data="春季学期 3 月 1 日开学".encode(),
            extract={"kind": "md", "text": "春季学期 3 月 1 日开学", "status": "ok"},
        )
        return str(made["artifact_id"]), up

    made_id, up_id = asyncio.run(_go())
    assert made_id not in projected
    assert up_id in projected
    drafts = asyncio.run(pico_draft_ids([made_id, up_id, "edu-material-1"]))
    assert drafts == {made_id}


def test_kb_search_drops_pico_drafts(ledger, monkeypatch) -> None:
    from app.artifact_store import LedgerArtifactStore
    from pico_orchestrator.tools_builtin import build_default_gateway

    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    store = LedgerArtifactStore(ledger.session_factory())
    made = asyncio.run(
        store.write(_principal(), title="旧讲义.md", content="浮力讲义 草稿", kind="md")
    )
    made_id = str(made["artifact_id"])

    def fake_search(query: str, **_kw: Any) -> dict[str, Any]:
        row = {"school_id": "school-a", "membership_id": "m-a", "text": "浮力 讲义"}
        return {
            "hybrid": False,
            "hits": [
                {**row, "artifact_id": made_id, "title": "旧讲义.md"},
                {**row, "artifact_id": "art-teacher", "title": "老师上传.md"},
            ],
        }

    monkeypatch.setattr("pico_orchestrator.tools_builtin.search_materials", fake_search)
    out = asyncio.run(
        build_default_gateway(store).invoke(_principal(), "kb_search", {"query": "浮力"})
    )
    assert [h["artifact_id"] for h in out["hits"]] == ["art-teacher"]
