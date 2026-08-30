from __future__ import annotations

from app.gateway_status import gateway_status


def test_gateway_status_is_manager_not_frontend(monkeypatch) -> None:
    monkeypatch.setattr("app.gateway_status._probe", lambda url, timeout=2.0: {"ok": True, "http": 200})
    body = gateway_status()
    assert body["audience"] == "manager"
    assert body["pico_talks_to"] == "new_api"
    assert body["sub2api_is_frontend"] is False
    assert body["sub2api_role"] == "new_api_upstream_account_pool"
    assert body["dify"] == "retired"
    assert "token" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert body["new_api"]["bind"] == "127.0.0.1:3000"
    assert body["sub2api"]["bind"] == "127.0.0.1:8081"


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
