"""Reject overlong chat prompts without silent truncation (stage #260 A1)."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app
from app.settings import Settings, get_settings


def test_chat_rejects_overlong_prompt() -> None:
    settings = Settings(
        _env_file=None,
        pico_env="test",
        pico_openai_proxy_key="pico-dev",
        pico_allowed_models="kimi-k2.6,pico-agent",
        pico_chat_max_prompt_chars=100,
        pico_accept_test_issuer=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        long_text = "测" * 200
        r = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer pico-dev"},
            json={
                "model": "kimi-k2.6",
                "messages": [{"role": "user", "content": long_text}],
                "stream": False,
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "输入过长" in detail
    assert "不会静默截断" in detail
