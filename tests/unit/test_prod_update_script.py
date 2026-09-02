from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prod-update.sh"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _production_checkout(tmp_path: Path) -> tuple[Path, str]:
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    production = tmp_path / "production"
    _run("git", "init", "--bare", str(origin), cwd=tmp_path)
    _run("git", "init", "-b", "main", str(source), cwd=tmp_path)
    _run("git", "config", "user.email", "ci@pico.local", cwd=source)
    _run("git", "config", "user.name", "Pico CI", cwd=source)
    (source / "scripts").mkdir()
    shutil.copy2(SCRIPT, source / "scripts" / "prod-update.sh")
    (source / "docker-compose.host.yml").write_text("services: {}\n")
    _run("git", "add", ".", cwd=source)
    _run("git", "commit", "-m", "fixture", cwd=source)
    _run("git", "remote", "add", "origin", str(origin), cwd=source)
    _run("git", "push", "-u", "origin", "main", cwd=source)
    _run("git", "clone", "--branch", "main", str(origin), str(production), cwd=tmp_path)
    sha = _run("git", "rev-parse", "HEAD", cwd=production).stdout.strip()
    return production, sha


def _fake_runtime(
    tmp_path: Path,
    *,
    login_code: str = "200",
    login_network_fail: bool = False,
    login_failures_before_success: int = 0,
    reindex_http: str = "200",
    reindex_body: str = '{"ok":true,"indexed":1,"skipped":0,"total":1}',
) -> Path:
    """Install fake docker/ss/curl. Login returns only the HTTP status body (curl -w)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "ss").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "sleep").write_text("#!/usr/bin/env bash\nexit 0\n")
    if login_network_fail:
        login_body = "  */login) exit 7 ;;\n"
    elif login_failures_before_success:
        login_body = (
            "  */login)\n"
            "    state=\"$(dirname \"$0\")/login-attempts\"\n"
            "    attempts=0\n"
            "    if [ -f \"$state\" ]; then read -r attempts <\"$state\"; fi\n"
            "    attempts=$((attempts + 1))\n"
            "    printf '%s' \"$attempts\" >\"$state\"\n"
            f"    if [ \"$attempts\" -le {login_failures_before_success} ]; then "
            "printf '000'; exit 7; fi\n"
            f"    printf '%s' '{login_code}'\n"
            "    ;;\n"
        )
    else:
        # Real prod-update uses: curl -o /dev/null -w "%{http_code}" …/login
        login_body = f"  */login) printf '%s' '{login_code}' ;;\n"
    # Keep reindex JSON free of single quotes so the fake curl stays simple.
    assert "'" not in reindex_body
    (bin_dir / "curl").write_text(
        "#!/usr/bin/env bash\n"
        "out_file=\"\"\n"
        "args=(\"$@\")\n"
        "i=0\n"
        "while [ \"$i\" -lt \"${#args[@]}\" ]; do\n"
        "  if [ \"${args[$i]}\" = \"-o\" ]; then\n"
        "    i=$((i + 1))\n"
        "    out_file=\"${args[$i]}\"\n"
        "  fi\n"
        "  i=$((i + 1))\n"
        "done\n"
        "case \"${*: -1}\" in\n"
        "  */health) printf '{\"ok\":true,\"git_sha\":\"%s\","
        "\"true_pi_binary_available\":true,"
        "\"true_pi_package_pin\":\"@earendil-works/pi-coding-agent@0.84.4\"}' "
        "\"$PICO_GIT_SHA\" ;;\n"
        "  */kb/reindex-all)\n"
        "    if [ -n \"$out_file\" ]; then printf '%s' '"
        + reindex_body
        + "' >\"$out_file\"; fi\n"
        "    printf '%s' '"
        + reindex_http
        + "'\n"
        "    ;;\n"
        + login_body
        + "esac\n"
    )
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    return bin_dir


def _advance_origin_main(tmp_path: Path, production: Path) -> str:
    updater = tmp_path / "updater"
    origin = _run("git", "remote", "get-url", "origin", cwd=production).stdout.strip()
    _run("git", "clone", "--branch", "main", origin, str(updater), cwd=tmp_path)
    _run("git", "config", "user.email", "ci@pico.local", cwd=updater)
    _run("git", "config", "user.name", "Pico CI", cwd=updater)
    (updater / "tip.txt").write_text("new main tip\n")
    _run("git", "add", "tip.txt", cwd=updater)
    _run("git", "commit", "-m", "advance main", cwd=updater)
    _run("git", "push", "origin", "main", cwd=updater)
    return _run("git", "rev-parse", "HEAD", cwd=updater).stdout.strip()


def _run_prod_update(production: Path, sha: str, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(production / "scripts" / "prod-update.sh")],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "PICO_ROOT": str(production),
            "PICO_DEPLOY_SHA": sha,
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_prod_update_requires_full_sha(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={**os.environ, "PICO_DEPLOY_SHA": "abc"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "full 40-character commit SHA" in result.stderr


def test_prod_update_deploys_exact_clean_main_sha(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 0, result.stderr
    assert f"health.git_sha exact match: {sha}" in result.stdout
    assert "ui_login=200" in result.stdout
    assert "[pico] done" in result.stdout


def test_prod_update_refuses_stale_origin_main_after_fetch(tmp_path: Path) -> None:
    production, _ = _production_checkout(tmp_path)
    new_sha = _advance_origin_main(tmp_path, production)
    _run(
        "git",
        "config",
        "--replace-all",
        "remote.origin.fetch",
        "+refs/heads/preview:refs/remotes/origin/preview",
        cwd=production,
    )
    result = _run_prod_update(production, new_sha, _fake_runtime(tmp_path))
    assert result.returncode == 3
    assert "origin/main did not advance to the fetched main tip" in result.stderr
    assert f"FETCH_HEAD={new_sha}" in result.stderr
    assert "+refs/heads/preview:refs/remotes/origin/preview" in result.stderr
    assert "git config --replace-all remote.origin.fetch" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_preview_refspec_even_when_tip_matches(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    _run(
        "git",
        "config",
        "--replace-all",
        "remote.origin.fetch",
        "+refs/heads/preview:refs/remotes/origin/preview",
        cwd=production,
    )
    result = _run_prod_update(production, sha, _fake_runtime(tmp_path))
    assert result.returncode == 3
    assert "remote.origin.fetch does not track main as origin/main" in result.stderr
    assert "git config --replace-all remote.origin.fetch" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_allows_older_main_sha_as_rollback(tmp_path: Path) -> None:
    production, old_sha = _production_checkout(tmp_path)
    new_sha = _advance_origin_main(tmp_path, production)
    result = _run_prod_update(production, old_sha, _fake_runtime(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "deploying older main SHA (rollback)" in result.stderr
    assert f"requested={old_sha} origin/main={new_sha}" in result.stderr
    assert "[pico] done" in result.stdout


def test_prod_update_refuses_sha_not_on_main(tmp_path: Path) -> None:
    production, _ = _production_checkout(tmp_path)
    updater = tmp_path / "side"
    origin = _run("git", "remote", "get-url", "origin", cwd=production).stdout.strip()
    _run("git", "clone", "--branch", "main", origin, str(updater), cwd=tmp_path)
    _run("git", "config", "user.email", "ci@pico.local", cwd=updater)
    _run("git", "config", "user.name", "Pico CI", cwd=updater)
    _run("git", "checkout", "-b", "feat/side", cwd=updater)
    (updater / "side.txt").write_text("not on main\n")
    _run("git", "add", "side.txt", cwd=updater)
    _run("git", "commit", "-m", "side", cwd=updater)
    side_sha = _run("git", "rev-parse", "HEAD", cwd=updater).stdout.strip()
    _run("git", "push", "origin", "feat/side", cwd=updater)
    _run("git", "fetch", "origin", "feat/side", cwd=production)
    result = _run_prod_update(production, side_sha, _fake_runtime(tmp_path))
    assert result.returncode == 3
    assert "requested SHA is not on origin/main" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_retries_transient_login_network_failure(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, login_failures_before_success=2)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "UI not ready attempt=1/30 status=000" in result.stderr
    assert "UI ready attempt=3/30" in result.stdout
    assert "ui_login=200" in result.stdout


def test_prod_update_refuses_dirty_worktree(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    (production / "local-note.txt").write_text("do not hide me\n")
    result = subprocess.run(
        ["bash", str(production / "scripts" / "prod-update.sh")],
        env={
            **os.environ,
            "PICO_ROOT": str(production),
            "PICO_DEPLOY_SHA": sha,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "worktree has local changes" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_login_http_404(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, login_code="404")
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 7
    assert "UI /login did not become ready after 30 attempts" in result.stderr
    assert "last_status=404" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_login_http_502(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, login_code="502")
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 7
    assert "UI /login did not become ready after 30 attempts" in result.stderr
    assert "last_status=502" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_login_network_failure(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, login_network_fail=True)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 7
    assert "UI /login did not become ready after 30 attempts" in result.stderr
    assert "last_status=000" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_kb_reindex_failure(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(
        tmp_path,
        reindex_http="403",
        reindex_body='{"detail":{"code":"forbidden","message":"loopback only"}}',
    )
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 10
    assert "kb reindex-all failed" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_ui_readiness_uses_librechat_url_default(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "UI readiness: waiting for http://127.0.0.1:18088/login HTTP 200" in result.stdout
    assert "8080/login" not in result.stdout
    assert "kb reindex ok" in result.stdout


def test_prod_update_ui_readiness_honors_librechat_url_override(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path)
    result = subprocess.run(
        ["bash", str(production / "scripts" / "prod-update.sh")],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "PICO_ROOT": str(production),
            "PICO_DEPLOY_SHA": sha,
            "LIBRECHAT_URL": "http://127.0.0.1:19999",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "UI readiness: waiting for http://127.0.0.1:19999/login HTTP 200" in result.stdout


def test_prod_update_generates_hook_token_when_missing() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "PICO_HOOK_SERVICE_TOKEN generated" in text
    assert "PICO_HOOK_SERVICE_TOKEN=SET" in text
    assert "Do not print the value" in text
