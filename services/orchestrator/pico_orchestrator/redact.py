"""Redact tenant identity from user-visible agent/tool text and payloads."""

from __future__ import annotations

import json
import re
from typing import Any

_ID_KEYS = (
    "school_id",
    "membership_id",
    "token_school_id",
    "requested_school_id",
    "pico_membership_id",
    "x_pico_membership_id",
)

_KEY_VALUE_RE = re.compile(
    r"(?i)([\"']?(?:"
    + "|".join(re.escape(k) for k in _ID_KEYS)
    + r")[\"']?\s*[:=]\s*)([\"']?)([^\"'\s,}\]]+)\2"
)

_SENSITIVE_IN_TEXT = re.compile(
    r"(?i)\b(school_id|membership_id|token_school_id|requested_school_id)\b"
)


def redact_tenant_text(
    text: str | None,
    *,
    school_id: str | None = None,
    membership_id: str | None = None,
) -> str:
    """Remove raw tenant identifiers from teacher-visible prose."""
    if not text:
        return ""
    out = str(text)
    out = _KEY_VALUE_RE.sub(r"\1\2[已脱敏]\2", out)
    for raw, label in (
        (school_id, "[学校标识]"),
        (membership_id, "[成员标识]"),
    ):
        if raw and len(raw) >= 4 and raw in out:
            out = out.replace(raw, label)
    # Collapse remaining bare key mentions that still look like dumps
    if _SENSITIVE_IN_TEXT.search(out) and ("=" in out or ":" in out):
        out = _KEY_VALUE_RE.sub(r"\1\2[已脱敏]\2", out)
    return out


def redact_tenant_payload(
    value: Any,
    *,
    school_id: str | None = None,
    membership_id: str | None = None,
) -> Any:
    """Deep-copy-ish redact of dict/list/str tool results."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            low = str(key).lower()
            if low in _ID_KEYS or low.endswith(("membership_id", "school_id")):
                out[key] = "[已脱敏]"
            else:
                out[key] = redact_tenant_payload(
                    item, school_id=school_id, membership_id=membership_id
                )
        return out
    if isinstance(value, list):
        return [
            redact_tenant_payload(item, school_id=school_id, membership_id=membership_id)
            for item in value
        ]
    if isinstance(value, str):
        return redact_tenant_text(value, school_id=school_id, membership_id=membership_id)
    return value


def safe_json_for_user(
    value: Any,
    *,
    school_id: str | None = None,
    membership_id: str | None = None,
) -> str:
    redacted = redact_tenant_payload(value, school_id=school_id, membership_id=membership_id)
    try:
        return json.dumps(redacted, ensure_ascii=False)
    except (TypeError, ValueError):
        return redact_tenant_text(str(value), school_id=school_id, membership_id=membership_id)
