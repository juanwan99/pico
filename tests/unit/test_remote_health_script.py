from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "remote-health.sh"


def _run(tmp_path: Path, *, ssh_output: str, ssh_exit: int = 0) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ssh_args = tmp_path / "ssh-args"
    fake_ssh = bin_dir / "ssh"
    fake_ssh.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >"$SSH_ARGS_FILE"\n'
        'printf "%s" "$SSH_OUTPUT"\n'
        'exit "$SSH_EXIT"\n'
    )
    fake_ssh.chmod(0o755)

    return subprocess.run(
        ["bash", str(SCRIPT), "prod-test"],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "SSH_ARGS_FILE": str(ssh_args),
            "SSH_OUTPUT": ssh_output,
            "SSH_EXIT": str(ssh_exit),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_remote_health_prints_only_validated_fields(tmp_path: Path) -> None:
    sha = "c1a97a700ae418810d88d99eeb5c697e4da130f0"
    result = _run(
        tmp_path,
        ssh_output=f'{{"ok":true,"service":"pico-api","git_sha":"{sha}"}}',
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"ok=true\ngit_sha={sha}\n"
    ssh_args = (tmp_path / "ssh-args").read_text()
    assert "-o BatchMode=yes" in ssh_args
    assert "prod-test" in ssh_args
    assert "http://127.0.0.1:18765/health" in ssh_args


def test_remote_health_fails_when_ssh_or_curl_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, ssh_output="", ssh_exit=7)

    assert result.returncode != 0
    assert "failed to read production health" in result.stderr


def test_remote_health_fails_for_invalid_health_json(tmp_path: Path) -> None:
    result = _run(tmp_path, ssh_output='{"ok":true,"git_sha":"unknown"}')

    assert result.returncode != 0
    assert "git_sha is not a full commit SHA" in result.stderr
