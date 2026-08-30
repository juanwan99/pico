"""Manager-only status of New API + Sub2API. Not a frontend; no secrets."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NEW_API_STATUS = "http://127.0.0.1:3000/api/status"
NEW_API_MODELS = "http://127.0.0.1:3000/v1/models"
SUB2API_HEALTH = "http://127.0.0.1:8081/health"
SUB2API_MONITORS = "http://127.0.0.1:8081/api/v1/channel-monitors"
SUB2API_ADMIN_ACCOUNTS = "http://127.0.0.1:8081/api/v1/admin/accounts"
SUB2API_TAILNET_UI = "https://aliyun-hy.tail217880.ts.net"


def _probe(url: str, timeout: float = 2.0, headers: dict[str, str] | None = None) -> dict:
    try:
        req = Request(url, method="GET", headers=headers or {})
        with urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200))
            return {"ok": 200 <= code < 500, "http": code}
    except HTTPError as exc:
        return {"ok": False, "http": int(exc.code)}
    except (URLError, TimeoutError, OSError, ValueError):
        return {"ok": False, "http": 0}


def _probe_json(url: str, timeout: float = 2.0, headers: dict[str, str] | None = None) -> tuple[int, dict | list | None]:
    try:
        req = Request(url, method="GET", headers=headers or {})
        with urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200))
            raw = resp.read().decode()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return code, None
            if isinstance(parsed, (dict, list)):
                return code, parsed
            return code, None
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        return int(exc.code), parsed if isinstance(parsed, (dict, list)) else None
    except (URLError, TimeoutError, OSError, ValueError):
        return 0, None


def _brain_snapshot() -> dict:
    base = (os.environ.get("DEEPSEEK_BASE_URL") or "").strip().lower()
    model = (os.environ.get("DEEPSEEK_MODEL") or "").strip()
    via_new_api = "127.0.0.1:3000" in base or "localhost:3000" in base
    via_aiproxy = "superaichao" in base or base.rstrip("/").endswith("/openai")
    if via_new_api:
        via = "new_api"
    elif via_aiproxy:
        via = "aiproxy_direct"
    else:
        via = "other"
    return {
        "model": model or None,
        "via": via,
        "slot": "DEEPSEEK_*",
        "expected_via": "new_api",
    }


def _new_api_models() -> list[str]:
    key = (os.environ.get("PICO_IMAGE_GATEWAY_KEY") or "").strip()
    if not key:
        return []
    code, body = _probe_json(
        NEW_API_MODELS,
        headers={"Authorization": "Bearer " + key},
    )
    if code != 200 or not isinstance(body, dict):
        return []
    rows = body.get("data")
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            mid = str(row.get("id") or "").strip()
            if mid and mid not in ids:
                ids.append(mid)
        if len(ids) >= 24:
            break
    return ids


def _sub2api_login_state() -> dict:
    monitors_http, monitors_body = _probe_json(SUB2API_MONITORS)
    accounts_http, accounts_body = _probe_json(SUB2API_ADMIN_ACCOUNTS)
    monitor_count = None
    if monitors_http == 200:
        if isinstance(monitors_body, list):
            monitor_count = len(monitors_body)
        elif isinstance(monitors_body, dict):
            items = monitors_body.get("items") or monitors_body.get("data") or monitors_body.get("monitors")
            if isinstance(items, list):
                monitor_count = len(items)
    compliance_required = False
    for blob in (monitors_body, accounts_body):
        if isinstance(blob, dict):
            code = str(blob.get("code") or "")
            if code == "ADMIN_COMPLIANCE_ACK_REQUIRED" or accounts_http == 423 or monitors_http == 423:
                compliance_required = True
    if accounts_http == 423:
        compliance_required = True
    return {
        "monitors_http": monitors_http,
        "accounts_http": accounts_http,
        "monitor_count": monitor_count,
        "compliance_required": compliance_required,
        "needs_auth": monitors_http == 401 or accounts_http == 401,
        "hard_relogin": "sub2api_tailnet_ui",
    }


def gateway_status() -> dict:
    """Thin adapter snapshot. Pico inference still talks only to New API."""
    brain = _brain_snapshot()
    return {
        "ok": True,
        "audience": "manager",
        "pico_talks_to": "new_api" if brain.get("via") == "new_api" else brain.get("via"),
        "sub2api_role": "account_login_state",
        "sub2api_is_frontend": False,
        "new_api_role": "pipe_channels_billing",
        "dify": "retired",
        "brain": brain,
        "new_api": {
            "bind": "0.0.0.0:3000",
            "intended_bind": "127.0.0.1:3000",
            "role": "pipe",
            "models": _new_api_models(),
            **_probe(NEW_API_STATUS),
        },
        "sub2api": {
            "bind": "127.0.0.1:8081",
            "role": "account_login_state",
            "tailnet_ui": SUB2API_TAILNET_UI,
            **_probe(SUB2API_HEALTH),
            **_sub2api_login_state(),
        },
    }


def gateway_status_json() -> str:
    return json.dumps(gateway_status(), ensure_ascii=False)
