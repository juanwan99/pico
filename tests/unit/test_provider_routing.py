"""E0/E1/E2: default-path model routing — never send Kimi ids to DeepSeek."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import (
    DEFAULT_DEEPSEEK_MODEL,
    owned_by_for_model,
    resolve_model_id,
    resolve_provider,
    resolve_provider_for_model,
)


@pytest.fixture
def deepseek_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)


@pytest.fixture
def both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-test")
    monkeypatch.setenv("KIMI_MODEL", "kimi-k2.6")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")


def test_product_default_provider_is_deepseek(deepseek_only: None) -> None:
    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert cfg.model == "deepseek-chat"


def test_kimi_ui_default_remounts_to_deepseek_when_no_kimi_key(
    deepseek_only: None,
) -> None:
    """Owner repro: default kimi-k2.6 + DeepSeek-only server must not 404."""
    cfg = resolve_provider_for_model("kimi-k2.6")
    assert cfg is not None
    assert cfg.name == "deepseek"
    model_id = resolve_model_id("kimi-k2.6", cfg)
    assert model_id == DEFAULT_DEEPSEEK_MODEL
    assert model_id != "kimi-k2.6"


def test_deepseek_model_stays_on_deepseek(deepseek_only: None) -> None:
    cfg = resolve_provider_for_model("deepseek-chat")
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert resolve_model_id("deepseek-chat", cfg) == "deepseek-chat"
    assert resolve_model_id("deepseek-reasoner", cfg) == "deepseek-reasoner"


def test_agent_model_uses_product_default(deepseek_only: None) -> None:
    cfg = resolve_provider_for_model("pico-agent")
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert resolve_model_id("pico-agent", cfg) == "deepseek-chat"


def test_kimi_model_uses_kimi_when_key_present(both_keys: None) -> None:
    cfg = resolve_provider_for_model("kimi-k2.6")
    assert cfg is not None
    assert cfg.name == "kimi"
    assert resolve_model_id("kimi-k2.6", cfg) == "kimi-k2.6"


def test_preferred_deepseek_when_both_keys(both_keys: None) -> None:
    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "deepseek"


def test_owned_by_is_honest() -> None:
    assert owned_by_for_model("deepseek-chat") == "deepseek"
    assert owned_by_for_model("kimi-k2.6") == "kimi"
    assert owned_by_for_model("pico-agent") == "pico"
    # Never brand DeepSeek rows as pico-kimi
    assert owned_by_for_model("deepseek-chat") != "pico-kimi"


def test_coerce_legacy_kimi_pref_onto_deepseek_allowlist() -> None:
    sys.path.insert(0, str(ROOT / "services" / "api"))
    from app.openai_compat import _coerce_default_model
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        pico_env="production",
        deepseek_api_key="sk-ds",
        pico_model_provider="deepseek",
        pico_allowed_models="deepseek-chat,pico-agent",
    )
    assert _coerce_default_model("kimi-k2.6", settings) == "deepseek-chat"
    assert _coerce_default_model("deepseek-chat", settings) == "deepseek-chat"
    # When Kimi remains allowlisted, keep it
    dual = Settings(
        _env_file=None,
        pico_env="production",
        deepseek_api_key="sk-ds",
        kimi_api_key="sk-kimi",
        pico_model_provider="deepseek",
        pico_allowed_models="deepseek-chat,kimi-k2.6,pico-agent",
    )
    assert _coerce_default_model("kimi-k2.6", dual) == "kimi-k2.6"
