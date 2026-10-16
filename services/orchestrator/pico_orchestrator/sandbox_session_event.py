"""Ledger event for ResultPanel「网页」态. Never carry passwords."""

from __future__ import annotations

from typing import Any

SANDBOX_BROWSER_TOOLS = frozenset(
    {
        "sandbox_browser_open",
        "sandbox_browser_screenshot",
        "sandbox_browser_snapshot",
        "sandbox_browser_navigate",
        "sandbox_browser_navigate_back",
        "sandbox_browser_click",
        "sandbox_browser_hover",
        "sandbox_browser_tabs",
        "sandbox_browser_fill_form",
        "sandbox_browser_file_upload",
        "sandbox_browser_page_file",
        "sandbox_browser_page_fn",
        "sandbox_browser_type",
        "sandbox_browser_select_option",
        "sandbox_browser_press_key",
        "sandbox_browser_wait_for",
        "sandbox_document_open",
    }
)
HUMAN_COPY = "这是你的隔离浏览器，可以直接在画面里操作"
_SECRET_KEYS = frozenset({"password", "passwd", "secret", "credential", "cookie", "cookies"})
# Screenshot pixels go to the model as image content (bridge), never into the ledger.
_PIXEL_KEYS = frozenset({"image_png_base64"})


def public_tool_result(result: Any) -> Any:
    """Drop password-like keys and raw pixels before a sandbox tool result hits the ledger."""
    if not isinstance(result, dict):
        return result
    out: dict[str, Any] = {}
    for key, value in result.items():
        low = str(key).lower()
        if low in _SECRET_KEYS or low in _PIXEL_KEYS or low.endswith("password"):
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
    payload = {
        "session_id": session_id,
        "url": url,
        "title": title,
        "view_path": view_path,
        "human_copy": str(result.get("human_copy") or HUMAN_COPY),
        "engine": str(result.get("engine") or ""),
        "kind": str(result.get("kind") or ""),
        "workspace_id": str(result.get("workspace_id") or ""),
        "has_text_input": bool(result.get("has_text_input")),
        "has_password_input": bool(result.get("has_password_input")),
        "human_hold": bool(result.get("human_hold")),
        "ai_acting": bool(result.get("ai_acting")),
    }
    windows = result.get("windows")
    if isinstance(windows, list):
        payload["windows"] = windows
    focused = str(result.get("focused_window_id") or "").strip()
    if focused:
        payload["focused_window_id"] = focused
    files = result.get("files")
    if isinstance(files, list):
        payload["files"] = files
    if result.get("persist"):
        payload["persist"] = True
    if result.get("disk_bytes") is not None:
        payload["disk_bytes"] = result.get("disk_bytes")
    if result.get("disk_quota_bytes") is not None:
        payload["disk_quota_bytes"] = result.get("disk_quota_bytes")
    return payload
