"""Save browser PNGs under distinct names in the existing artifact ledger."""

from __future__ import annotations

import asyncio
import re
from sys import maxsize
from typing import Any
from weakref import WeakValueDictionary

from pico_orchestrator.gateway import ArtifactStore, Principal
from pico_orchestrator.sandbox_s1 import deny_secret_filename

_write_locks: WeakValueDictionary[tuple[str, str], asyncio.Lock] = WeakValueDictionary()


async def write_browser_screenshot(
    store: ArtifactStore,
    principal: Principal,
    *,
    name: str,
    page_title: str,
    png: bytes,
) -> dict[str, Any]:
    name = name.strip()
    label = re.sub(r"[/\\\x00-\x1f\x7f-\x9f]", "", name or page_title).strip()
    if label.lower().endswith(".png"):
        label = label[:-4]
    stem = label or "page"
    number = 1

    # Concurrent screenshot calls must choose and write titles one at a time.
    owner = (principal.school_id, principal.membership_id)
    async with _write_locks.setdefault(owner, asyncio.Lock()):
        titles = {row["title"] for row in await store.list(principal, limit=maxsize)}
        while True:
            suffix = f"-{number}.png" if not name or number > 1 else ".png"
            title = f"{stem[:128 - len(suffix)]}{suffix}"
            deny_secret_filename(title)
            if title not in titles:
                return await store.write(principal, title=title, content=png, kind="image")
            number += 1
