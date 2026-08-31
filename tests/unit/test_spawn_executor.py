from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "spawn-executor.sh"
REMOTE = ROOT / "scripts" / "ecs-grok-exec.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_print_payload_retired() -> None:
    result = _run("--print-payload", "--prompt", "hello", "--cwd", "/tmp")
    assert result.returncode == 1
    assert "RETIRED" in result.stderr
    assert "ok=false" in result.stdout
    assert "runtime=retired" in result.stdout
    assert "use=grok-sandbox-exec" in result.stdout
    assert "CURSOR_API_KEY" not in result.stdout
    assert "api.cursor.com" not in result.stdout


def test_dry_run_retired_skips_ssh() -> None:
    result = _run(
        "--dry-run",
        "--prompt",
        "ok",
        "--issue",
        "9",
        env={"PICO_EXECUTOR_SSH": "/bin/false"},
    )
    assert result.returncode == 1
    assert "RETIRED" in result.stderr
    assert "ssh ecs failed" not in result.stderr
    assert "ok=dry-run" not in result.stdout


def test_wake_merge_retired() -> None:
    result = _run(
        "--print-payload",
        "--prompt",
        "base slip",
        "--issue",
        "682",
        "--wake-merge",
        "--pr",
        "683",
        "--sha",
        "9c22b25dc0099f1eaed6317d1e299420b37492ce",
    )
    assert result.returncode == 1
    assert "RETIRED" in result.stderr
    assert "runtime=ecs-grok" not in result.stdout


def test_cursor_agent_id_retired() -> None:
    result = _run(
        "--agent",
        "bc-00000000-0000-0000-0000-000000000001",
        "--prompt",
        "merge now",
        "--cwd",
        "/tmp",
    )
    assert result.returncode == 1
    assert "RETIRED" in result.stderr


def test_no_ssh_even_when_wrapper_is_false() -> None:
    result = _run(
        "--prompt",
        "## 派发\n派发 · T-TEST\n",
        "--issue",
        "1",
        "--no-comment",
        env={"PICO_EXECUTOR_SSH": "/bin/false"},
    )
    assert result.returncode == 1
    assert "RETIRED" in result.stderr
    assert "ssh ecs failed" not in result.stderr


def test_ecs_grok_exec_retired() -> None:
    result = subprocess.run(
        ["bash", str(REMOTE), "--session", "pico-exec-1", "--prompt", "/tmp/missing"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "RETIRED" in result.stderr
    assert "ok=false" in result.stdout
    assert "runtime=retired" in result.stdout


def test_stub_records_old_forbid_and_has_no_cursor_api() -> None:
    text = REMOTE.read_text(encoding="utf-8")
    assert "RETIRED" in text
    assert "opt/pico" in text
    src = SCRIPT.read_text(encoding="utf-8")
    assert "RETIRED" in src
    assert "opt/pico" in src
    assert "api.cursor.com" not in src
    assert "CURSOR_API_KEY" not in src
    assert "exit 1" in src
