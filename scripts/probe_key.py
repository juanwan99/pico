"""Probe / test scripts call New API with the pico-probe token, never production (pico#1271).

New API tokens: production (DEEPSEEK_API_KEY, chat), knowledge base
(PICO_KB_API_KEY, embeddings + rerank), probe (PICO_PROBE_API_KEY, these
scripts). A probe on the production token eats teachers' key slots and hides
in their numbers, so it is refused.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

PROBE_ENV = "PICO_PROBE_API_KEY"


def probe_key(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    key = (source.get(PROBE_ENV) or "").strip()
    if not key:
        raise SystemExit(f"{PROBE_ENV} missing: probes use the New API pico-probe token")
    taken = {(source.get(name) or "").strip() for name in ("DEEPSEEK_API_KEY", "PICO_KB_API_KEY")}
    if key in taken:
        raise SystemExit(f"{PROBE_ENV} is the production or knowledge-base token; use pico-probe")
    return key


def use_probe_key() -> str:
    """For scripts that run Pico code in-process: swap the brain key for the probe one."""
    key = probe_key()
    os.environ["DEEPSEEK_API_KEY"] = key
    return key
