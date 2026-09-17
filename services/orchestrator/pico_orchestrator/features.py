"""Teacher-chosen feature switches and today's points allowance, read from the JWT.

edu stores the switches and the wallet; Pico only reads what edu signed into
the token. No balance is stored here (USAGE-LEDGER §1). #1042.

Rules (owner 2026-09-16):
- A token with no ``feat:*`` scope at all = every feature on (edu not rolled out).
- A token with any ``feat:*`` scope = allowlist; features not listed are off.
- ``allowance_points_today`` absent = no allowance gate.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

FEATURE_PREFIX = "feat:"
FEATURES = ("kb", "rerank", "image", "deep", "office")
FEATURE_SCOPES = frozenset(f"{FEATURE_PREFIX}{name}" for name in FEATURES)
ALLOWANCE_CLAIM = "allowance_points_today"

# Gateway tools → the switch that must be on. Tools not listed are always allowed.
FEATURE_BY_TOOL: dict[str, str] = {
    "kb_search": "kb",
    "generate_image": "image",
    "generate_diagram": "image",
    "generate_html_document": "office",
    "sandbox_office_lib": "office",
    "publish_html_page": "office",
}

FEATURE_OFF_MESSAGE = {
    "kb": "知识库功能未开启，可在设置里开启。",
    "rerank": "精排未开启。",
    "image": "出图功能未开启，可在设置里开启。",
    "deep": "深度档未开启，可在设置里开启。",
    "office": "办公文件功能未开启，可在设置里开启。",
}


def _scopes_of(principal: Any) -> list[str]:
    try:
        return [str(s) for s in (getattr(principal, "scopes", None) or [])]
    except TypeError:
        return []


def feature_enabled(principal: Any, feature: str) -> bool:
    scopes = _scopes_of(principal)
    feats = [s for s in scopes if s.startswith(FEATURE_PREFIX)]
    if not feats:
        return True
    return f"{FEATURE_PREFIX}{feature}" in feats


def feature_for_tool(tool_name: str) -> str | None:
    return FEATURE_BY_TOOL.get((tool_name or "").strip())


def allowance_millipoints(principal: Any) -> int | None:
    """Today's allowance in millipoints (1 point = 1000), or None when the token
    carries no allowance claim. Negative or garbage → 0 (fail-closed on a bad number)."""
    raw = getattr(principal, "raw", None)
    if not isinstance(raw, dict) or ALLOWANCE_CLAIM not in raw:
        return None
    value = raw.get(ALLOWANCE_CLAIM)
    if value is None or isinstance(value, bool):
        return 0
    try:
        points = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return 0
    if points.is_nan() or points.is_infinite() or points < 0:
        return 0
    return int((points * 1000).to_integral_value())
