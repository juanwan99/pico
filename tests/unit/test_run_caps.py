"""Tiered run budgets (P-COMPLEX-DONE package A).

Loads modules by path so hosts without kimi_cli / pydantic still exercise defaults.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ORCH = ROOT / "services" / "orchestrator" / "pico_orchestrator"


def _load_isolated(name: str, path: Path, *, deps: dict | None = None):
    """Load a module file without executing package __init__."""
    if deps:
        for key, mod in deps.items():
            sys.modules[key] = mod
    # Ensure parent package is a lightweight namespace (no __init__ side effects).
    if "pico_orchestrator" not in sys.modules:
        pkg = types.ModuleType("pico_orchestrator")
        pkg.__path__ = [str(_ORCH)]  # type: ignore[attr-defined]
        sys.modules["pico_orchestrator"] = pkg
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    # Stub heavy imports used only by provider_label in run_types.
    if name.endswith("run_types") and "pico_orchestrator.provider" not in sys.modules:
        stub = types.ModuleType("pico_orchestrator.provider")

        class ProviderConfig:
            pass

        def resolve_provider():
            return None

        stub.ProviderConfig = ProviderConfig
        stub.resolve_provider = resolve_provider
        sys.modules["pico_orchestrator.provider"] = stub
    spec.loader.exec_module(mod)
    return mod


_run_types = _load_isolated("pico_orchestrator.run_types", _ORCH / "run_types.py")
_run_caps = _load_isolated(
    "pico_orchestrator.run_caps",
    _ORCH / "run_caps.py",
    deps={"pico_orchestrator.run_types": _run_types},
)

RunCaps = _run_types.RunCaps
DELIVERY_MAX_SECONDS = _run_caps.DELIVERY_MAX_SECONDS
DELIVERY_MAX_STEPS = _run_caps.DELIVERY_MAX_STEPS
DELIVERY_MAX_TOKENS = _run_caps.DELIVERY_MAX_TOKENS
SHORT_MAX_SECONDS = _run_caps.SHORT_MAX_SECONDS
caps_for_tier = _run_caps.caps_for_tier
spend_caps_public = _run_caps.spend_caps_public


def test_delivery_defaults_are_900s_not_120() -> None:
    assert DELIVERY_MAX_SECONDS == 900
    assert DELIVERY_MAX_SECONDS > 120
    assert DELIVERY_MAX_STEPS >= 16
    assert DELIVERY_MAX_TOKENS >= 16_000
    bare = RunCaps()
    assert bare.max_seconds == 900
    assert bare.max_steps == 24


def test_short_tier_stays_fast() -> None:
    short = caps_for_tier("short")
    delivery = caps_for_tier("delivery")
    assert short.max_seconds == SHORT_MAX_SECONDS == 120
    assert short.max_seconds < delivery.max_seconds
    # LAW #865: short is a wall-clock lane, not a smaller model window.
    assert short.max_tokens == delivery.max_tokens == 32_000
    assert short.max_context == delivery.max_context == 256_000


def test_settings_delivery_and_short_caps() -> None:
    sys.path.insert(0, str(ROOT / "services" / "api"))
    try:
        from app.settings import Settings
    except ModuleNotFoundError as exc:
        import pytest

        pytest.skip(f"settings deps unavailable: {exc}")
    settings = Settings(_env_file=None)
    delivery = settings.delivery_run_caps()
    short = settings.short_run_caps()
    assert delivery.max_seconds == 900
    assert delivery.max_steps == 24
    assert short.max_seconds == 120
    public = settings.spend_caps_dict()
    assert public["max_seconds"] == 900
    assert public["delivery"]["max_seconds"] == 900
    assert public["short"]["max_seconds"] == 120
    assert "max_steps" in public


def test_env_override_delivery_seconds() -> None:
    sys.path.insert(0, str(ROOT / "services" / "api"))
    try:
        from app.settings import Settings
    except ModuleNotFoundError as exc:
        import pytest

        pytest.skip(f"settings deps unavailable: {exc}")
    settings = Settings(
        _env_file=None,
        pico_run_max_seconds=600,
        pico_run_max_steps=12,
    )
    caps = settings.delivery_run_caps(skill_instruction="x")
    assert caps.max_seconds == 600
    assert caps.max_steps == 12
    assert caps.skill_instruction == "x"


def test_spend_caps_public_shape() -> None:
    snap = spend_caps_public(
        delivery_seconds=900,
        delivery_tokens=32000,
        delivery_steps=24,
        delivery_retries=2,
        short_seconds=120,
        short_tokens=8000,
    )
    assert snap["delivery"]["max_seconds"] == 900
    assert snap["short"]["max_seconds"] == 120


def test_c1_fast_context_is_128k_not_output() -> None:
    """#865: fast/short use the real 256k window. Tokens ≠ context."""
    short = caps_for_tier("short")
    fast = spend_caps_public(
        delivery_seconds=900,
        delivery_tokens=32000,
        delivery_steps=24,
        delivery_retries=2,
        short_seconds=120,
        short_tokens=32000,
    )["fast"]
    assert short.max_context == 256_000
    assert fast["max_context"] == 256_000
    assert short.max_tokens == 32_000
    assert fast["max_tokens"] == 32_000
    assert short.max_tokens != short.max_context


def test_c2_deep_context_is_256k_not_output() -> None:
    delivery = caps_for_tier("delivery")
    deep = spend_caps_public(
        delivery_seconds=900,
        delivery_tokens=32000,
        delivery_steps=24,
        delivery_retries=2,
        short_seconds=120,
        short_tokens=8000,
    )["deep"]
    assert delivery.max_context == 256_000
    assert deep["max_context"] == 256_000
    assert delivery.max_tokens == 32_000
    assert deep["max_tokens"] == 32_000
    assert delivery.max_tokens != 256_000
    assert delivery.max_context != delivery.max_tokens
