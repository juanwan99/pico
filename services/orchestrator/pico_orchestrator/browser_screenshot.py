"""Save browser PNGs under distinct names in the existing artifact ledger."""

from __future__ import annotations

import asyncio
from typing import Any
from weakref import WeakValueDictionary

from pico_orchestrator.gateway import ArtifactStore, Principal
from pico_orchestrator.sandbox_s1 import deny_secret_filename, safe_segment

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
    label = name or page_title.strip()
    if label.lower().endswith(".png"):
        label = label[:-4]
    stem = safe_segment(label, fallback="page")
    number = 1
    title = f"{stem}.png" if name else f"{stem}-{number}.png"

    # Concurrent screenshot calls must choose and write titles one at a time.
    owner = (principal.school_id, principal.membership_id)
    async with _write_locks.setdefault(owner, asyncio.Lock()):
        while await store.read(principal, artifact_id=None, title=title) is not None:
            number += 1
            title = f"{stem}-{number}.png"
        deny_secret_filename(title)
        return await store.write(principal, title=title, content=png, kind="image")
