"""init_db 一个进程只建表 / 迁移 / 清账本一次（edu-core#4503：每次对话重跑，阅卷一次排队 30–100 秒）。"""

from __future__ import annotations

import pytest
from app import db as dbmod
from app.settings import get_settings


@pytest.mark.asyncio
async def test_init_db_runs_setup_once_per_url(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(dbmod, "_scrub_usage_events_sync", lambda conn: calls.append("scrub"))
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None

    await dbmod.init_db()
    first = dbmod.session_factory()
    await dbmod.init_db()
    await dbmod.init_db()
    assert calls == ["scrub"]
    assert dbmod.session_factory() is first

    # 换库（测试换临时库）照旧重建
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'b.db'}")
    get_settings.cache_clear()
    await dbmod.init_db()
    assert calls == ["scrub", "scrub"]
    assert dbmod.session_factory() is not first
