from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import issue_test_token
from app.openai_compat import (
    _assert_model_allowed,
    _effective_max_tokens,
    _principal_from_auth,
)
from app.rate_limit import ChatAdmission, _rate_limit_key
from app.settings import Settings


def test_host_shell_models_follow_api_allowlist() -> None:
    compose = (ROOT / "docker-compose.host.yml").read_text()
    assert "OPENAI_MODELS: ${PICO_ALLOWED_MODELS:?set PICO_ALLOWED_MODELS}" in compose
    assert "OPENAI_MODELS: moonshot-v1-8k" not in compose


def _valid_production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "pico_env": "production",
        "pico_jwt_secret": "jwt-" + "a" * 40,
        "pico_accept_test_issuer": False,
        "pico_openai_proxy_key": "proxy-" + "b" * 40,
        "kimi_api_key": "model-key",
        "pico_allowed_models": "kimi-k2.6,pico-agent",
        "pico_chat_rpm": 30,
        "pico_chat_max_concurrent": 2,
        "pico_run_max_tokens": 4096,
        "pico_dangerous_tools_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"pico_jwt_secret": "change-me-dev-only-not-for-prod-32b!"}, "PICO_JWT_SECRET"),
        ({"pico_jwt_secret": ""}, "PICO_JWT_SECRET"),
        ({"pico_openai_proxy_key": "pico-dev"}, "PICO_OPENAI_PROXY_KEY"),
        ({"kimi_api_key": "", "deepseek_api_key": ""}, "KIMI_API_KEY"),
        ({"pico_allowed_models": ""}, "PICO_ALLOWED_MODELS"),
        ({"pico_allowed_models": "pico-agent"}, "provider model"),
    ],
)
def test_production_configuration_fails_closed(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _valid_production(**overrides).validate_production()


def test_production_rejects_test_issuer_without_break_glass() -> None:
    with pytest.raises(ValueError, match="BREAK_GLASS"):
        _valid_production(pico_accept_test_issuer=True).validate_production()


def test_production_break_glass_is_explicit_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    settings = _valid_production(
        pico_accept_test_issuer=True,
        pico_allow_test_issuer_break_glass=True,
    )
    settings.validate_production()
    assert "SECURITY BREAK-GLASS" in caplog.text


def test_production_rejects_default_proxy_but_accepts_strong_internal_proxy() -> None:
    settings = _valid_production()
    with pytest.raises(HTTPException) as rejected:
        _principal_from_auth("Bearer pico-dev", settings)
    assert rejected.value.status_code == 401

    principal = _principal_from_auth(
        f"Bearer {settings.pico_openai_proxy_key}",
        settings,
    )
    assert principal.raw["proxy"] is True


def test_production_model_allowlist_rejects_unknown() -> None:
    settings = _valid_production()
    _assert_model_allowed("openAI/kimi-k2.6", settings)
    with pytest.raises(HTTPException) as rejected:
        _assert_model_allowed("unknown-expensive-model", settings)
    assert rejected.value.status_code == 400


def test_requested_tokens_are_clamped_to_global_cap() -> None:
    assert _effective_max_tokens(999_999, 4096) == 4096
    assert _effective_max_tokens(512, 4096) == 512
    assert _effective_max_tokens(None, 1024) == 1024


async def test_chat_admission_enforces_concurrency_and_rpm() -> None:
    admission = ChatAdmission()
    assert await admission.acquire("ip", rpm=2, max_concurrent=1) is None
    assert await admission.acquire("ip", rpm=2, max_concurrent=1) == "concurrency_limit"
    await admission.release("ip")
    assert await admission.acquire("ip", rpm=2, max_concurrent=1) is None
    await admission.release("ip")
    assert await admission.acquire("ip", rpm=2, max_concurrent=1) == "rate_limit"


async def test_chat_admission_isolated_by_membership_on_same_ip() -> None:
    settings = Settings()
    shared_scope = {
        "client": ("203.0.113.10", 1234),
        "headers": [],
    }

    def key_for(member: str) -> str:
        token = issue_test_token(
            school_id="school-a",
            membership_id=member,
            settings=settings,
        )
        scope = {
            **shared_scope,
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
        return _rate_limit_key(scope, settings)

    member_a = key_for("member-a")
    member_b = key_for("member-b")
    assert member_a != member_b

    admission = ChatAdmission()
    assert await admission.acquire(member_a, rpm=1, max_concurrent=1) is None
    await admission.release(member_a)
    assert await admission.acquire(member_a, rpm=1, max_concurrent=1) == "rate_limit"
    assert await admission.acquire(member_b, rpm=1, max_concurrent=1) is None
    await admission.release(member_b)


def test_chat_rate_limit_falls_back_to_ip_without_principal() -> None:
    scope = {"client": ("203.0.113.10", 1234), "headers": []}
    assert _rate_limit_key(scope, Settings()) == "ip:203.0.113.10"
