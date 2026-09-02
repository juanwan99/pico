"""llm-pass is a loopback splice, not a public file mouth."""

from __future__ import annotations

import sys
from pathlib import Path

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.llm_pass_router import _is_loopback_host, _loopback


def _request(*, client: str | None, server: str | None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.1", "version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/internal/llm-pass/run/v1/responses",
        "raw_path": b"/internal/llm-pass/run/v1/responses",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "client": (client, 4321) if client is not None else None,
        "server": (server, 18765) if server is not None else None,
    }
    return Request(scope)


def test_loopback_host_accepts_mapped_ipv4() -> None:
    assert _is_loopback_host("127.0.0.1")
    assert _is_loopback_host("::1")
    assert _is_loopback_host("localhost")
    assert _is_loopback_host("::ffff:127.0.0.1")
    assert not _is_loopback_host("172.20.109.183")
    assert not _is_loopback_host("8.8.8.8")


def test_loopback_allows_lan_client_on_loopback_socket() -> None:
    """Pi on this host may appear as eth0; the socket is still 127.0.0.1."""
    req = _request(client="172.20.109.183", server="127.0.0.1")
    assert _loopback(req) is True


def test_loopback_denies_lan_client_on_open_socket() -> None:
    req = _request(client="172.20.109.183", server="0.0.0.0")
    assert _loopback(req) is False


def test_loopback_allows_explicit_loopback_client() -> None:
    req = _request(client="127.0.0.1", server="0.0.0.0")
    assert _loopback(req) is True
