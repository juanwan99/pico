"""Public HTML page plumbing (capability only · no scene prompts).

Serve-time hook + collect payload caps. Persistence stays on the Pico ledger.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pico_orchestrator.gateway import ToolError

PAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_CSP_META_RE = re.compile(
    r"<meta\b[^>]*http-equiv=[\"']Content-Security-Policy[\"'][^>]*>\s*",
    re.IGNORECASE,
)
COLLECT_MAX_BYTES = 16_384
COLLECT_MAX_KEYS = 32
COLLECT_MAX_STR = 2_000
COLLECT_HOOK = (
    "<script>"
    "window.__PICO_COLLECT__=(function(){"
    "var p=location.pathname.replace(/\\/+$/,'');"
    "return p+'/collect';})();"
    "document.addEventListener('submit',function(e){"
    "var f=e.target;if(!f||!f.getAttribute||f.getAttribute('action'))return;"
    "e.preventDefault();var d={};"
    "if(window.FormData){new FormData(f).forEach(function(v,k){d[k]=v;});}"
    "fetch(window.__PICO_COLLECT__,{method:'POST',"
    "headers:{'content-type':'application/json'},"
    "body:JSON.stringify(d)}).catch(function(){});},true);"
    "</script>"
)
PUBLIC_CSP = (
    "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
    "script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; "
    "base-uri 'none'; frame-ancestors 'none'; sandbox allow-scripts allow-forms"
)


def assert_page_id(page_id: str) -> str:
    raw = (page_id or "").strip()
    if not PAGE_ID_RE.fullmatch(raw):
        raise ToolError("tool.invalid_arguments", "invalid page id")
    return raw


def inject_collect_hook(html: str) -> str:
    """Insert same-origin collect URL. Not a prompt. Not a scene template."""
    text = html or ""
    if "__PICO_COLLECT__" in text:
        return text
    lower = text.lower()
    idx = lower.rfind("</body>")
    if idx >= 0:
        return text[:idx] + COLLECT_HOOK + text[idx:]
    return text + COLLECT_HOOK


def prepare_public_html(html: str) -> str:
    """Serve-time only: drop embedded CSP (often form-action none) then inject hook."""
    return inject_collect_hook(_CSP_META_RE.sub("", html or ""))


def normalize_collect_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        raise ToolError("tool.invalid_arguments", "empty collect body")
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > COLLECT_MAX_BYTES:
            raise ToolError("tool.invalid_arguments", "collect body too large")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ToolError("tool.invalid_arguments", "collect body must be JSON") from exc
    elif isinstance(raw, str):
        if len(raw.encode("utf-8")) > COLLECT_MAX_BYTES:
            raise ToolError("tool.invalid_arguments", "collect body too large")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ToolError("tool.invalid_arguments", "collect body must be JSON") from exc
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise ToolError("tool.invalid_arguments", "collect body must be JSON")
    if not isinstance(parsed, dict):
        raise ToolError("tool.invalid_arguments", "collect body must be a JSON object")
    if len(parsed) > COLLECT_MAX_KEYS:
        raise ToolError("tool.invalid_arguments", "too many fields")
    out: dict[str, Any] = {}
    blob = json.dumps(parsed, ensure_ascii=False)
    if len(blob.encode("utf-8")) > COLLECT_MAX_BYTES:
        raise ToolError("tool.invalid_arguments", "collect body too large")
    for key, value in parsed.items():
        name = str(key).strip()[:64]
        if not name:
            continue
        if isinstance(value, str):
            out[name] = value[:COLLECT_MAX_STR]
        elif isinstance(value, (int, float, bool)) or value is None:
            out[name] = value
        else:
            out[name] = json.dumps(value, ensure_ascii=False)[:COLLECT_MAX_STR]
    if not out:
        raise ToolError("tool.invalid_arguments", "collect body has no fields")
    return out
