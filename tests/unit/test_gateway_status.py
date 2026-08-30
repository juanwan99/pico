from __future__ import annotations

from app.gateway_status import gateway_status


def test_gateway_status_is_manager_not_frontend(monkeypatch) -> None:
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0, headers=None: {"ok": True, "http": 200})
    monkeypatch.setattr("app.gateway_status._new_api_models", lambda: ["gpt-5.6-sol"])
    monkeypatch.setattr(
        "app.gateway_status._sub2api_login_state",
        lambda: {
            "monitors_http": 401,
            "accounts_http": 401,
            "monitor_count": None,
            "compliance_required": False,
            "needs_auth": True,
            "hard_relogin": "sub2api_tailnet_ui",
        },
    )
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    body = gateway_status()
    assert body["audience"] == "manager"
    assert body["pico_talks_to"] == "new_api"
    assert body["sub2api_is_frontend"] is False
    assert body["sub2api_role"] == "account_login_state"
    assert body["new_api_role"] == "pipe_channels_billing"
    assert body["dify"] == "retired"
    assert body["brain"]["via"] == "new_api"
    assert body["brain"]["model"] == "gpt-5.6-sol"
    assert body["new_api"]["models"] == ["gpt-5.6-sol"]
    assert body["sub2api"]["tailnet_ui"].startswith("https://")
    assert "token" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert body["new_api"]["intended_bind"] == "127.0.0.1:3000"
    assert body["sub2api"]["bind"] == "127.0.0.1:8081"


def test_gateway_brain_flags_aiproxy_direct(monkeypatch) -> None:
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0, headers=None: {"ok": True, "http": 200})
    monkeypatch.setattr("app.gateway_status._new_api_models", list)
    monkeypatch.setattr(
        "app.gateway_status._sub2api_login_state",
        lambda: {
            "monitors_http": 401,
            "accounts_http": 401,
            "monitor_count": None,
            "compliance_required": False,
            "needs_auth": True,
            "hard_relogin": "sub2api_tailnet_ui",
        },
    )
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://superaichao.xin/openai")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    body = gateway_status()
    assert body["brain"]["via"] == "aiproxy_direct"
    assert body["pico_talks_to"] == "aiproxy_direct"


def test_pico_nginx_snippet_is_librechat_only() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "pico.aivia.asia.conf").read_text(
        encoding="utf-8"
    )
    assert "127.0.0.1:18088" in text
    assert "pico_sub2api_door" not in text
    assert "8081" not in text
    assert "dify" not in text.lower()


def test_workbench_snippet_is_retired() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "workbench.aivia.asia.retired.conf"
    ).read_text(encoding="utf-8")
    assert "return 410" in text
    assert "8081" not in text
    assert "13080" not in text
    assert "proxy_pass" not in text
