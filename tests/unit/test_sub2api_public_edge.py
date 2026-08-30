from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PICO = ROOT / "deploy" / "nginx" / "pico.aivia.asia.conf"
WB = ROOT / "deploy" / "nginx" / "workbench.aivia.asia.sub2api.conf"
APPLY = ROOT / "scripts" / "apply-sub2api-public-edge.sh"


def test_pico_door_cookie_switches_to_loopback() -> None:
    text = PICO.read_text(encoding="utf-8")
    assert "server_name pico.aivia.asia;" in text
    assert "127.0.0.1:18088" in text
    assert "127.0.0.1:8081" in text
    assert "0.0.0.0:8081" not in text
    assert "location = /accounts/enter-sub2api" in text
    assert "location = /accounts/exit-sub2api" in text
    assert "pico_sub2api_door" in text
    assert "ssl_certificate" in text


def test_workbench_sni_door_keeps_experts() -> None:
    text = WB.read_text(encoding="utf-8")
    assert "server_name workbench.aivia.asia;" in text
    assert "server 127.0.0.1:8081" in text
    assert "location ^~ /experts/" in text
    assert "proxy_pass http://sub2api_loopback" in text


def test_apply_script_reloads_nginx_without_secrets() -> None:
    text = APPLY.read_text(encoding="utf-8")
    assert "sudo -n /usr/bin/systemctl reload nginx" in text
    assert "ADMIN_PASSWORD" not in text
    assert "pico.aivia.asia.conf" in text
    assert "127.0.0.1:8081" in text
