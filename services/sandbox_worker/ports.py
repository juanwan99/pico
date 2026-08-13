"""Listen-port contract: sandbox worker never occupies product UI or pico-api."""

from __future__ import annotations

PRODUCT_PORTS = frozenset({8080, 18088})
PICO_API_PORT = 18765
SANDBOX_DEFAULT_PORT = 18767
_BLOCKED_LISTEN = PRODUCT_PORTS | {PICO_API_PORT}


def assert_listen_port(port: int) -> int:
    """Refuse to bind product UI (8080/18088) or pico-api (18765)."""
    if int(port) in _BLOCKED_LISTEN:
        raise RuntimeError(
            f"pico-sandbox must not bind {port} (product UI 8080/18088 or pico-api 18765)"
        )
    if int(port) <= 0 or int(port) > 65535:
        raise RuntimeError(f"invalid sandbox listen port: {port}")
    return int(port)
