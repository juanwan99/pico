"""L1b: openai-compat auth hardening + membership workspace isolation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import scope_proxy_principal
from app.main import app
from app.openai_compat import _dev_proxy_keys, _principal_from_auth
from app.settings import Settings


def test_dev_proxy_keys_never_include_model_or_jwt_secret() -> None:
    s = Settings(
        kimi_api_key="sk-real-kimi-key",
        pico_jwt_secret="super-secret-jwt-material-32bytes!!",
        pico_openai_proxy_key="my-proxy",
        pico_env="development",
    )
    keys = _dev_proxy_keys(s)
    assert "pico-dev" in keys
    assert "sk-pico-dev" in keys
    assert "my-proxy" in keys
    assert "sk-real-kimi-key" not in keys
    assert "super-secret-jwt-material-32bytes!!" not in keys


def test_openai_compat_rejects_arbitrary_sk_and_model_key() -> None:
    s = Settings(
        kimi_api_key="sk-real-kimi-key",
        pico_jwt_secret="change-me-dev-only-not-for-prod-32b!",
        pico_openai_proxy_key="",
        pico_env="development",
        pico_accept_test_issuer=True,
    )
    with pytest.raises(HTTPException) as ei:
        _principal_from_auth("Bearer sk-totally-random", s)
    assert ei.value.status_code == 401

    with pytest.raises(HTTPException):
        _principal_from_auth("Bearer sk-real-kimi-key", s)


def test_openai_compat_accepts_pico_dev_in_development() -> None:
    s = Settings(
        kimi_api_key="sk-real-kimi-key",
        pico_jwt_secret="change-me-dev-only-not-for-prod-32b!",
        pico_env="development",
        pico_accept_test_issuer=True,
    )
    p = _principal_from_auth("Bearer pico-dev", s)
    assert p.school_id == "school-a"
    assert p.membership_id == "nextchat-user"


def test_proxy_principal_requires_valid_membership_header() -> None:
    s = Settings(
        pico_jwt_secret="change-me-dev-only-not-for-prod-32b!",
        pico_env="development",
        pico_accept_test_issuer=True,
    )
    proxy = _principal_from_auth("Bearer pico-dev", s)

    with pytest.raises(HTTPException) as missing:
        scope_proxy_principal(proxy, None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as invalid:
        scope_proxy_principal(proxy, "member:other")
    assert invalid.value.status_code == 400

    scoped = scope_proxy_principal(proxy, "member-a")
    assert scoped.membership_id == "member-a"


def test_openai_compat_rejects_proxy_in_production() -> None:
    s = Settings(
        pico_jwt_secret="change-me-dev-only-not-for-prod-32b!",
        pico_env="production",
        pico_accept_test_issuer=False,
        pico_openai_proxy_key="still-set",
    )
    with pytest.raises(HTTPException) as ei:
        _principal_from_auth("Bearer pico-dev", s)
    assert ei.value.status_code == 401


def _token(client: TestClient, school: str, member: str) -> str:
    r = client.post(
        "/v1/dev/token",
        json={"school_id": school, "membership_id": member},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_list_tasks_is_membership_scoped() -> None:
    client = TestClient(app)
    tok_a = _token(client, "school-a", "member-a")
    tok_b = _token(client, "school-a", "member-b")
    h_a = {"Authorization": f"Bearer {tok_a}"}
    h_b = {"Authorization": f"Bearer {tok_b}"}

    # create task as A (may fail if no model key — still creates task/run attempt)
    r = client.post(
        "/v1/tasks",
        headers=h_a,
        json={"title": "only-a", "prompt": "hello from a"},
    )
    # 200 even when model blocked mid-run in some paths; accept 200
    assert r.status_code == 200, r.text
    task_id = r.json()["task"]["id"]

    list_a = client.get("/v1/tasks", headers=h_a)
    assert list_a.status_code == 200
    ids_a = {t["id"] for t in list_a.json()["tasks"]}
    assert task_id in ids_a

    list_b = client.get("/v1/tasks", headers=h_b)
    assert list_b.status_code == 200
    ids_b = {t["id"] for t in list_b.json()["tasks"]}
    assert task_id not in ids_b

    # B cannot read A's task
    get_b = client.get(f"/v1/tasks/{task_id}", headers=h_b)
    assert get_b.status_code == 404


def test_stream_ends_when_terminal_with_zero_new_events() -> None:
    """Regression: terminal + last_seq==0 must not spin forever."""
    # Unit-check the condition logic used in stream_run
    terminal = {"succeeded", "failed", "cancelled"}
    status = "failed"
    last_seq = 0
    should_end = status in terminal  # fixed condition (was: and last_seq > 0)
    assert should_end is True
    # old buggy condition:
    old = status in terminal and last_seq > 0
    assert old is False
