from __future__ import annotations

import json
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


def test_fail_closed_without_ssh(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\n派发 · T-TEST\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--prompt-file", str(slip), "--issue", "1", "--no-comment"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PICO_EXECUTOR_SSH": "/bin/false"},
    )
    assert result.returncode == 2
    assert "ssh ecs failed" in result.stderr
    assert "CURSOR_API_KEY" not in result.stdout
    assert "CURSOR_API_KEY" not in result.stderr
    assert "api.cursor.com" not in result.stdout
    assert "key=" not in result.stdout.lower()


def test_print_payload_ecs_grok_not_cursor(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\n派发 · T-KB-ENGINE-ON\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--prompt-file",
        str(slip),
        "--issue",
        "682",
        "--pr",
        "683",
        "--name",
        "T-KB-ENGINE-ON",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["runtime"] == "ecs-grok"
    assert body["ssh_host"] == "ecs"
    assert body["session"]
    assert "682" in body["cwd"] or body["issue"] == "682"
    assert "CURSOR_API_KEY" not in result.stdout
    assert "api.cursor.com" not in result.stdout
    assert "autoCreatePR" not in body
    assert "repos" not in body
    assert "env" not in body
    assert "ECS Grok" in body["prompt"]
    assert "T-KB-ENGINE-ON" in body["prompt"]


def test_env_flag_ignored(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("do the card\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--prompt-file",
        str(slip),
        "--cwd",
        "/tmp",
        "--env",
        "pico-executor",
        "--pr",
        "https://github.com/juanwan99/pico/pull/683",
    )
    assert result.returncode == 0, result.stderr
    assert "ignored" in result.stderr
    body = json.loads(result.stdout)
    assert body["runtime"] == "ecs-grok"
    assert body["pr"] == "683"
    assert body["no_worktree"] is True


def test_cursor_agent_id_rejected(tmp_path: Path) -> None:
    slip = tmp_path / "wake.txt"
    slip.write_text("merge now\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--agent",
        "bc-00000000-0000-0000-0000-000000000001",
        "--prompt-file",
        str(slip),
        "--cwd",
        "/tmp",
    )
    assert result.returncode == 2
    assert "Cursor agent id retired" in result.stderr


def test_session_follow_up_payload(tmp_path: Path) -> None:
    slip = tmp_path / "wake.txt"
    slip.write_text("merge now\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--session",
        "pico-exec-682",
        "--prompt-file",
        str(slip),
        "--cwd",
        "/tmp",
        "--continue",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["session"] == "pico-exec-682"
    assert body["continue"] is True


def test_wake_merge_appends_contract(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\nbase slip\n", encoding="utf-8")
    sha = "9c22b25dc0099f1eaed6317d1e299420b37492ce"
    result = _run(
        "--print-payload",
        "--prompt-file",
        str(slip),
        "--issue",
        "682",
        "--wake-merge",
        "--pr",
        "683",
        "--sha",
        sha,
        "--no-comment",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    text = body["prompt"]
    assert "【续派 · 合部】" in text
    assert "issues/682" in text
    assert sha in text
    assert "第二张" in text
    assert "origin/main" in text
    assert "PR 头" in text
    assert body["wake_merge"] is True
    assert body["runtime"] == "ecs-grok"


def test_dry_run_skips_ssh(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\nok\n", encoding="utf-8")
    result = _run(
        "--dry-run",
        "--prompt-file",
        str(slip),
        "--issue",
        "9",
        env={"PICO_EXECUTOR_SSH": "/bin/false"},
    )
    assert result.returncode == 0, result.stderr
    assert "ok=dry-run" in result.stdout
    assert "runtime=ecs-grok" in result.stdout


def test_empty_prompt_fails() -> None:
    result = _run("--print-payload", "--prompt", "   ", "--cwd", "/tmp")
    assert result.returncode == 2
    assert "empty prompt" in result.stderr


def test_need_issue_or_cwd() -> None:
    result = _run("--print-payload", "--prompt", "hello")
    assert result.returncode == 2
    assert "need --issue or --cwd" in result.stderr


def test_remote_helper_exists_and_forbids_prod_tree() -> None:
    text = REMOTE.read_text(encoding="utf-8")
    assert "opt/pico" in text
    assert "tmux" in text
    src = SCRIPT.read_text(encoding="utf-8")
    assert "api.cursor.com" not in src
    assert "CURSOR_API_KEY" not in src
    assert "tmux kill-session" in text
    assert "still live" in text
    assert "refuse kill-session" in text
    assert "pane_dead" in text
