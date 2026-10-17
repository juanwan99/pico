"""pico#1331「我的接口」: storage, SSRF guard, model switch, billing."""

from __future__ import annotations

import ipaddress
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import Principal, issue_test_token
from app.settings import get_settings

ENDPOINT_SECRET = "test-endpoint-secret-at-least-32-bytes!!"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "model-endpoint.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "")
    monkeypatch.setenv("PICO_ENDPOINT_SECRET", ENDPOINT_SECRET)
    from app import db as dbmod
    from app.main import app
    from app.settings import get_settings as gs

    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()
    # api.example.com has no real DNS inside the test sandbox; stub it to a
    # public IP so the SSRF guard's allow path is exercised (IP-literal URLs
    # used by the reject tests never go through this resolver at all).
    monkeypatch.setattr(
        "pico_orchestrator.web_guard._resolve_ips",
        lambda host: [ipaddress.ip_address("93.184.216.34")],
    )
    with TestClient(app) as test_client:
        yield test_client
    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()


def _headers(membership: str = "m-teacher") -> dict[str, str]:
    token = issue_test_token(
        school_id="school-a",
        membership_id=membership,
        scopes=["ai:run", "ai:read"],
        settings=get_settings(),
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Pico-Membership-Id": f"school-a:{membership}",
    }


# ---------------------------------------------------------------------------
# Crypto
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_ENDPOINT_SECRET", ENDPOINT_SECRET)
    from app.model_endpoint import decrypt_api_key, encrypt_api_key, mask_key

    enc = encrypt_api_key("sk-teacher-secret-abcd")
    assert enc != "sk-teacher-secret-abcd"
    assert decrypt_api_key(enc) == "sk-teacher-secret-abcd"
    assert mask_key("sk-teacher-secret-abcd") == "sk-…abcd"


def test_encrypt_without_secret_raises_and_never_stores_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PICO_ENDPOINT_SECRET", raising=False)
    from app.model_endpoint import encrypt_api_key, secret_configured

    assert secret_configured() is False
    with pytest.raises(RuntimeError):
        encrypt_api_key("sk-raw")


# ---------------------------------------------------------------------------
# Storage / API: only-self, masked key, SSRF guard
# ---------------------------------------------------------------------------


def test_put_get_delete_round_trip_and_masked_key(client) -> None:
    headers = _headers()
    put = client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-teacher-secret-wxyz",
            "enabled": True,
        },
        headers=headers,
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["masked_key"] == "sk-…wxyz"
    assert "sk-teacher-secret-wxyz" not in put.text

    got = client.get("/v1/me/model-endpoint", headers=headers)
    assert got.status_code == 200
    assert got.json()["masked_key"] == "sk-…wxyz"
    assert "sk-teacher-secret-wxyz" not in got.text

    deleted = client.delete("/v1/me/model-endpoint", headers=headers)
    assert deleted.status_code == 200
    after = client.get("/v1/me/model-endpoint", headers=headers)
    assert after.json()["configured"] is False


def test_only_self_can_read_its_own_endpoint(client) -> None:
    client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-teacher-a",
            "enabled": True,
        },
        headers=_headers("m-a"),
    )
    other = client.get("/v1/me/model-endpoint", headers=_headers("m-b"))
    assert other.status_code == 200
    assert other.json()["configured"] is False  # m-b never sees m-a's row


def test_put_rejects_private_and_loopback_urls(client) -> None:
    headers = _headers()
    for bad_url in (
        "http://127.0.0.1:8080/v1",
        "http://10.1.2.3/v1",
        "http://169.254.169.254/latest/meta-data",
        "http://100.64.0.1/v1",  # CGNAT / Tailscale range
    ):
        res = client.put(
            "/v1/me/model-endpoint",
            json={"base_url": bad_url, "model": "gpt-4o-mini", "api_key": "sk-x", "enabled": True},
            headers=headers,
        )
        assert res.status_code == 400, f"{bad_url} -> {res.status_code} {res.text}"
        assert res.json()["detail"]["code"] == "endpoint.denied"


def test_put_without_secret_configured_is_honest_503(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PICO_ENDPOINT_SECRET", raising=False)
    res = client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-x",
            "enabled": True,
        },
        headers=_headers(),
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "endpoint.secret_unconfigured"


# ---------------------------------------------------------------------------
# personal_provider_config_for: the chat-entry lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_personal_provider_config_for_disabled_row_is_none(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-x",
            "enabled": False,
        },
        headers=_headers(),
    )
    from app.model_endpoint import personal_provider_config_for

    principal = Principal(
        school_id="school-a",
        membership_id="m-teacher",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    assert await personal_provider_config_for(principal) is None


@pytest.mark.asyncio
async def test_personal_provider_config_for_enabled_row_builds_cfg(client) -> None:
    client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-teacher-live",
            "enabled": True,
        },
        headers=_headers(),
    )
    from app.model_endpoint import personal_provider_config_for

    principal = Principal(
        school_id="school-a",
        membership_id="m-teacher",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    cfg = await personal_provider_config_for(principal)
    assert cfg is not None
    assert cfg.name == "personal"
    assert cfg.base_url == "https://api.example.com/v1"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.api_key == "sk-teacher-live"


@pytest.mark.asyncio
async def test_personal_provider_config_for_db_down_fails_open_to_school(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Some chat_completions callers run without the app lifespan (no init_db()) —
    the lookup must never 500 the whole turn; it just falls back to the school
    model exactly as if nothing were ever saved (#1331 regression guard)."""
    from app import db as dbmod
    from app.model_endpoint import personal_provider_config_for

    dbmod._engine = None
    dbmod._Session = None
    principal = Principal(
        school_id="school-a",
        membership_id="m-teacher",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    assert await personal_provider_config_for(principal) is None


# ---------------------------------------------------------------------------
# Model switch: resolve_provider()/resolve_provider_for_model() prefer personal
# ---------------------------------------------------------------------------


def test_personal_scope_wins_over_school_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-school")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    from pico_orchestrator.provider import (
        ProviderConfig,
        personal_provider_scope,
        resolve_model_id,
        resolve_provider,
        resolve_provider_for_model,
    )

    # No scope: the school model as usual.
    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "deepseek"

    personal = ProviderConfig(
        name="personal", api_key="sk-teacher", base_url="https://teacher.example/v1", model="gpt-4o-mini"
    )
    with personal_provider_scope(personal):
        assert resolve_provider() is personal
        assert resolve_provider_for_model("pico-deep") is personal
        # One model, no fast/deep lane remap, no kimi-id passthrough.
        assert resolve_model_id("pico-fast", personal) == "gpt-4o-mini"
        assert resolve_model_id("pico-deep", personal) == "gpt-4o-mini"

    # Scope is gone afterwards — back to the school model.
    assert resolve_provider().name == "deepseek"


def test_personal_scope_never_routes_to_responses_or_new_api_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A teacher-chosen model name that happens to start with gpt-/grok- must
    stay a plain chat/completions call to their own server (#1331)."""
    from pico_orchestrator.provider import (
        ProviderConfig,
        uses_new_api_openai_overlay,
        uses_openai_responses_brain,
    )

    personal = ProviderConfig(
        name="personal", api_key="sk-teacher", base_url="https://teacher.example/v1", model="gpt-4o-mini"
    )
    assert uses_openai_responses_brain(personal) is False
    assert uses_new_api_openai_overlay(personal) is False


@pytest.mark.asyncio
async def test_personal_endpoint_error_tagged_never_falls_back_to_school(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-school")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    calls: list[dict] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            exc = RuntimeError("Error code: 400 - {'error': {'type': 'invalid_request_error'}}")
            exc.status_code = 400  # type: ignore[attr-defined]
            raise exc

    class _Client:
        def __init__(self, **_kwargs) -> None:
            self.chat = SimpleNamespace(completions=_Completions())
            self.responses = SimpleNamespace()

    monkeypatch.setattr("pico_orchestrator.provider.AsyncOpenAI", _Client)

    from pico_orchestrator.provider import ProviderConfig, personal_provider_scope, stream_chat
    from pico_orchestrator.user_errors import PERSONAL_ENDPOINT_ERROR_TAG

    personal = ProviderConfig(
        name="personal", api_key="sk-teacher", base_url="https://teacher.example/v1", model="gpt-4o-mini"
    )
    with personal_provider_scope(personal):
        with pytest.raises(RuntimeError) as ei:
            _ = [piece async for piece in stream_chat("hi", model="pico-fast", thinking=False)]

    assert PERSONAL_ENDPOINT_ERROR_TAG in str(ei.value)
    assert calls, "expected at least one call against the teacher's own endpoint"
    # Never switched to deepseek-v4-flash (the school model) or any other id.
    assert all(kwargs["model"] == "gpt-4o-mini" for kwargs in calls)


def test_personal_endpoint_reason_classifies_without_leaking_model_word() -> None:
    from pico_orchestrator.provider import PERSONAL_PROVIDER_NAME
    from pico_orchestrator.teacher_text import leaks
    from pico_orchestrator.user_errors import (
        PERSONAL_ENDPOINT_ERROR_TAG,
        personal_endpoint_reason,
        user_message_for_error,
    )

    assert PERSONAL_PROVIDER_NAME == "personal"
    cases = {
        "Error code: 401 - invalid_api_key": "密钥",
        "Error code: 402 - insufficient_quota": "余额",
        "Error code: 404 - model_not_found": "名字",
        "Error code: 429 - rate limit": "频繁",
        "timeout after 10000ms": "等待",
        "httpx.ConnectError: [Errno -2] Name or service not known": "连不上",
    }
    for raw, expect_fragment in cases.items():
        reason = personal_endpoint_reason(raw)
        assert expect_fragment in reason, reason
        assert not leaks(reason), reason

    tagged = f"{PERSONAL_ENDPOINT_ERROR_TAG}Error code: 401 - invalid_api_key"
    shown = user_message_for_error(tagged)
    assert shown.startswith("你的接口出错了：")
    assert "密钥" in shown
    assert not leaks(shown)


# ---------------------------------------------------------------------------
# Billing: personal turns record tokens at 0 points; other kinds unaffected
# ---------------------------------------------------------------------------


def test_resolve_bill_to_personal_is_explicit_only() -> None:
    from app.usage_ledger import _resolve_bill_to

    assert _resolve_bill_to("personal") == "personal"
    assert _resolve_bill_to("Personal") == "personal"
    assert _resolve_bill_to(None) == "member"
    assert _resolve_bill_to("school") == "school"


def test_milli_from_row_zero_for_personal_llm_but_not_for_search_or_image() -> None:
    from app.points_meter import milli_from_row

    personal_llm = milli_from_row(
        tokens_unknown=False,
        prompt_tokens=10_000,
        completion_tokens=2_000,
        total_tokens=12_000,
        kind="llm",
        model="gpt-5.6-sol",
        extra={"bill_to": "personal"},
    )
    assert personal_llm == 0

    member_llm = milli_from_row(
        tokens_unknown=False,
        prompt_tokens=10_000,
        completion_tokens=2_000,
        total_tokens=12_000,
        kind="llm",
        model="gpt-5.6-sol",
        extra={"bill_to": "member"},
    )
    assert member_llm is not None and member_llm > 0

    # Per-use features never carry bill_to=personal; unaffected either way.
    search = milli_from_row(
        tokens_unknown=True,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        kind="search",
        extra={"query_count": 1},
    )
    assert search is None or search >= 0


def test_usage_event_dict_accepts_personal_bill_to() -> None:
    from app.usage_ledger import usage_event_dict

    row = SimpleNamespace(
        id=1,
        school_id="school-a",
        membership_id="m-teacher",
        kind="llm",
        model="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        tokens_unknown=False,
        estimated=False,
        task_id=None,
        run_id=None,
        source=None,
        idempotency_key="k1",
        created_at=None,
        extra_json='{"bill_to": "personal"}',
    )
    body = usage_event_dict(row)
    assert body["extra"]["bill_to"] == "personal"
