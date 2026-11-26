"""Locks shared by the pico-api processes using the same ledger."""

from __future__ import annotations

import asyncio
import fcntl
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.engine import make_url

from app.db import _normalize_url, _sqlite_base_dir
from app.settings import get_settings


def lock_path(name: str) -> Path:
    url = make_url(_normalize_url(get_settings().pico_database_url))
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        database = Path(url.database)
        return database.with_name(f"{database.name}.{name}.lock")
    data = _sqlite_base_dir() / "data"
    data.mkdir(exist_ok=True)
    return data / f"{name}.lock"


def try_lock(path: Path) -> BinaryIO | None:
    lock = path.open("a+b")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Another process owns this lock. The caller decides whether to wait.
        lock.close()
        return None
    except BaseException:
        lock.close()
        raise
    return lock


async def wait_lock(path: Path) -> BinaryIO:
    while (lock := try_lock(path)) is None:
        await asyncio.sleep(0.2)
    return lock
