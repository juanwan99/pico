"""True-Pi phase-1 flags and paths.

Environment (documented · no secrets):
  PICO_TRUE_PI_SHADOW=1   — after hosted multi-step, run shadow + write diff
  PICO_TRUE_PI_BYPASS=1   — allow explicit run_true_pi_agent as primary (tests/ops only)
  PICO_TRUE_PI_BIN        — pi executable (default: pi)
  PICO_TRUE_PI_PACKAGE    — npm package pin for install docs
  PICO_TRUE_PI_SESSION_ROOT — session dir parent (default: tmp)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

TRUE_PI_SHADOW_ENV = "PICO_TRUE_PI_SHADOW"
TRUE_PI_BYPASS_ENV = "PICO_TRUE_PI_BYPASS"
TRUE_PI_BIN_ENV = "PICO_TRUE_PI_BIN"
TRUE_PI_PACKAGE_ENV = "PICO_TRUE_PI_PACKAGE"
TRUE_PI_SESSION_ROOT_ENV = "PICO_TRUE_PI_SESSION_ROOT"

# npm pin for deploy notes (not auto-installed into default image in phase 1)
PINNED_PI_PACKAGE = "@mariozechner/pi-coding-agent@0.73.1"
RUNTIME_LABEL = "pi-true"
HOSTED_RUNTIME_LABEL = "pi-agent"

# Thin bridge allowlist — do not expand without ADR revision.
ALLOWED_GATEWAY_TOOLS: frozenset[str] = frozenset(
    {
        "workspace_list_files",
        "workspace_read_file",
        "workspace_write_file",
        "generate_html_document",
        "generate_docx_document",
        "generate_pptx_document",
        "verify_html_document",
    }
)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def shadow_enabled() -> bool:
    return _truthy(TRUE_PI_SHADOW_ENV)


def bypass_enabled() -> bool:
    """Explicit bypass entry only — never production default."""
    return _truthy(TRUE_PI_BYPASS_ENV)


def pi_bin() -> str:
    return os.environ.get(TRUE_PI_BIN_ENV, "pi").strip() or "pi"


def pinned_package() -> str:
    return os.environ.get(TRUE_PI_PACKAGE_ENV, PINNED_PI_PACKAGE).strip() or PINNED_PI_PACKAGE


def session_root() -> Path:
    raw = os.environ.get(TRUE_PI_SESSION_ROOT_ENV, "").strip()
    if raw:
        return Path(raw)
    return Path(os.environ.get("TMPDIR", "/tmp")) / "pico-true-pi-sessions"


def extension_path() -> Path:
    """Path to the Node extension that registers Pico gateway tools."""
    here = Path(__file__).resolve()
    # services/orchestrator/pico_orchestrator/true_pi → repo root services/true_pi_bridge
    return here.parents[3] / "true_pi_bridge" / "pico-gateway-tools.ts"


def true_pi_available() -> bool:
    """Whether a pi binary is on PATH (or absolute PICO_TRUE_PI_BIN)."""
    binary = pi_bin()
    if Path(binary).is_file() and os.access(binary, os.X_OK):
        return True
    return shutil.which(binary) is not None


def health_fields() -> dict[str, object]:
    """Observability only — must not change default_runtime."""
    return {
        "true_pi_shadow_enabled": shadow_enabled(),
        "true_pi_bypass_enabled": bypass_enabled(),
        "true_pi_binary_available": true_pi_available(),
        "true_pi_package_pin": pinned_package(),
        "true_pi_runtime_label": RUNTIME_LABEL,
        # Honest naming: product default remains hosted loop until phase 2.
        "true_pi_phase": "p1-shadow",
    }
