"""Manager-only status of New API + Sub2API. Not a frontend; no secrets."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

NEW_API_STATUS = "http://127.0.0.1:3000/api/status"
SUB2API_HEALTH = "http://127.0.0.1:8081/health"


def _probe(url: str, timeout: float = 2.0) -> dict:
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200))
            return {"ok": 200 <= code < 500, "http": code}
    except URLError:
        return {"ok": False, "http": 0}
    except TimeoutError:
        return {"ok": False, "http": 0}
    except Exception:
        return {"ok": False, "http": 0}


def gateway_status() -> dict:
    """Thin adapter snapshot. Pico inference still talks only to New API."""
    return {
        "ok": True,
        "audience": "manager",
        "pico_talks_to": "new_api",
        "sub2api_role": "new_api_upstream_account_pool",
        "sub2api_is_frontend": False,
        "dify": "retired",
        "new_api": {
            "bind": "127.0.0.1:3000",
            "role": "reverse_proxy",
            **_probe(NEW_API_STATUS),
        },
        "sub2api": {
            "bind": "127.0.0.1:8081",
            "role": "account_polling_pool",
            **_probe(SUB2API_HEALTH),
        },
    }


def gateway_status_json() -> str:
    return json.dumps(gateway_status(), ensure_ascii=False)
