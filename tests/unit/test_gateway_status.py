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
            "hard_relogin": "sub2api_public_ui",
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
    assert body["sub2api"]["account_ui"] == "https://workbench.aivia.asia"
    assert body["sub2api"]["tailnet_ui"] == body["sub2api"]["account_ui"]
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
            "hard_relogin": "sub2api_public_ui",
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


def test_workbench_snippet_proxies_sub2api_loopback() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "workbench.aivia.asia.conf"
    ).read_text(encoding="utf-8")
    assert "127.0.0.1:8081" in text
    assert "server_name workbench.aivia.asia" in text
    assert "127.0.0.1:13080" not in text
    assert "dify_workbench" not in text
    pico = (Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "pico.aivia.asia.conf").read_text(
        encoding="utf-8"
    )
    assert "8081" not in pico


def _clear_token_cache() -> None:
    from app import gateway_status as gs

    gs._token_cache["token"] = None
    gs._token_cache["exp"] = 0.0


def test_login_reads_monitors_and_strips_secrets(monkeypatch) -> None:
    from app.gateway_status import gateway_status

    _clear_token_cache()
    monkeypatch.delenv("SUB2API_ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("SUB2API_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("SUB2API_ADMIN_PASSWORD", "super-secret-password")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0, headers=None: {"ok": True, "http": 200})
    monkeypatch.setattr("app.gateway_status._new_api_models", list)
    timeline = [{"status": "operational", "checked_at": "t", "secret": "leak", "latency_ms": 12}] * 200

    def fake_probe_json(url, timeout=2.0, headers=None, method="GET", payload=None):
        if url.endswith("/auth/login"):
            assert method == "POST"
            assert payload == {"email": "owner@example.com", "password": "super-secret-password"}
            return 200, {"code": 0, "data": {"access_token": "tok_abc", "expires_in": 3600}}
        assert headers == {"Authorization": "Bearer tok_abc"}
        if url.endswith("/channel-monitors"):
            return 200, {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "id": 1,
                            "name": "Gemini A",
                            "provider": "google",
                            "primary_status": "operational",
                            "availability_7d": 0.992,
                            "timeline": timeline,
                            "access_token": "should-not-leak",
                        }
                    ]
                },
            }
        if url.endswith("/admin/accounts"):
            return 200, {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "id": 9,
                            "name": "订阅号甲",
                            "platform": "google",
                            "status": "ok",
                            "password": "nope",
                            "access_token": "nope",
                        }
                    ]
                },
            }
        return 200, {}

    monkeypatch.setattr("app.gateway_status._probe_json", fake_probe_json)
    body = gateway_status()
    dumped = str(body).lower()
    assert "tok_abc" not in dumped
    assert "super-secret-password" not in dumped
    assert "access_token" not in dumped
    assert "password" not in dumped
    assert "should-not-leak" not in dumped
    monitors = body["sub2api"]["monitors"]
    assert len(monitors) == 1
    assert monitors[0]["name"] == "Gemini A"
    assert monitors[0]["bucket"] == "健康"
    assert monitors[0]["availability_7d"] == 0.992
    assert len(monitors[0]["timeline"]) == 168
    assert "secret" not in monitors[0]["timeline"][0]
    assert "latency_ms" not in monitors[0]["timeline"][0]
    accounts = body["sub2api"]["accounts"]
    assert accounts[0]["id"] == 9
    assert accounts[0]["error"] is None
    assert body["sub2api"]["compliance_required"] is False
    assert body["sub2api"]["needs_auth"] is False


def test_admin_api_key_uses_x_api_key_not_password_login(monkeypatch) -> None:
    from app.gateway_status import gateway_status

    _clear_token_cache()
    monkeypatch.setenv("SUB2API_ADMIN_API_KEY", "admin-deadbeef")
    monkeypatch.setenv("SUB2API_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("SUB2API_ADMIN_PASSWORD", "super-secret-password")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0, headers=None: {"ok": True, "http": 200})
    monkeypatch.setattr("app.gateway_status._new_api_models", list)
    login_calls = {"n": 0}

    def fake_probe_json(url, timeout=2.0, headers=None, method="GET", payload=None):
        if url.endswith("/auth/login"):
            login_calls["n"] += 1
            raise AssertionError("password login must not run when admin API key is set")
        assert headers == {"X-API-Key": "admin-deadbeef"}
        if url.endswith("/channel-monitors"):
            return 200, {"code": 0, "data": {"items": []}}
        if url.endswith("/admin/accounts"):
            return 200, {"code": 0, "data": {"items": []}}
        return 200, {}

    monkeypatch.setattr("app.gateway_status._probe_json", fake_probe_json)
    body = gateway_status()
    assert login_calls["n"] == 0
    assert body["sub2api"]["needs_auth"] is False
    assert body["sub2api"]["accounts"] == []
    dumped = str(body).lower()
    assert "admin-deadbeef" not in dumped
    assert "super-secret-password" not in dumped


def test_password_login_requires_2fa_marks_needs_auth(monkeypatch) -> None:
    from app.gateway_status import gateway_status

    _clear_token_cache()
    monkeypatch.delenv("SUB2API_ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("SUB2API_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("SUB2API_ADMIN_PASSWORD", "super-secret-password")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0, headers=None: {"ok": True, "http": 200})
    monkeypatch.setattr("app.gateway_status._new_api_models", list)

    def fake_probe_json(url, timeout=2.0, headers=None, method="GET", payload=None):
        if url.endswith("/auth/login"):
            return 200, {"code": 0, "data": {"requires_2fa": True, "temp_token": "tmp"}}
        return 401, {"code": 401, "message": "Authorization required"}

    monkeypatch.setattr("app.gateway_status._probe_json", fake_probe_json)
    body = gateway_status()
    assert body["sub2api"]["needs_auth"] is True
    assert "tmp" not in str(body)


def test_admin_accounts_423_is_compliance_not_fake_success(monkeypatch) -> None:
    from app.gateway_status import account_soft_action, gateway_status

    _clear_token_cache()
    monkeypatch.delenv("SUB2API_ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("SUB2API_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("SUB2API_ADMIN_PASSWORD", "super-secret-password")
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0, headers=None: {"ok": True, "http": 200})
    monkeypatch.setattr("app.gateway_status._new_api_models", list)

    def fake_probe_json(url, timeout=2.0, headers=None, method="GET", payload=None):
        if url.endswith("/auth/login"):
            return 200, {"code": 0, "data": {"access_token": "tok_abc", "expires_in": 3600}}
        if url.endswith("/channel-monitors"):
            return 200, {"code": 0, "data": {"items": []}}
        if url.endswith("/admin/accounts"):
            return 423, {"code": "ADMIN_COMPLIANCE_ACK_REQUIRED", "message": "ack"}
        if url.endswith("/admin/accounts/9/refresh"):
            return 423, {"code": "ADMIN_COMPLIANCE_ACK_REQUIRED"}
        return 0, None

    monkeypatch.setattr("app.gateway_status._probe_json", fake_probe_json)
    body = gateway_status()
    assert body["sub2api"]["accounts_http"] == 423
    assert body["sub2api"]["compliance_required"] is True
    assert body["sub2api"]["accounts"] == []
    assert body["sub2api"]["monitors"] == []
    dumped = str(body).lower()
    assert "tok_abc" not in dumped
    assert "super-secret-password" not in dumped
    result = account_soft_action(9, "refresh")
    assert result["ok"] is False
    assert result["http"] == 423
    assert "不代签" in result["message"]
    assert "账号台" in result["message"]


def test_soft_action_rejects_unknown_verb() -> None:
    from app.gateway_status import account_soft_action

    result = account_soft_action(1, "apply-oauth-credentials")
    assert result["ok"] is False
    assert result["http"] == 400
    assert "没有这个动作" in result["message"]
