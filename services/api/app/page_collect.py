"""pico.page-collect.v1 — page-level join keys on school land.

Pico does not mint business ids. source_item_ids are this-turn named_ids.
edu-core is the collect landing; Pico only attaches the envelope.
"""

from __future__ import annotations

import re
from typing import Any

SCHEMA = "pico.page-collect.v1"
VALUE_KINDS = frozenset({"string", "string[]", "number", "bool"})
COLLECT_FIELDS_MAX = 32
KEY_MAX = 64
IDS_MAX = 12

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def sanitize_uuid(raw: Any) -> str:
    value = str(raw or "").strip()
    return value if _UUID_RE.match(value) else ""


def sanitize_uuid_list(raw: Any, *, limit: int = IDS_MAX) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        uid = sanitize_uuid(item)
        if not uid or uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
        if len(out) >= limit:
            break
    return out


def sanitize_collect_fields(raw: Any, *, source_item_ids: list[str]) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    allowed = set(source_item_ids)
    out: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()[:KEY_MAX]
        if not key or key in seen_keys:
            continue
        kind = str(row.get("value_kind") or "string").strip()
        if kind not in VALUE_KINDS:
            kind = "string"
        ref = sanitize_uuid(row.get("ref"))
        if ref and ref not in allowed:
            continue
        seen_keys.add(key)
        field: dict[str, str] = {"key": key, "value_kind": kind}
        if ref:
            field["ref"] = ref
        out.append(field)
        if len(out) >= COLLECT_FIELDS_MAX:
            break
    return out


def attach_page_collect(
    payload: dict[str, Any],
    *,
    source_item_ids: list[str] | tuple[str, ...] | None = None,
    pico_artifact_id: str = "",
    pico_task_id: str = "",
    collect_fields: list[Any] | None = None,
) -> dict[str, Any]:
    """Mutate land body with join keys. Always set source_item_ids (honest empty)."""
    ids = sanitize_uuid_list(list(source_item_ids or []))
    payload["source_item_ids"] = ids
    artifact = sanitize_uuid(pico_artifact_id)
    if artifact:
        payload["pico_artifact_id"] = artifact
    task = sanitize_uuid(pico_task_id)
    if task:
        payload["pico_task_id"] = task
    fields = sanitize_collect_fields(collect_fields, source_item_ids=ids)
    if fields:
        payload["collect_fields"] = fields
    return payload
