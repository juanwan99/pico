#!/usr/bin/env python3
"""S1 smoke: real model streaming hello (or honest BLOCKED)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import resolve_provider, stream_chat


async def main() -> int:
    cfg = resolve_provider()
    if cfg is None:
        print("BLOCKED S1: set KIMI_API_KEY (or DEEPSEEK_API_KEY) — mock ≠ S1")
        return 2
    print(f"provider={cfg.name} model={cfg.model} base={cfg.base_url}")
    text = []
    async for delta in stream_chat("Reply with exactly: pico-hello-ok", max_tokens=64):
        text.append(delta)
        print(delta, end="", flush=True)
    print()
    joined = "".join(text)
    if not joined.strip():
        print("FAIL: empty model response")
        return 1
    print("OK: received stream length", len(joined))
    return 0


if __name__ == "__main__":
    # Load .env if present (optional)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    raise SystemExit(asyncio.run(main()))
