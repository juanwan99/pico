"""True-Pi flags and paths (phase 1 shadow + phase 2 cutover).

Environment (documented · no secrets):
  PICO_TRUE_PI_SHADOW=1      — after hosted multi-step, run shadow + write diff
  PICO_TRUE_PI_BYPASS=1      — force true-pi for all multi-step (ops/test)
  PICO_TRUE_PI_DEFAULT=1     — production default multi-step = true Pi
  PICO_TRUE_PI_CANARY        — joint keys school:member,... or * (gray release)
  PICO_HOSTED_LOOP=1         — force hosted pi_runtime (rollback one-shot)
  PICO_TRUE_PI_BIN           — pi executable (default: pi)
  PICO_TRUE_PI_PACKAGE       — npm package pin
  PICO_TRUE_PI_SESSION_ROOT  — session dir parent
  PICO_TRUE_PI_HISTORY_N     — max history turns injected (default 10)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Collection
from pathlib import Path

TRUE_PI_SHADOW_ENV = "PICO_TRUE_PI_SHADOW"
TRUE_PI_BYPASS_ENV = "PICO_TRUE_PI_BYPASS"
TRUE_PI_DEFAULT_ENV = "PICO_TRUE_PI_DEFAULT"
TRUE_PI_CANARY_ENV = "PICO_TRUE_PI_CANARY"
HOSTED_LOOP_ENV = "PICO_HOSTED_LOOP"
TRUE_PI_BIN_ENV = "PICO_TRUE_PI_BIN"
TRUE_PI_PACKAGE_ENV = "PICO_TRUE_PI_PACKAGE"
TRUE_PI_SESSION_ROOT_ENV = "PICO_TRUE_PI_SESSION_ROOT"
TRUE_PI_HISTORY_N_ENV = "PICO_TRUE_PI_HISTORY_N"

# npm pin for deploy notes
PINNED_PI_PACKAGE = "@mariozechner/pi-coding-agent@0.73.1"
RUNTIME_LABEL = "pi-true"
HOSTED_RUNTIME_LABEL = "pi-agent"

# Thin bridge allowlist — #516 added B2 browser tools (still no shell).
ALLOWED_GATEWAY_TOOLS: frozenset[str] = frozenset(
    {
        "workspace_list_files",
        "workspace_read_file",
        "workspace_write_file",
        "generate_html_document",
        "generate_docx_document",
        "generate_pptx_document",
        "edit_docx_document",
        "edit_pptx_document",
        "generate_image",
        "verify_html_document",
        "web_search",
        "web_fetch",
        "kb_search",
        "sandbox_preview_inspect",
        "sandbox_workspace_exec",
        "sandbox_browser_open",
        "sandbox_browser_screenshot",
        "sandbox_document_open",
    }
)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def shadow_enabled() -> bool:
    return _truthy(TRUE_PI_SHADOW_ENV)


def bypass_enabled() -> bool:
    """Force true-pi path (ops / explicit)."""
    return _truthy(TRUE_PI_BYPASS_ENV)


def true_pi_default_enabled() -> bool:
    """When set, multi-step defaults to true Pi (unless hosted loop forced)."""
    return _truthy(TRUE_PI_DEFAULT_ENV)


def hosted_loop_forced() -> bool:
    """Rollback: force hosted pi_runtime regardless of true-pi default/canary."""
    return _truthy(HOSTED_LOOP_ENV)


def pi_bin() -> str:
    raw = os.environ.get(TRUE_PI_BIN_ENV, "pi").strip() or "pi"
    if Path(raw).is_file():
        return raw
    found = shutil.which(raw)
    return found or raw


def pinned_package() -> str:
    return os.environ.get(TRUE_PI_PACKAGE_ENV, PINNED_PI_PACKAGE).strip() or PINNED_PI_PACKAGE


def session_root() -> Path:
    raw = os.environ.get(TRUE_PI_SESSION_ROOT_ENV, "").strip()
    if raw:
        return Path(raw)
    return Path(os.environ.get("TMPDIR", "/tmp")) / "pico-true-pi-sessions"


_SAFE_SEG = re.compile(r"[^A-Za-z0-9._-]+")


def session_segment(raw: str, *, max_len: int = 80) -> str:
    """Path-safe school/convo segment. Never '..' or empty."""
    text = (raw or "").strip()
    if not text:
        return "unknown"
    safe = _SAFE_SEG.sub("_", text).strip("._")[:max_len]
    if not safe or safe in {".", ".."}:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
    return safe


def persist_session_dir(*, school_id: str, conversation_id: str | None) -> Path | None:
    """Workbench Pi session tree: school_id / conversation_id.

    Missing either side → None (caller must use a per-run dir). Cross-tenant
    reuse is a REVISE.
    """
    school = (school_id or "").strip()
    convo = (conversation_id or "").strip()
    if not school or not convo:
        return None
    return session_root() / session_segment(school) / session_segment(convo)


def history_n() -> int:
    raw = os.environ.get(TRUE_PI_HISTORY_N_ENV, "10").strip() or "10"
    try:
        return max(0, min(40, int(raw)))
    except ValueError:
        return 10


def extension_path() -> Path:
    """Path to the Node extension that registers Pico gateway tools."""
    here = Path(__file__).resolve()
    return here.parents[3] / "true_pi_bridge" / "pico-gateway-tools.ts"


def plan_mode_extension_path() -> Path:
    """Official 0.73.1 plan-mode (vendored). Override with PICO_TRUE_PI_PLAN_MODE_EXT."""
    override = os.environ.get("PICO_TRUE_PI_PLAN_MODE_EXT", "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    return (
        here.parents[3]
        / "true_pi_bridge"
        / "vendor"
        / "pi-0.73.1"
        / "plan-mode"
        / "index.ts"
    )


def true_pi_available() -> bool:
    """Whether a pi binary is on PATH (or absolute PICO_TRUE_PI_BIN)."""
    binary = pi_bin()
    if Path(binary).is_file() and os.access(binary, os.X_OK):
        return True
    return shutil.which(binary) is not None


def parse_canary_entries(raw: str | None = None) -> list[str]:
    text = (raw if raw is not None else os.environ.get(TRUE_PI_CANARY_ENV, "")).strip()
    if not text:
        return []
    return [p.strip() for p in text.split(",") if p.strip()]


def canary_allows_principal(
    *,
    school_id: str,
    membership_id: str,
    canary: Collection[str] | None = None,
) -> bool:
    """True when canary list is * / *:* or contains school:membership."""
    entries = list(canary) if canary is not None else parse_canary_entries()
    if not entries:
        return False
    school = (school_id or "").strip()
    membership = (membership_id or "").strip()
    for entry in entries:
        token = entry.strip()
        if token in {"*", "*:*"}:
            return True
        if ":" not in token:
            # membership-only token
            if membership and token == membership:
                return True
            continue
        s, m = token.split(":", 1)
        if s.strip() == school and m.strip() == membership:
            return True
    return False


def should_use_true_pi(
    *,
    school_id: str = "",
    membership_id: str = "",
    canary: Collection[str] | None = None,
) -> bool:
    """Dispatch gate: true Pi vs hosted pi_runtime.

    Priority:
      1. PICO_HOSTED_LOOP=1 → hosted (rollback)
      2. PICO_TRUE_PI_BYPASS=1 → true
      3. PICO_TRUE_PI_DEFAULT=1 → true
      4. canary match → true
      5. else hosted
    """
    if hosted_loop_forced():
        return False
    if bypass_enabled():
        return True
    if true_pi_default_enabled():
        return True
    return canary_allows_principal(
        school_id=school_id,
        membership_id=membership_id,
        canary=canary,
    )


def active_runtime_label(
    *,
    school_id: str = "",
    membership_id: str = "",
) -> str:
    if should_use_true_pi(school_id=school_id, membership_id=membership_id):
        return RUNTIME_LABEL
    return HOSTED_RUNTIME_LABEL


def default_runtime_for_health() -> str:
    """Honest product default name for /health (no principal context)."""
    if hosted_loop_forced():
        return HOSTED_RUNTIME_LABEL
    if true_pi_default_enabled() or bypass_enabled():
        return RUNTIME_LABEL
    # Canary-only does not change global default label
    return HOSTED_RUNTIME_LABEL


def true_pi_phase_label() -> str:
    """Finite phase enum for health (name matches real mode).

    hosted-rollback > p2-default > p2-bypass > p2-canary > p1-shadow > idle
    """
    if hosted_loop_forced():
        return "hosted-rollback"
    if true_pi_default_enabled():
        return "p2-default"
    if bypass_enabled():
        return "p2-bypass"
    if parse_canary_entries():
        return "p2-canary"
    if shadow_enabled():
        return "p1-shadow"
    return "idle"


def health_fields() -> dict[str, object]:
    """Observability for true-Pi path."""
    canary = parse_canary_entries()
    return {
        "true_pi_shadow_enabled": shadow_enabled(),
        "true_pi_bypass_enabled": bypass_enabled(),
        "true_pi_default_enabled": true_pi_default_enabled(),
        "true_pi_hosted_loop_forced": hosted_loop_forced(),
        "true_pi_canary_configured": len(canary) > 0,
        "true_pi_canary_entry_count": len(canary),
        "true_pi_binary_available": true_pi_available(),
        "true_pi_package_pin": pinned_package(),
        "true_pi_runtime_label": RUNTIME_LABEL,
        "true_pi_phase": true_pi_phase_label(),
        "true_pi_rollback_flag": HOSTED_LOOP_ENV,
    }
