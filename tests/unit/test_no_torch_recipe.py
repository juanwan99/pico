"""T-PICO-NO-TORCH: production Dockerfiles must not pip install torch."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ("Dockerfile.pico-api", "Dockerfile.pico-api.true-pi")
_INSTALL_TORCH = re.compile(r"pip install[^\n]*\btorch\b", re.IGNORECASE)


def _code_lines(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def test_recipes_do_not_pip_install_torch():
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        code = _code_lines(text)
        assert "download.pytorch.org" not in code, name
        assert _INSTALL_TORCH.search(code) is None, name


def test_recipes_bound_pip_timeout():
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "PIP_DEFAULT_TIMEOUT=120" in text, name
