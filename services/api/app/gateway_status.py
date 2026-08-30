"""Manager-only status of New API + Sub2API. Not a frontend; no secrets."""

from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NEW_API_STATUS = "http://127.0.0.1:3000/api/status"
NEW_API_MODELS = "http://127.0.0.1:3000/v1/models"
SUB2API_HEALTH = "http://127.0.0.1:8081/health"
SUB2API_LOGIN = "http://127.0.0.1:8081/api/v1/auth/login"
SUB2API_MONITORS = "http://127.0.0.1:8081/api/v1/channel-monitors"
SUB2API_ADMIN_ACCOUNTS = "http://127.0.0.1:8081/api/v1/admin/accounts"
SUB2API_TAILNET_UI = "https://aliyun-hy.tail217880.ts.net"
SOFT_ACTIONS = frozenset({"refresh", "test", "clear-error", "recover-state"})
_STATUS_BUCKET = {
    "operational": "健康",
    "degraded": "警告",
    "failed": "严重",
    "error": "严重",
}

_token_cache: dict[str, object] = {"token": None, "exp": 0.0}


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


def _probe_json(
    url: str,
    timeout: float = 2.0,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict | list | None]:
    try:
        data = None if payload is None else json.dumps(payload).encode()
        hdrs = dict(headers or {})
        if data is not None:
            hdrs.setdefault("Content-Type", "application/json")
        req = Request(url, data=data, method=method, headers=hdrs)
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


def _unwrap(body: dict | list | None) -> dict | list | None:
    if isinstance(body, dict) and "data" in body:
        inner = body.get("data")
        if isinstance(inner, (dict, list)):
            return inner
    return body


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


def _sub2api_token() -> str | None:
    key = (os.environ.get("SUB2API_ADMIN_API_KEY") or "").strip()
    if key:
        return key
    cached = _token_cache.get("token")
    exp = float(_token_cache.get("exp") or 0)
    if isinstance(cached, str) and cached and time.time() < exp - 30:
        return cached
    email = (os.environ.get("SUB2API_ADMIN_EMAIL") or "").strip()
    password = (os.environ.get("SUB2API_ADMIN_PASSWORD") or "").strip()
    if not email or not password:
        return None
    code, body = _probe_json(
        SUB2API_LOGIN,
        method="POST",
        payload={"email": email, "password": password},
        timeout=8.0,
    )
    data = _unwrap(body)
    if code != 200 or not isinstance(data, dict):
        return None
    token = str(data.get("access_token") or "").strip()
    if not token:
        return None
    expires = data.get("expires_in")
    ttl = int(expires) if isinstance(expires, int) and expires > 0 else 3600
    _token_cache["token"] = token
    _token_cache["exp"] = time.time() + ttl
    return token


def _auth_headers() -> dict[str, str] | None:
    token = _sub2api_token()
    if not token:
        return None
    return {"Authorization": "Bearer " + token}


def _bucket(status: str) -> str:
    return _STATUS_BUCKET.get((status or "").strip().lower(), "未知")


def _sanitize_timeline(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for point in raw[-168:]:
        if not isinstance(point, dict):
            continue
        status = str(point.get("status") or "").strip()
        checked = str(point.get("checked_at") or "").strip()
        item: dict[str, str] = {"status": status, "bucket": _bucket(status)}
        if checked:
            item["checked_at"] = checked
        out.append(item)
    return out


def _sanitize_monitor(row: dict) -> dict:
    status = str(row.get("primary_status") or "").strip()
    avail = row.get("availability_7d")
    latency = row.get("primary_latency_ms")
    ident = row.get("id")
    return {
        "id": ident if isinstance(ident, int) else None,
        "name": str(row.get("name") or "").strip() or "未命名",
        "provider": str(row.get("provider") or "").strip(),
        "group_name": str(row.get("group_name") or "").strip(),
        "primary_model": str(row.get("primary_model") or "").strip(),
        "primary_status": status,
        "bucket": _bucket(status),
        "primary_latency_ms": latency if isinstance(latency, int) else None,
        "availability_7d": float(avail) if isinstance(avail, (int, float)) else None,
        "timeline": _sanitize_timeline(row.get("timeline")),
    }


def _sanitize_account(row: dict) -> dict:
    ident = row.get("id")
    err = str(row.get("error") or row.get("last_error") or "").strip()
    if len(err) > 160:
        err = err[:157] + "…"
    return {
        "id": ident if isinstance(ident, int) else None,
        "name": str(row.get("name") or "").strip() or "未命名",
        "platform": str(row.get("platform") or "").strip(),
        "status": str(row.get("status") or "").strip(),
        "schedulable": row.get("schedulable") if isinstance(row.get("schedulable"), bool) else None,
        "error": err or None,
        "soft_actions": sorted(SOFT_ACTIONS),
    }


def _items(body: dict | list | None) -> list[dict]:
    data = _unwrap(body)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        raw = data.get("items") or data.get("data") or data.get("accounts") or data.get("monitors")
        rows = raw if isinstance(raw, list) else []
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _sub2api_login_state() -> dict:
    headers = _auth_headers()
    monitors_http, monitors_body = _probe_json(SUB2API_MONITORS, headers=headers)
    accounts_http, accounts_body = _probe_json(SUB2API_ADMIN_ACCOUNTS, headers=headers)
    monitors = [_sanitize_monitor(row) for row in _items(monitors_body)] if monitors_http == 200 else []
    accounts = [_sanitize_account(row) for row in _items(accounts_body)] if accounts_http == 200 else []
    compliance_required = accounts_http == 423 or monitors_http == 423
    for blob in (monitors_body, accounts_body):
        if isinstance(blob, dict) and str(blob.get("code") or "") == "ADMIN_COMPLIANCE_ACK_REQUIRED":
            compliance_required = True
    return {
        "monitors_http": monitors_http,
        "accounts_http": accounts_http,
        "monitor_count": len(monitors) if monitors_http == 200 else None,
        "monitors": monitors,
        "accounts": accounts,
        "compliance_required": compliance_required,
        "needs_auth": headers is None or monitors_http == 401 or accounts_http == 401,
        "hard_relogin": "sub2api_tailnet_ui",
        "soft_actions": sorted(SOFT_ACTIONS),
    }


def account_soft_action(account_id: int, action: str) -> dict:
    """Thin POST to Sub2API admin account actions. Never returns tokens."""
    if action not in SOFT_ACTIONS:
        return {"ok": False, "http": 400, "message": "没有这个动作。"}
    if account_id < 1:
        return {"ok": False, "http": 400, "message": "账号不对。"}
    headers = _auth_headers()
    if headers is None:
        return {"ok": False, "http": 401, "message": "还没接上 Sub2API 管理账号。硬重登走尾网真页。"}
    url = f"{SUB2API_ADMIN_ACCOUNTS}/{account_id}/{action}"
    code, body = _probe_json(url, method="POST", headers=headers, timeout=12.0)
    message = "已交给上游。"
    if isinstance(body, dict):
        raw_msg = str(body.get("message") or "").strip()
        err_code = str(body.get("code") or "")
        if err_code == "ADMIN_COMPLIANCE_ACK_REQUIRED" or code == 423:
            message = "要先在尾网 Sub2API 真页签合规承诺。Pico 不代签。"
        elif raw_msg:
            message = raw_msg[:200]
    if code == 0:
        message = "上游没响应。"
    return {"ok": 200 <= code < 300, "http": code, "message": message, "action": action}


def gateway_status() -> dict:
    """Thin adapter snapshot. Pico inference still talks only to New API."""
    brain = _brain_snapshot()
    login_state = _sub2api_login_state()
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
            **login_state,
        },
    }


def gateway_status_json() -> str:
    return json.dumps(gateway_status(), ensure_ascii=False)
