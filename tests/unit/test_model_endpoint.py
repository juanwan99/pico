"""pico#1331「我的接口」: storage, SSRF guard, model switch, billing.

封存 since pico#1349: the tests below run with the switch off; the last test
pins the sealed behaviour live runs with.
"""

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


@pytest.fixture(autouse=True)
def _unsealed(request, monkeypatch):
    if not request.node.name.startswith("test_sealed"):
        monkeypatch.setattr("app.model_endpoint.SEALED", False)


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


_PERSONAL_PRINCIPAL = Principal(
    school_id="school-a",
    membership_id="m-teacher",
    scopes=["ai:run"],
    iss="pico-test-issuer",
    aud="pico-api",
    exp=9999999999,
    raw={},
)


@pytest.mark.asyncio
async def test_personal_provider_config_for_incomplete_row_raises_never_none(
    client,
) -> None:
    """Coordinator review of a66c0078 (1): an *enabled* row that is broken must
    fail the turn, never silently return None (= fall back to the school
    model and bill it as if nothing were saved)."""
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
    # Blank the saved base_url directly (PUT's own validation can never save
    # this; simulates a row gone bad some other way — migration, manual fix).
    from app.db import UserModelEndpointRow, session_factory

    factory = session_factory()
    async with factory() as session:
        row = await session.get(UserModelEndpointRow, ("school-a", "m-teacher"))
        row.base_url = ""
        await session.commit()

    from app.model_endpoint import personal_provider_config_for
    from pico_orchestrator.user_errors import (
        PERSONAL_ENDPOINT_ERROR_TAG,
        personal_endpoint_reason,
        user_message_for_error,
    )

    with pytest.raises(RuntimeError) as excinfo:
        await personal_provider_config_for(_PERSONAL_PRINCIPAL)
    raw = str(excinfo.value)
    assert raw.startswith(PERSONAL_ENDPOINT_ERROR_TAG)
    assert personal_endpoint_reason(raw[len(PERSONAL_ENDPOINT_ERROR_TAG) :]) == (
        "密钥读不出来，请在『我的接口』里重新保存"
    )
    assert user_message_for_error(raw) == "你的接口出错了：密钥读不出来，请在『我的接口』里重新保存"


@pytest.mark.asyncio
async def test_personal_provider_config_for_decrypt_failure_raises_never_none(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Secret rotated after the row was saved: decrypt fails — must still
    refuse the turn, never fall back to the school model."""
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
    monkeypatch.setenv("PICO_ENDPOINT_SECRET", "a-totally-different-rotated-secret!!")

    from app.model_endpoint import personal_provider_config_for
    from pico_orchestrator.user_errors import PERSONAL_ENDPOINT_ERROR_TAG

    with pytest.raises(RuntimeError) as excinfo:
        await personal_provider_config_for(_PERSONAL_PRINCIPAL)
    raw = str(excinfo.value)
    assert raw.startswith(PERSONAL_ENDPOINT_ERROR_TAG)
    assert "endpoint_key_undecryptable" in raw


@pytest.mark.asyncio
async def test_personal_provider_config_for_unsafe_url_at_use_time_raises(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coordinator review of a66c0078 (2): base_url is re-checked for SSRF at
    use time (every turn), not only at PUT — a DNS change after saving (e.g.
    now resolving into a private/metadata/Tailscale range) must refuse the
    turn rather than silently dialing an internal address."""
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
    # DNS for api.example.com "changed" to a Tailscale-range address.
    monkeypatch.setattr(
        "pico_orchestrator.web_guard._resolve_ips",
        lambda host: [ipaddress.ip_address("100.64.1.1")],
    )

    from app.model_endpoint import personal_provider_config_for
    from pico_orchestrator.user_errors import PERSONAL_ENDPOINT_ERROR_TAG

    with pytest.raises(RuntimeError) as excinfo:
        await personal_provider_config_for(_PERSONAL_PRINCIPAL)
    raw = str(excinfo.value)
    assert raw.startswith(PERSONAL_ENDPOINT_ERROR_TAG)
    assert "拒绝访问" in raw or "内网" in raw


def test_chat_completions_with_broken_personal_row_refuses_no_fallback_billing(
    client, tmp_path
) -> None:
    """End-to-end: a broken enabled row must make /v1/chat/completions refuse
    the turn with a teacher-facing 「你的接口出错了」message, 502, and record
    *no* usage_events row at all — not a school-billed fallback row."""
    headers = _headers()
    client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-teacher-live",
            "enabled": True,
        },
        headers=headers,
    )
    monkeypatch_secret = "a-totally-different-rotated-secret-for-e2e!!"
    import os

    old = os.environ.get("PICO_ENDPOINT_SECRET")
    os.environ["PICO_ENDPOINT_SECRET"] = monkeypatch_secret
    try:
        resp = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={
                "model": "pico-fast",
                "messages": [{"role": "user", "content": "你好"}],
                "stream": False,
            },
        )
    finally:
        if old is not None:
            os.environ["PICO_ENDPOINT_SECRET"] = old
        else:
            os.environ.pop("PICO_ENDPOINT_SECRET", None)

    assert resp.status_code == 502, resp.text
    assert "你的接口出错了" in resp.text
    assert "重新保存" in resp.text

    import sqlite3

    database = tmp_path / "model-endpoint.db"
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT COUNT(*) FROM usage_events WHERE school_id='school-a' AND membership_id='m-teacher' AND kind='llm'"
    ).fetchone()
    con.close()
    assert rows[0] == 0


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
    with personal_provider_scope(personal), pytest.raises(RuntimeError) as ei:
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


# ---------------------------------------------------------------------------
# Vision: 看图 must never forward a school vision model id to the teacher's
# own endpoint (#1331 coordinator follow-up).
# ---------------------------------------------------------------------------

# 1x1 transparent PNG — just needs to be valid base64 + decodable bytes.
_TINY_PNG_DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
    "EQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_personal_cfg_for_images_drops_scope_when_personal_model_cannot_see() -> None:
    """The card: 看图仍走学校的视觉模型、照扣 — never with the teacher's key."""
    from app.openai_compat import _personal_cfg_for_images

    cfg = SimpleNamespace(name="personal", model="deepseek-chat")
    assert _personal_cfg_for_images(cfg, [{"type": "image", "data": "x"}]) is None
    # No images at all: untouched, even though the model still can't see.
    assert _personal_cfg_for_images(cfg, []) is cfg
    assert _personal_cfg_for_images(cfg, None) is cfg
    # No personal scope to begin with: stays None either way.
    assert _personal_cfg_for_images(None, [{"type": "image", "data": "x"}]) is None


def test_personal_cfg_for_images_keeps_scope_when_personal_model_can_see() -> None:
    from app.openai_compat import _personal_cfg_for_images

    cfg = SimpleNamespace(name="personal", model="gpt-4o-mini")
    assert _personal_cfg_for_images(cfg, [{"type": "image", "data": "x"}]) is cfg
    assert _personal_cfg_for_images(cfg, []) is cfg


def _put_personal_endpoint(client, headers, *, model: str) -> None:
    resp = client.put(
        "/v1/me/model-endpoint",
        json={
            "base_url": "https://api.example.com/v1",
            "model": model,
            "api_key": "sk-teacher-live",
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def _bill_to_for_last_llm_row(tmp_path) -> str | None:
    import json
    import sqlite3

    database = tmp_path / "model-endpoint.db"
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    row = con.execute(
        "SELECT extra_json FROM usage_events WHERE kind='llm' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    con.close()
    if row is None:
        return None
    return json.loads(row[0] or "{}").get("bill_to")


def test_chat_completions_image_on_non_vision_personal_model_runs_on_school_not_personal(
    client, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Agent path (model=pico-fast): the teacher's own model can't read
    images, so this turn must run on the *school* provider — never send
    DEFAULT_DEEPSEEK_VISION (a school model id) to the teacher's own
    base_url — and bill normally (bill_to != personal)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-school")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    headers = _headers()
    _put_personal_endpoint(client, headers, model="deepseek-chat")  # not vision-capable

    captured: dict = {}

    async def _fake_run_agent_runtime(**kwargs):
        from pico_orchestrator.provider import resolve_provider
        from pico_orchestrator.run_types import RunResult

        caps = kwargs["caps"]
        provider = resolve_provider()
        captured["provider_name"] = getattr(provider, "name", None)
        captured["backend_model"] = getattr(caps, "backend_model", None)
        return RunResult(
            status="succeeded",
            final_text="看到了，图里是……",
            token_usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
        )

    monkeypatch.setattr(
        "pico_orchestrator.runtime.run_agent_runtime", _fake_run_agent_runtime
    )

    resp = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "pico-fast",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "看这张图"},
                        {"type": "image_url", "image_url": {"url": _TINY_PNG_DATA_URL}},
                    ],
                }
            ],
            "stream": False,
        },
    )

    assert resp.status_code == 200, resp.text
    assert captured["provider_name"] != "personal"
    assert "vision" in str(captured["backend_model"] or "").lower()
    assert _bill_to_for_last_llm_row(tmp_path) != "personal"


def test_chat_completions_image_on_vision_capable_personal_model_stays_personal(
    client, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same shape, but the teacher's own model *can* see — must stay
    personal (own key, own base_url, 0 llm points billed as personal)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-school")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    headers = _headers()
    _put_personal_endpoint(client, headers, model="gpt-4o-mini")  # vision-capable

    captured: dict = {}

    async def _fake_run_agent_runtime(**kwargs):
        from pico_orchestrator.provider import resolve_provider
        from pico_orchestrator.run_types import RunResult

        caps = kwargs["caps"]
        provider = resolve_provider()
        captured["provider_name"] = getattr(provider, "name", None)
        captured["backend_model"] = getattr(caps, "backend_model", None)
        return RunResult(
            status="succeeded",
            final_text="看到了，图里是……",
            token_usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
        )

    monkeypatch.setattr(
        "pico_orchestrator.runtime.run_agent_runtime", _fake_run_agent_runtime
    )

    resp = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "pico-fast",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "看这张图"},
                        {"type": "image_url", "image_url": {"url": _TINY_PNG_DATA_URL}},
                    ],
                }
            ],
            "stream": False,
        },
    )

    assert resp.status_code == 200, resp.text
    assert captured["provider_name"] == "personal"
    assert captured["backend_model"] == "gpt-4o-mini"
    assert _bill_to_for_last_llm_row(tmp_path) == "personal"


@pytest.mark.asyncio
async def test_sealed_hides_the_routes_and_never_reads_a_saved_endpoint(client, monkeypatch) -> None:
    """pico#1349 封存: owner 10-18「先下线功能，代码暂时不删除」."""
    from app import model_endpoint

    assert model_endpoint.SEALED is True
    for method, path in (
        ("get", "/v1/me/model-endpoint"),
        ("put", "/v1/me/model-endpoint"),
        ("delete", "/v1/me/model-endpoint"),
        ("post", "/v1/me/model-endpoint/test"),
    ):
        assert getattr(client, method)(path, headers=_headers()).status_code == 404

    async def boom(*_a, **_kw):
        raise AssertionError("sealed: no lookup")

    monkeypatch.setattr(model_endpoint, "_get_row", boom)
    assert await model_endpoint.personal_provider_config_for(_PERSONAL_PRINCIPAL) is None

