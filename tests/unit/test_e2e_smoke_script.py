"""scripts/e2e-smoke.sh against a fake Pico API + UI: all green → 0, one broken flow → 1."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "e2e-smoke.sh"
BASH = os.environ.get("PICO_TEST_BASH") or "bash"
SHA = "a" * 40
KEY = "pico-dev"


def _routes(sha: str) -> dict[str, tuple[int, object]]:
    return {
        "/v1/meta/tip": (200, {"ok": True, "git_sha": sha}),
        "/api/pico/tip": (200, {"ok": True, "git_sha": sha}),
        "/health": (200, {"ok": True, "service": "pico-api", "git_sha": sha, "default_runtime": "pi-true"}),
        "/login": (200, "<html>login</html>"),
        "/api/config": (200, {"appTitle": "Pico"}),
        "/v1/me": (200, {"school_id": "smoke-school", "membership_id": "smoke-e2e", "scopes": ["ai:read", "ai:run"]}),
        "/v1/models": (200, {"object": "list", "data": [{"id": "pico-fast"}, {"id": "pico-deep"}]}),
        "/v1/skills/catalog": (200, {"skills": [{"id": "skill-deliverable"}]}),
        "/v1/tools": (200, {"tools": []}),
        "/v1/tasks": (200, {"tasks": []}),
        "/v1/usage/summary": (200, {"billing": False, "schema": "pico.usage.v1", "days": []}),
        "/v1/my/folders": (200, {"folders": [], "count": 0}),
    }


class _FakePico(ThreadingHTTPServer):
    def __init__(self, routes: dict[str, tuple[int, object]], *, open_auth: bool = False):
        self.routes = routes
        self.open_auth = open_auth
        self.seen: list[tuple[str, bool]] = []
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _FakePico

    def log_message(self, *_args: object) -> None:  # quiet
        return

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        authed = bool(self.headers.get("Authorization"))
        self.server.seen.append((path, authed))
        if path.startswith("/v1/") and path != "/v1/meta/tip" and not authed and not self.server.open_auth:
            code, body = 401, {"detail": {"code": "auth.missing"}}
        else:
            code, body = self.server.routes.get(path, (404, {"detail": "not found"}))
        raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html" if isinstance(body, str) else "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def fake_pico():
    servers: list[_FakePico] = []

    def start(routes: dict[str, tuple[int, object]], *, open_auth: bool = False) -> str:
        srv = _FakePico(routes, open_auth=open_auth)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def _run(base: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, SMOKE.as_posix(), *args],
        env={
            **os.environ,
            "PICO_SMOKE_API": base,
            "PICO_SMOKE_UI": base,
            "PICO_SMOKE_KEY": KEY,
            "PICO_SMOKE_TIMEOUT": "5",
            **(env or {}),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )


def test_smoke_all_green_exits_zero(fake_pico) -> None:
    base = fake_pico(_routes(SHA))
    result = _run(base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.rstrip().splitlines()[-1] == "smoke 12/12 PASS (local)"
    assert "FAIL" not in result.stdout


def test_smoke_reports_anonymous_and_authenticated_paths(fake_pico) -> None:
    base = fake_pico(_routes(SHA))
    result = _run(base)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("tip", "health", "ui-login", "ui-config", "auth-401", "me", "models", "skills", "tools", "tasks", "usage", "my-folders"):
        assert f"ok   {name}" in result.stdout


def test_smoke_fails_when_one_key_flow_breaks(fake_pico) -> None:
    routes = _routes(SHA)
    routes["/v1/models"] = (500, {"detail": "boom"})
    base = fake_pico(routes)
    result = _run(base)
    assert result.returncode == 1
    assert "FAIL models" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("smoke 11/12 FAIL")


def test_smoke_fails_when_auth_is_not_fail_closed(fake_pico) -> None:
    # Anonymous /v1/me answering 200 means the tenant gate is open.
    base = fake_pico(_routes(SHA), open_auth=True)
    result = _run(base)
    assert result.returncode == 1
    assert "FAIL auth-401" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("smoke 11/12 FAIL")


def test_smoke_fails_on_deploy_sha_mismatch(fake_pico) -> None:
    base = fake_pico(_routes(SHA))
    result = _run(base, env={"PICO_SMOKE_EXPECT_SHA": "b" * 40})
    assert result.returncode == 1
    assert "FAIL tip" in result.stdout
    assert "expected=" in result.stdout


def test_smoke_fails_on_split_brain_between_tip_and_health(fake_pico) -> None:
    routes = _routes(SHA)
    routes["/health"] = (200, {"ok": True, "service": "pico-api", "git_sha": "c" * 40})
    base = fake_pico(routes)
    result = _run(base)
    assert result.returncode == 1
    assert "FAIL health" in result.stdout
    assert "split brain" in result.stdout


def test_smoke_no_ui_drops_librechat_checks(fake_pico) -> None:
    routes = _routes(SHA)
    del routes["/login"]
    del routes["/api/config"]
    base = fake_pico(routes)
    result = _run(base, "--no-ui")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.rstrip().splitlines()[-1] == "smoke 10/10 PASS (local)"


def test_smoke_prod_mode_requires_proxy_key(fake_pico, tmp_path: Path) -> None:
    base = fake_pico(_routes(SHA))
    result = _run(
        base,
        "--prod",
        env={"PICO_SMOKE_KEY": "", "PICO_ROOT": str(tmp_path), "PICO_SMOKE_PUBLIC": base},
    )
    assert result.returncode == 1
    assert "FAIL key" in result.stdout


def test_smoke_prod_mode_reads_key_from_env_file(fake_pico, tmp_path: Path) -> None:
    base = fake_pico(_routes(SHA))
    (tmp_path / ".env").write_text(f"OTHER=1\nPICO_OPENAI_PROXY_KEY={KEY}\n")
    result = _run(
        base,
        "--prod",
        env={"PICO_SMOKE_KEY": "", "PICO_ROOT": str(tmp_path), "PICO_SMOKE_PUBLIC": base},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.rstrip().splitlines()[-1] == "smoke 12/12 PASS (prod)"
    assert KEY not in result.stdout


def test_smoke_rejects_unknown_argument() -> None:
    result = subprocess.run(
        [BASH, SMOKE.as_posix(), "--bogus"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
