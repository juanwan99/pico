#!/usr/bin/env python3
"""Wire gpt-5.6-sol through New API (Custom URL → AIProxy /responses).

Reads secrets from host files. Never prints keys or passwords.
Run on ECS: python3 scripts/wire-brain-via-newapi.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

NEW_API = "http://127.0.0.1:3000"
SECRETS_NEWAPI = Path("/home/ops/.secrets/new-api.env")
SECRETS_AIPROXY = Path("/home/ops/.secrets/aiproxy-direct.env")
PICO_ENV = Path("/opt/pico/.env")
CHANNEL_NAME = "aiproxy-openai"
UPSTREAM_RESPONSES = "https://superaichao.xin/openai/responses"
MODEL = "gpt-5.6-sol"


def env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v.strip().strip('"')
    return out


def main() -> int:
    na = env_file(SECRETS_NEWAPI)
    pico = env_file(PICO_ENV)
    aiproxy = env_file(SECRETS_AIPROXY) if SECRETS_AIPROXY.is_file() else {}
    user = na.get("NEW_API_ADMIN_USER") or "picoadmin"
    password = na.get("NEW_API_ADMIN_PASSWORD") or ""
    pico_base = (pico.get("DEEPSEEK_BASE_URL") or "").lower()
    aiproxy_key = aiproxy.get("AIPROXY_API_KEY") or ""
    if not aiproxy_key and ("superaichao" in pico_base or pico_base.rstrip("/").endswith("/openai")):
        aiproxy_key = pico.get("DEEPSEEK_API_KEY") or ""
    gateway_key = pico.get("PICO_IMAGE_GATEWAY_KEY") or ""
    if not password or not aiproxy_key or not gateway_key:
        print("MISSING_SECRETS")
        return 2
    if aiproxy_key == gateway_key:
        print("REFUSING_GATEWAY_KEY_AS_UPSTREAM")
        return 2

    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(method: str, path: str, body: dict | None = None, bearer: str | None = None) -> tuple[int, dict | str]:
        headers = {"Content-Type": "application/json"}
        data = None
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        if body is not None:
            data = json.dumps(body).encode()
        req = urllib.request.Request(NEW_API + path, data=data, headers=headers, method=method)
        try:
            with opener.open(req, timeout=30) as resp:
                raw = resp.read().decode()
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, raw[:160]
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, raw[:160]

    code, login = call("POST", "/api/user/login", {"username": user, "password": password})
    ok = isinstance(login, dict) and login.get("success") is True
    data = login.get("data") if isinstance(login, dict) else None
    access = ""
    if isinstance(data, dict):
        access = str(data.get("access_token") or "")
    elif isinstance(data, str):
        access = data
    print("login", code, "ok" if ok and access else "fail", "token_len", len(access))
    if not ok or not access:
        return 1

    def admin(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
        return call(method, path, body, bearer=access)

    code, listing = admin("GET", "/api/channel/?p=1&page_size=50")
    print("list_channel", code, (listing.get("success") if isinstance(listing, dict) else type(listing).__name__))
    items = []
    if isinstance(listing, dict):
        data = listing.get("data") or {}
        if isinstance(data, dict):
            items = data.get("items") or data.get("data") or data.get("list") or []
            if not items and isinstance(data.get("data"), list):
                items = data["data"]
        elif isinstance(data, list):
            items = data
    names = []
    for ch in items:
        if isinstance(ch, dict):
            names.append((ch.get("id"), ch.get("name"), ch.get("type")))
    print("channels", names)

    existing = next((ch for ch in items if isinstance(ch, dict) and ch.get("name") == CHANNEL_NAME), None)
    payload = {
        "name": CHANNEL_NAME,
        "type": 8,
        "key": aiproxy_key,
        "base_url": UPSTREAM_RESPONSES,
        "models": MODEL,
        "group": "default",
        "groups": ["default"],
        "status": 1,
        "priority": 0,
        "weight": 0,
        "auto_ban": 0,
        "remark": "Pico chat brain. Custom URL = AIProxy /responses (no /v1).",
    }
    if existing:
        cid = existing.get("id")
        code, body = admin("PUT", "/api/channel/", {**payload, "id": cid})
        print("update_channel", cid, code, (body.get("success") if isinstance(body, dict) else "nonjson"))
    else:
        code, body = admin("POST", "/api/channel/", {"mode": "single", "channel": payload})
        print("create_channel", code, (body.get("success") if isinstance(body, dict) else "nonjson"),
              (body.get("message") if isinstance(body, dict) else str(body)[:80]))

    # Smoke: Pico's existing New API token through /v1/responses
    smoke_body = {
        "model": MODEL,
        "input": "ping",
        "store": False,
        "stream": False,
        "max_output_tokens": 16,
    }
    code, smoke = call(
        "POST",
        "/v1/responses",
        smoke_body,
        bearer=gateway_key,
    )
    kind = type(smoke).__name__
    status_key = None
    if isinstance(smoke, dict):
        status_key = smoke.get("status") or smoke.get("object") or smoke.get("error")
        if isinstance(status_key, dict):
            status_key = status_key.get("message") or status_key.get("type") or "error"
    print("smoke_responses", code, kind, status_key)
    return 0 if 200 <= code < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
