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
) -> Path:
    """Install fake docker/ss/curl. Login returns only the HTTP status body (curl -w)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "ss").write_text("#!/usr/bin/env bash\nexit 0\n")
    if login_network_fail:
        login_body = "  */login) exit 7 ;;\n"
    else:
        # Real prod-update uses: curl -o /dev/null -w "%{http_code}" …/login
        login_body = f"  */login) printf '%s' '{login_code}' ;;\n"
    (bin_dir / "curl").write_text(
        "#!/usr/bin/env bash\n"
        "case \"${*: -1}\" in\n"
        "  */health) printf '{\"ok\":true,\"git_sha\":\"%s\"}' \"$PICO_GIT_SHA\" ;;\n"
        f"{login_body}"
        "esac\n"
    )
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    return bin_dir


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
    assert "UI /login HTTP status not 200" in result.stderr
    assert "got=404" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_login_http_502(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, login_code="502")
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode == 7
    assert "UI /login HTTP status not 200" in result.stderr
    assert "got=502" in result.stderr
    assert "[pico] done" not in result.stdout


def test_prod_update_refuses_login_network_failure(tmp_path: Path) -> None:
    production, sha = _production_checkout(tmp_path)
    bin_dir = _fake_runtime(tmp_path, login_network_fail=True)
    result = _run_prod_update(production, sha, bin_dir)
    assert result.returncode != 0
    assert "[pico] done" not in result.stdout
