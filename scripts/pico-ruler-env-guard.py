#!/usr/bin/env python3
"""Keep a ruler / test stack off AIProxy (pico#1344). Rewrites the env file in place.

AIProxy is a coding subscription: one session, many rounds. Tests, rulers and
probes never use it (owner 10-18 07:3x PDT「根本不是速率问题 是使用方式问题」).
The AIProxy models (``PICO_LONG_SESSION_MODELS``, default ``gpt-5.6-sol``)
leave ``PICO_BRAIN_FALLBACKS``; any other line still naming one (the primary
model, an override) stops the stack from starting.

    python3 scripts/pico-ruler-env-guard.py <stack>/api.env
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_LONG = "gpt-5.6-sol"
DEFAULT_FALLBACKS = "grok-4.6,gpt-5.6-sol"  # brain_ha.configured_fallbacks()


def _split(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


def guard(text: str) -> tuple[str, list[str]]:
    """(new env text, keys that still name an AIProxy model)."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    long_only = set(_split(env.get("PICO_LONG_SESSION_MODELS") or DEFAULT_LONG))
    fallbacks = _split(env.get("PICO_BRAIN_FALLBACKS") or DEFAULT_FALLBACKS)
    out = [
        line
        for line in text.splitlines()
        if not line.startswith(("PICO_BRAIN_FALLBACKS=", "PICO_LONG_SESSION_MODELS="))
    ]
    out.append("PICO_BRAIN_FALLBACKS=" + ",".join(m for m in fallbacks if m not in long_only))
    out.append("PICO_LONG_SESSION_MODELS=" + ",".join(sorted(long_only)))
    bad = sorted(
        k
        for k, v in env.items()
        if k not in ("PICO_BRAIN_FALLBACKS", "PICO_LONG_SESSION_MODELS")
        and any(m in _split(v.replace(" ", ",")) for m in long_only)
    )
    return "\n".join(out) + "\n", bad


def main() -> int:
    path = Path(sys.argv[1])
    text, bad = guard(path.read_text(encoding="utf-8"))
    if bad:
        print(f"测试栈不能用 AIProxy 的模型：{', '.join(bad)}（pico#1344）", file=sys.stderr)
        return 4
    path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
