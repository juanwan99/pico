"""Production API images must not pull torch, and deploy SHA must not bust pip."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ("Dockerfile.pico-api", "Dockerfile.pico-api.true-pi")
_INSTALL_TORCH = re.compile(r"pip install[^\n]*\btorch\b", re.IGNORECASE)
_DOCLING_META = re.compile(r'["\']docling>=', re.IGNORECASE)
_FROM_DIGEST = re.compile(
    r"^FROM\s+python:3\.12-slim@sha256:[0-9a-f]{64}\s*$", re.MULTILINE
)


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


def test_recipes_use_locked_ingest_and_no_torch_constraints():
    ingest = (ROOT / "requirements-ingest.txt").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints-no-torch.txt").read_text(encoding="utf-8")
    assert "docling-slim[format-office,format-xlsx,convert-core]==2.121.0" in ingest
    assert _DOCLING_META.search(ingest) is None
    assert "torch==0.0.0" in constraints
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        code = _code_lines(text)
        assert "constraints-no-torch.txt" in code, name
        assert "requirements-ingest.txt" in code, name
        assert "find_spec('torch')" in code or 'find_spec("torch")' in code, name
        assert "pip uninstall" not in code, name
        assert _DOCLING_META.search(code) is None, name


def test_from_image_is_digest_pinned():
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert _FROM_DIGEST.search(text), f"{name} must pin python:3.12-slim@sha256:…"


def test_git_sha_is_not_a_build_input():
    """Changing PICO_GIT_SHA must not invalidate Node/pip/docling layers."""
    for name in RECIPES:
        text = (ROOT / name).read_text(encoding="utf-8")
        code = _code_lines(text)
        assert "ARG PICO_GIT_SHA" not in code, name
        assert "ENV PICO_GIT_SHA" not in code, name
    compose = (ROOT / "docker-compose.host.yml").read_text(encoding="utf-8")
    assert "      args:\n        PICO_GIT_SHA:" not in compose
    # Runtime stamp still exists so /health.git_sha can match main.
    assert "      PICO_GIT_SHA: ${PICO_GIT_SHA:-unknown}" in compose
