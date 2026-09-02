"""Loopback-bound sockets. client.host may be eth0 under host-network."""

from __future__ import annotations

from fastapi import Request

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower().strip("[]")
    if h in _LOOPBACK_HOSTS:
        return True
    if h.startswith("::ffff:"):
        return is_loopback_host(h.rsplit(":", 1)[-1])
    return False


def request_on_loopback_socket(request: Request) -> bool:
    """True when this request hit a 127.0.0.1/::1 bind, or the peer is loopback.

    Do not trust client.host alone: uvicorn proxy-headers and this host's eth0
    make local Pi / prod-update look like 172.x / 100.x.
    """
    if request.client and is_loopback_host(request.client.host):
        return True
    server = request.scope.get("server") if hasattr(request, "scope") else None
    if isinstance(server, (list, tuple)) and server:
        return is_loopback_host(str(server[0] or ""))
    return False
