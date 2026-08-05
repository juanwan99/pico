"""Durable job unit tests (package B) — offline-friendly where possible."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ORCH = ROOT / "services" / "orchestrator" / "pico_orchestrator"


def _load_isolated(name: str, path: Path):
    if "pico_orchestrator" not in sys.modules:
        pkg = types.ModuleType("pico_orchestrator")
        pkg.__path__ = [str(_ORCH)]  # type: ignore[attr-defined]
        sys.modules["pico_orchestrator"] = pkg
    if name.endswith("run_types") and "pico_orchestrator.provider" not in sys.modules:
        stub = types.ModuleType("pico_orchestrator.provider")

        class ProviderConfig:
            pass

        def resolve_provider():
            return None

        stub.ProviderConfig = ProviderConfig
        stub.resolve_provider = resolve_provider
        sys.modules["pico_orchestrator.provider"] = stub
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_durable_tier_defaults() -> None:
    _load_isolated("pico_orchestrator.run_types", _ORCH / "run_types.py")
    caps_mod = _load_isolated("pico_orchestrator.run_caps", _ORCH / "run_caps.py")
    assert caps_mod.DURABLE_MAX_SECONDS == 3600
    assert caps_mod.DURABLE_MAX_SECONDS > caps_mod.DELIVERY_MAX_SECONDS
    durable = caps_mod.caps_for_tier("durable")
    delivery = caps_mod.caps_for_tier("delivery")
    assert durable.max_seconds >= 1800
    assert durable.max_seconds > delivery.max_seconds
    pub = caps_mod.spend_caps_public(
        delivery_seconds=900,
        delivery_tokens=32000,
        delivery_steps=24,
        delivery_retries=2,
        short_seconds=120,
        short_tokens=8000,
        durable_seconds=3600,
        detach_on_disconnect=True,
    )
    assert pub["durable"]["max_seconds"] == 3600
    assert pub["durable"]["detach_on_disconnect"] is True


def test_settings_detach_default_true() -> None:
    sys.path.insert(0, str(ROOT / "services" / "api"))
    try:
        from app.settings import Settings
    except ModuleNotFoundError as exc:
        import pytest

        pytest.skip(f"settings deps unavailable: {exc}")
    s = Settings(_env_file=None)
    assert s.pico_run_detach_on_disconnect is True
    assert s.pico_run_durable_max_seconds == 3600
    d = s.durable_run_caps()
    assert d.max_seconds == 3600
    snap = s.spend_caps_dict()
    assert snap["durable"]["detach_on_disconnect"] is True
