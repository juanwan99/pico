"""Ledger event for ResultPanel「网页」态. Never carry passwords."""

from __future__ import annotations

from typing import Any

SANDBOX_BROWSER_TOOLS = frozenset(
    {"sandbox_browser_open", "sandbox_browser_screenshot", "sandbox_document_open"}
)
HUMAN_COPY = "请在此画面自行登录，不要在聊天里发送密码"
_SECRET_KEYS = frozenset({"password", "passwd", "secret", "credential", "cookie", "cookies"})


def public_tool_result(result: Any) -> Any:
    """Drop password-like keys before a sandbox tool result hits the ledger."""
    if not isinstance(result, dict):
        return result
    out: dict[str, Any] = {}
    for key, value in result.items():
        low = str(key).lower()
        if low in _SECRET_KEYS or low.endswith("password"):
            continue
        out[key] = value
    return out


def sandbox_session_payload(result: Any) -> dict[str, Any] | None:
    """Build a teacher-facing session event. Drop any secret-like keys."""
    if not isinstance(result, dict):
        return None
    session_id = str(result.get("session_id") or "").strip()
    if not session_id.startswith("sbox_"):
        return None
    url = str(result.get("url") or "").strip()
    title = str(result.get("title") or "").strip()
    view_path = str(result.get("view_path") or "").strip()
    if not view_path:
        view_path = f"/v1/sandbox/sessions/{session_id}/view"
    return {
        "session_id": session_id,
        "url": url,
        "title": title,
        "view_path": view_path,
        "human_copy": str(result.get("human_copy") or HUMAN_COPY),
        "engine": str(result.get("engine") or ""),
        "kind": str(result.get("kind") or ""),
        "workspace_id": str(result.get("workspace_id") or ""),
    }
