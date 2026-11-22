from __future__ import annotations

import pytest
from app import channel_rates, db
from app.auth import issue_test_token
from app.openai_compat import EDU_SIDEBAR_MARK, _assert_model_allowed, router
from app.settings import Settings, get_settings
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pico_orchestrator import provider, runtime
from pico_orchestrator.edu_sidebar import JSON_ONLY_OUTPUT
from pico_orchestrator.provider import runtime_policy_for_model
from pico_orchestrator.run_types import RunResult
from sqlalchemy import select


def test_rail_trial_model_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_RAIL_TRIAL_MODELS", raising=False)
    settings = Settings(_env_file=None, pico_env="production", pico_allowed_models="pico-fast")
    assert settings.rail_trial_model_set == frozenset()
    with pytest.raises(HTTPException) as rejected:
        _assert_model_allowed("grok-4.6", settings)
    assert rejected.value.status_code == 400

    monkeypatch.setenv("PICO_RAIL_TRIAL_MODELS", " grok-4.6, , deepseek-flash, grok-4.6 ")
    settings = Settings(_env_file=None, pico_env="production", pico_allowed_models="pico-fast")
    assert settings.rail_trial_model_set == {"grok-4.6", "deepseek-flash"}
    with pytest.raises(HTTPException) as rejected:
        _assert_model_allowed("grok-4.6", settings)
    assert rejected.value.status_code == 400


@pytest.fixture
async def rail_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'rail.db'}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "production")
    monkeypatch.setenv("PICO_ACCEPT_TEST_ISSUER", "true")
    monkeypatch.setenv("PICO_ALLOWED_MODELS", "pico-fast,pico-deep")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gemini-3.8-flash")
    monkeypatch.delenv("PICO_CHANNEL_RATES", raising=False)
    monkeypatch.delenv("PICO_CHANNEL_RATES_PATH", raising=False)
    monkeypatch.setattr(channel_rates, "_CARD", None)
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_Session", None)
    get_settings.cache_clear()
    await db.init_db()

    def unexpected_model_call(*args, **kwargs):
        pytest.fail("unexpected model call")

    monkeypatch.setattr(provider, "stream_chat", unexpected_model_call)
    monkeypatch.setattr(runtime, "run_agent_runtime", unexpected_model_call)
    monkeypatch.setattr(runtime, "_edu_sidebar_pi_hint", False, raising=False)
    app = FastAPI()
    app.include_router(router)
    token = issue_test_token(school_id="school-a", membership_id="rail-test", settings=get_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://pico",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
    await db._engine.dispose()
    get_settings.cache_clear()


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    ("configured", "prompt", "expected_backend", "backup"),
    [
        ("", "【模型偏好：grok-4.6】你好", "gemini-3.8-flash", None),
        (" grok-4.6 ", "【模型偏好：grok-4.6】你好", "grok-4.6", None),
        ("grok-4.6", "【模型偏好：grok-4.6】你好", "grok-4.6", "deepseek-flash"),
        ("grok-4.6", "【模型偏好：unlisted-model】你好", "gemini-3.8-flash", None),
        ("grok-4.6", "你好", "gemini-3.8-flash", None),
    ],
)
async def test_sidebar_trial_uses_fast_pi_policy(
    rail_client, monkeypatch, stream, configured, prompt, expected_backend, backup
) -> None:
    monkeypatch.setenv("PICO_RAIL_TRIAL_MODELS", configured)
    get_settings.cache_clear()
    captured = []

    async def fake_pi_run(*, caps, emit, **kwargs):
        captured.append(caps)
        await emit(
            "run.model", {"backend_model": backup or caps.backend_model, "ui_model": caps.ui_model}
        )
        return RunResult(status="succeeded", final_text="你好！")

    monkeypatch.setattr(runtime, "run_agent_runtime", fake_pi_run)
    response = await rail_client.post(
        "/v1/chat/completions",
        json={
            "model": "pico-fast",
            "stream": stream,
            "reasoning_effort": "high",
            "messages": [
                {"role": "system", "content": EDU_SIDEBAR_MARK},
                {"role": "user", "content": prompt},
            ],
        },
    )
    assert response.status_code == 200, response.text
    (caps,) = captured
    policy = runtime_policy_for_model("pico-fast")
    assert caps.backend_model == expected_backend
    assert caps.ui_model == "pico-fast"
    assert caps.thinking_on is False
    assert caps.max_steps == policy["max_steps"]
    assert caps.max_tokens == policy["max_tokens"]
    assert caps.max_context == policy["max_context"]
    assert policy["backend_model"] == "gemini-3.8-flash"

    async with db.session_factory()() as session:
        model = await session.scalar(select(db.UsageEventRow.model))
    assert model == (backup or expected_backend)


@pytest.mark.parametrize(
    ("trial_model", "code"),
    [
        ("gpt-unpriced", "channel.unpriced"),
        ("claude-sonnet-4", "rail_trial.unsupported_model_family"),
    ],
)
async def test_sidebar_rejects_unavailable_trial(rail_client, monkeypatch, trial_model, code) -> None:
    monkeypatch.setenv("PICO_RAIL_TRIAL_MODELS", trial_model)
    get_settings.cache_clear()

    response = await rail_client.post(
        "/v1/chat/completions",
        json={
            "model": "pico-fast",
            "messages": [
                {"role": "system", "content": EDU_SIDEBAR_MARK},
                {"role": "user", "content": f"【模型偏好：{trial_model}】你好"},
            ],
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == code
    if code == "rail_trial.unsupported_model_family":
        assert response.json()["detail"]["message"] == "试用模型族未接线"


@pytest.mark.parametrize(
    ("system", "headers", "prompt"),
    [
        ("你是 Pico", {}, "【模型偏好：grok-4.6】你好"),
        (EDU_SIDEBAR_MARK, {"X-Pico-Output": JSON_ONLY_OUTPUT}, "【模型偏好：grok-4.6】你好"),
        (EDU_SIDEBAR_MARK, {}, "你好"),
    ],
)
async def test_trial_allowlist_does_not_allow_body_model(
    rail_client, monkeypatch, system, headers, prompt
) -> None:
    monkeypatch.setenv("PICO_RAIL_TRIAL_MODELS", "grok-4.6")
    get_settings.cache_clear()

    response = await rail_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "grok-4.6",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "model is not allowed"
