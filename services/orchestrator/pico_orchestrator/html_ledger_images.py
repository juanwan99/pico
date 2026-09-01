"""Resolve ledger picture ids in HTML. Model speaks ids; Pico inlines bytes.

Not a renderer. Not a courseware pipeline. Same primitive as PPT
image_artifact_id: missing id skips that picture; the page still lands.
"""

from __future__ import annotations

import base64
import re
from typing import Any

PICO_ARTIFACT_SCHEME = "pico-artifact:"
# src/href="pico-artifact:<id-or-index>"  and  url(pico-artifact:…)
_SRC_RE = re.compile(
    r"""(?P<attr>(?:src|href)\s*=\s*)(?P<q>["'])"""
    r"""pico-artifact:(?P<ref>[^"']+)(?P=q)""",
    re.IGNORECASE,
)
_URL_RE = re.compile(
    r"""url\(\s*(?P<q>["']?)pico-artifact:(?P<ref>[^"')\s]+)(?P=q)\s*\)""",
    re.IGNORECASE,
)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


def parse_image_artifact_ids(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("image_artifact_ids 必须是数组。")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        aid = str(item or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        out.append(aid)
    return out


def collect_pico_artifact_refs(text: str, index_ids: list[str]) -> list[str]:
    """Unique ledger ids referenced by pico-artifact: tokens (plus index aliases)."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(ref: str) -> None:
        aid = _ref_to_id(ref, index_ids)
        if aid and aid not in seen:
            seen.add(aid)
            found.append(aid)

    for match in _SRC_RE.finditer(text or ""):
        _add(match.group("ref"))
    for match in _URL_RE.finditer(text or ""):
        _add(match.group("ref"))
    return found


def _ref_to_id(ref: str, index_ids: list[str]) -> str | None:
    token = (ref or "").strip()
    if not token:
        return None
    if token.isdigit():
        idx = int(token)
        if 0 <= idx < len(index_ids):
            return index_ids[idx]
        return None
    return token


def image_data_url(raw: bytes) -> str | None:
    if not raw:
        return None
    if raw.startswith(PNG_MAGIC):
        mime = "image/png"
    elif raw[:3] == JPEG_MAGIC:
        mime = "image/jpeg"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        mime = "image/webp"
    elif raw[:6] in (b"GIF87a", b"GIF89a"):
        mime = "image/gif"
    else:
        return None
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def rewrite_pico_artifact_srcs(
    text: str,
    *,
    resolved: dict[str, str],
    index_ids: list[str],
) -> tuple[str, dict[str, Any]]:
    """Replace known pico-artifact refs with data: URLs. Missing refs stay.

    ``resolved`` keys are ledger artifact ids. Index aliases (0, 1, …)
    map through ``index_ids``.
    """
    landed: list[str] = []
    skipped: list[str] = []
    seen_land: set[str] = set()
    seen_skip: set[str] = set()

    def _url_for(ref: str) -> str | None:
        aid = _ref_to_id(ref, index_ids)
        if not aid:
            token = (ref or "").strip()
            if token and token not in seen_skip:
                seen_skip.add(token)
                skipped.append(token)
            return None
        url = resolved.get(aid)
        if not url:
            if aid not in seen_skip:
                seen_skip.add(aid)
                skipped.append(aid)
            return None
        if aid not in seen_land:
            seen_land.add(aid)
            landed.append(aid)
        return url

    def _src(match: re.Match[str]) -> str:
        url = _url_for(match.group("ref"))
        if not url:
            return match.group(0)
        return f"{match.group('attr')}{match.group('q')}{url}{match.group('q')}"

    def _css(match: re.Match[str]) -> str:
        url = _url_for(match.group("ref"))
        if not url:
            return match.group(0)
        return f"url({url})"

    out = _SRC_RE.sub(_src, text or "")
    out = _URL_RE.sub(_css, out)
    return out, {"landed": landed, "skipped": skipped}
