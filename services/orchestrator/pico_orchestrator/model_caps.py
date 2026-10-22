"""Upstream output ceiling per backend model (pico#1332).

Measured 10-17 on the live gateway: gemini-3.8-flash takes max_tokens 65536,
65537 is a 400. A known model writes up to its ceiling; unknown ones (incl. a
teacher's own endpoint) keep the configured tier cap. No imports: provider.py
and true_pi/client.py both read it.
"""

from __future__ import annotations

MODEL_OUTPUT_CAPS = {"gemini-3.8-flash": 65_536}


def output_cap_for_model(model: str | None, configured: int) -> int:
    bare = (model or "").strip().split("/")[-1].lower()
    return MODEL_OUTPUT_CAPS.get(bare, int(configured))
