from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prod-update.sh"
IMPL = ROOT / "scripts" / "prod-update.impl.sh"


# Windows: the `bash` on PATH is usually the WSL launcher, which cannot see C:/.
# Point PICO_TEST_BASH at Git Bash (C:\Program Files\Git\bin\bash.exe). CI is Linux.
BASH = os.environ.get("PICO_TEST_BASH") or "bash"


def _bash_path(path: Path) -> str:
    # Git bash on Windows treats backslashes as escapes; POSIX path works on both.
    return path.as_posix()


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
    shutil.copy2(IMPL, source / "scripts" / "prod-update.impl.sh")
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
    office_down: bool = False,
    leftover_volumes: tuple[str, ...] = (),
    volume_rm_fails: bool = False,
    inflight_health_polls: int = 0,
) -> Path:
    """Install fake docker/ss/curl. Login returns only the HTTP status body (curl -w).

    Fake docker branches on the subcommand so the impl's own gates are exercised:
    the pico-office unix-socket probe (``compose exec -T pico-api python3``),
    ``volume ls --filter label=…pico_office_sock`` and ``volume rm``.

    ``inflight_health_polls``: the first N ``/health`` calls report
    ``inflight_runs=2`` (teacher runs still owned by the old process); later
    calls report 0. The fake ``sleep`` is a no-op, so the impl's wait loop
    spins through its budget instantly.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if office_down:
        (bin_dir / "office-down").write_text("1\n")
    if inflight_health_polls:
        (bin_dir / "inflight-polls").write_text(f"{inflight_health_polls}\n")
    if leftover_volumes:
        (bin_dir / "volumes").write_text("".join(f"{v}\n" for v in leftover_volumes))
    if volume_rm_fails:
        (bin_dir / "volume-rm-fail").write_text("1\n")
    (bin_dir / "docker").write_text(
        "#!/usr/bin/env bash\n"
        'here="$(cd "$(dirname "$0")" && pwd)"\n'
        'args="$*"\n'
        'case "$args" in\n'
        '  *" exec -T pico-api "*)\n'
        '    if [ -f "$here/office-down" ]; then exit 1; fi\n'
        "    exit 0 ;;\n"
        '  "volume ls "*)\n'
        '    if [ -f "$here/volumes" ]; then cat "$here/volumes"; fi\n'
        "    exit 0 ;;\n"
        '  "volume rm "*)\n'
        '    if [ -f "$here/volume-rm-fail" ]; then exit 1; fi\n'
        '    printf \'%s\\n\' "${@: -1}"\n'
        '    : >"$here/volume-removed"\n'
        "    exit 0 ;;\n"
        "esac\n"
        "exit 0\n"
    )
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
        "  */health)\n"
        "    here=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "    inflight_field=\"\"\n"
        "    if [ -f \"$here/inflight-polls\" ]; then\n"
        "      read -r left <\"$here/inflight-polls\"\n"
        "      if [ \"$left\" -gt 0 ]; then\n"
        "        inflight_field='\"inflight_runs\":2,'\n"
        "        printf '%s' \"$((left - 1))\" >\"$here/inflight-polls\"\n"
        "      else\n"
        "        inflight_field='\"inflight_runs\":0,'\n"
        "      fi\n"
        "    fi\n"
        "    printf '{\"ok\":true,\"git_sha\":\"%s\",%s"
        "\"true_pi_binary_available\":true,"
        "\"true_pi_package_pin\":\"@earendil-works/pi-coding-agent@0.84.4\"}' "
        "\"$PICO_GIT_SHA\" \"$inflight_field\" ;;\n"
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
        [BASH, _bash_path(production / "scripts" / "prod-update.sh")],
        env={
            **os.environ,
            "PATH": f"{_bash_path(bin_dir)}{os.pathsep}{os.environ['PATH']}",
            "PICO_ROOT": _bash_path(production),
            "PICO_DEPLOY_SHA": sha,
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_prod_update_requires_full_sha(tmp_path: Path) -> None:
    result = subprocess.run(
        [BASH, _bash_path(SCRIPT)],
        env={**os.environ, "PICO_DEPLOY_SHA": "abc"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
        [BASH, _bash_path(production / "scripts" / "prod-update.sh")],
        env={
            **os.environ,
            "PICO_ROOT": _bash_path(production),
            "PICO_DEPLOY_SHA": sha,
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
        [BASH, _bash_path(production / "scripts" / "prod-update.sh")],
        env={
            **os.environ,
            "PATH": f"{_bash_path(bin_dir)}{os.pathsep}{os.environ['PATH']}",
            "PICO_ROOT": _bash_path(production),
            "PICO_DEPLOY_SHA": sha,
            "LIBRECHAT_URL": "http://127.0.0.1:19999",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "UI readiness: waiting for http://127.0.0.1:19999/login HTTP 200" in result.stdout


def test_prod_update_generates_hook_token_when_missing() -> None:
    text = IMPL.read_text(encoding="utf-8")
    assert "PICO_HOOK_SERVICE_TOKEN generated" in text
    assert "PICO_HOOK_SERVICE_TOKEN=SET" in text
    assert "Do not print the value" in text


def test_prod_update_refuses_when_pico_office_socket_is_dead(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    result = _run_prod_update(production, sha, _fake_runtime(tmp_path, office_down=True))
    assert result.returncode == 11
    assert "pico-office unix socket not answering" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_removes_leftover_office_named_volume(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, leftover_volumes=("pico_pico_office_sock",))
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "removing leftover named volume pico_pico_office_sock" in result.stdout
    assert (bin_dir / "volume-removed").exists()
    assert "[pico] done" in result.stdout


def test_prod_update_refuses_when_leftover_volume_cannot_be_removed(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(
        tmp_path, leftover_volumes=("pico_pico_office_sock",), volume_rm_fails=True
    )
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 12
    assert "still in use" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_compose_that_declares_office_named_volume(tmp_path: Path) -> None:
    production, _sha = _production_checkout(tmp_path)
    updater = tmp_path / "updater"
    origin = _run("git", "remote", "get-url", "origin", cwd=production).stdout.strip()
    _run("git", "clone", "--branch", "main", origin, str(updater), cwd=tmp_path)
    _run("git", "config", "user.email", "ci@pico.local", cwd=updater)
    _run("git", "config", "user.name", "Pico CI", cwd=updater)
    (updater / "docker-compose.host.yml").write_text(
        "services: {}\nvolumes:\n  pico_office_sock:\n"
    )
    _run("git", "add", "docker-compose.host.yml", cwd=updater)
    _run("git", "commit", "-m", "named volume back", cwd=updater)
    _run("git", "push", "origin", "main", cwd=updater)
    new_sha = _run("git", "rev-parse", "HEAD", cwd=updater).stdout.strip()
    result = _run_prod_update(production, new_sha, _fake_runtime(tmp_path))
    assert result.returncode == 12
    assert "still declares named volume pico_office_sock" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_generates_sandbox_token_when_missing(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    (production / ".env").write_text("PICO_SANDBOX_TOKEN=\nKIMI_API_KEY=k\n")
    # .env is untracked in the fixture; ignore it so the dirty-tree gate stays honest.
    (production / ".git" / "info" / "exclude").write_text(".env\n")
    result = _run_prod_update(production, sha, _fake_runtime(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "PICO_SANDBOX_TOKEN generated" in result.stdout
    env = (production / ".env").read_text()
    lines = [ln for ln in env.splitlines() if ln.startswith("PICO_SANDBOX_TOKEN=")]
    assert len(lines) == 1
    assert len(lines[0].split("=", 1)[1]) >= 32
    assert lines[0].split("=", 1)[1] not in result.stdout


def test_prod_update_waits_for_inflight_runs_then_recreates(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, inflight_health_polls=3)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "inflight_runs=2 — waiting up to 300s before recreate" in result.stdout
    assert "inflight_runs=0 after" in result.stdout
    assert "WARN recreating with inflight_runs" not in result.stderr
    assert "[pico] done" in result.stdout


def test_prod_update_warns_and_recreates_when_inflight_runs_outlast_budget(
    tmp_path: Path,
) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, inflight_health_polls=10_000)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "waiting up to 300s before recreate" in result.stdout
    assert "WARN recreating with inflight_runs=2 after 300s" in result.stderr
    assert "[pico] done" in result.stdout


def test_prod_update_treats_missing_inflight_field_as_zero(tmp_path: Path) -> None:
    """Old image without the field, or API down: nothing to wait for."""
    production, sha = _production_checkout(tmp_path)
    result = _run_prod_update(production, sha, _fake_runtime(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "waiting up to" not in result.stdout
    assert "[pico] done" in result.stdout


def test_prod_update_bootstrap_only_checkouts_then_execs_impl() -> None:
    bootstrap = SCRIPT.read_text(encoding="utf-8")
    impl = IMPL.read_text(encoding="utf-8")
    assert "exec bash" in bootstrap
    assert "prod-update.impl.sh" in bootstrap
    assert "git checkout --detach" in bootstrap
    assert "docker compose" not in bootstrap
    assert "docker compose" in impl
    assert "prepare_office_sock_bind" in impl
    assert 'chmod 1777 "$dir"' in impl
    assert "chown 65532:65532 \"$OFFICE_SOCK\"" not in impl
    assert "pico_office_sock" in impl
    assert "exit 11" in impl
    assert "exit 12" in impl
    assert "PICO_SANDBOX_TOKEN generated" in impl


def test_prod_update_runs_impl_from_checked_out_sha(tmp_path: Path) -> None:
    production, _old_sha = _production_checkout(tmp_path)
    updater = tmp_path / "updater"
    origin = _run("git", "remote", "get-url", "origin", cwd=production).stdout.strip()
    _run("git", "clone", "--branch", "main", origin, str(updater), cwd=tmp_path)
    _run("git", "config", "user.email", "ci@pico.local", cwd=updater)
    _run("git", "config", "user.name", "Pico CI", cwd=updater)
    impl = updater / "scripts" / "prod-update.impl.sh"
    text = impl.read_text(encoding="utf-8")
    text = text.replace(
        "set -euo pipefail\n",
        'set -euo pipefail\necho "[pico] impl-from-advanced-main"\n',
        1,
    )
    impl.write_text(text, encoding="utf-8")
    _run("git", "add", "scripts/prod-update.impl.sh", cwd=updater)
    _run("git", "commit", "-m", "advance impl", cwd=updater)
    _run("git", "push", "origin", "main", cwd=updater)
    new_sha = _run("git", "rev-parse", "HEAD", cwd=updater).stdout.strip()
    result = _run_prod_update(production, new_sha, _fake_runtime(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "[pico] exec impl from" in result.stdout
    assert "[pico] impl-from-advanced-main" in result.stdout
    assert f"health.git_sha exact match: {new_sha}" in result.stdout
