"""Thin cross-session day-use context for SYSTEM — not a memory OS.

Only: optional teacher display name + recent ledger artifact titles.
Long-chat compaction stays Pi official; no vector diary / second ledger.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Iterable

from pico_orchestrator.delivery_policy import is_bookkeeping_title

_MAX_NAME = 80
_MAX_TITLES = 8
_MAX_TITLE_LEN = 96
_EDU_FALLBACK = re.compile(r"^edu-[0-9a-f]{8,12}$", re.IGNORECASE)


def decode_display_name_header(raw: str | None) -> str:
    """LibreChat may send ``b64:…`` for non-Latin-1 names (see encodeHeaderValue)."""
    s = " ".join(str(raw or "").replace("\r", " ").replace("\n", " ").replace("\t", " ").split())
    s = s.strip()
    if s.startswith("b64:"):
        try:
            s = base64.b64decode(s[4:], validate=True).decode("utf-8")
        except Exception:  # noqa: BLE001 — bad header → no identity, never crash
            return ""
        s = " ".join(s.replace("\r", " ").replace("\n", " ").replace("\t", " ").split()).strip()
    return sanitize_display_name(s)


def sanitize_display_name(raw: str | None) -> str:
    name = " ".join(str(raw or "").replace("\r", " ").replace("\n", " ").replace("\t", " ").split())
    name = name.strip()[:_MAX_NAME]
    if not name or name == "学校账号":
        return ""
    if _EDU_FALLBACK.match(name):
        return ""
    return name


def normalize_recent_titles(titles: Iterable[str] | None, *, limit: int = _MAX_TITLES) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in titles or ():
        title = " ".join(str(raw or "").split()).strip()[:_MAX_TITLE_LEN]
        if not title or is_bookkeeping_title(title):
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(title)
        if len(out) >= max(0, int(limit or 0)):
            break
    return out


def build_day_use_block(
    *,
    display_name: str = "",
    recent_titles: Iterable[str] | None = None,
    max_titles: int = _MAX_TITLES,
) -> str:
    """SYSTEM appendix. Empty when nothing useful — never invent memory."""
    name = sanitize_display_name(display_name)
    titles = normalize_recent_titles(recent_titles, limit=max_titles)
    if not name and not titles:
        return ""
    lines = [
        "## Day-use context (thin · not a memory store)",
        "Facts from Pico ledger / SSO for this membership. Do not invent history beyond this list.",
        "Long-chat recall uses Pi official compaction + session files — not this block.",
    ]
    if name:
        lines.append(f"- Teacher display name: {name}")
    if titles:
        lines.append("- Recent files on this membership (newest first):")
        lines.extend(f"  - {t}" for t in titles)
    else:
        lines.append("- Recent files: (none listed)")
    return "\n".join(lines)
