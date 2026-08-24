"""T-PICO-NO-TORCH: production Dockerfiles must not pull torch, and must not
bust the pip cache on every deploy SHA.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ("Dockerfile.pico-api", "Dockerfile.pico-api.true-pi")
_INSTALL_TORCH = re.compile(r"pip install[^\n]*\btorch\b", re.IGNORECASE)
_PIP_INSTALL = re.compile(r"\bpip install\b")
_SHA_ARG = re.compile(r"^ARG\s+PICO_GIT_SHA\b")
_SHA_ENV = re.compile(r"^ENV\s+.*PICO_GIT_SHA=")
_DOCLING_META = re.compile(r'pip install[^\n]*["\']docling>=', re.IGNORECASE)


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


def test_recipes_use_docling_slim_not_meta_package():
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        code = _code_lines(text)
        assert "docling-slim" in code, name
        assert _DOCLING_META.search(code) is None, name
        assert "find_spec('torch')" in code or 'find_spec("torch")' in code, name
        assert "pip uninstall" not in code, name


def test_git_sha_arg_is_below_every_pip_layer():
    """Changing PICO_GIT_SHA must not invalidate Node/pip/docling layers."""
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        sha_arg_at: int | None = None
        sha_env_at: int | None = None
        last_pip_at = -1
        for i, raw in enumerate(text.splitlines()):
            s = raw.strip()
            if s.startswith("#"):
                continue
            if _SHA_ARG.match(s):
                sha_arg_at = i
            if _SHA_ENV.match(s) or (
                s.startswith("ENV ") and "PICO_GIT_SHA=" in s and "PICO_GIT_SHA=${PICO_GIT_SHA}" in s
            ):
                sha_env_at = i
            if _PIP_INSTALL.search(s):
                last_pip_at = i
        assert last_pip_at >= 0, name
        assert sha_arg_at is not None, name
        assert sha_arg_at > last_pip_at, (
            f"{name}: ARG PICO_GIT_SHA line {sha_arg_at + 1} is above pip line {last_pip_at + 1}"
        )
        if sha_env_at is not None:
            assert sha_env_at > last_pip_at, (
                f"{name}: ENV PICO_GIT_SHA line {sha_env_at + 1} is above pip line {last_pip_at + 1}"
            )
