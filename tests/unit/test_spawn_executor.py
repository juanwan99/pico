from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "spawn-executor.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_fail_closed_without_api_key(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\n派发 · T-TEST\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "CURSOR_API_KEY"}
    result = subprocess.run(
        ["bash", str(SCRIPT), "--prompt-file", str(slip)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 2
    assert "CURSOR_API_KEY unset" in result.stderr
    assert "key=" not in result.stdout.lower()


def test_print_payload_named_env_excludes_repos(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\n派发 · T-KB-ENGINE-ON\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--prompt-file",
        str(slip),
        "--env",
        "pico-executor",
        "--pr",
        "683",
        "--name",
        "T-KB-ENGINE-ON",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["env"] == {"type": "cloud", "name": "pico-executor"}
    assert "repos" not in body
    assert "683" in body["prompt"]["text"]
    assert body["autoCreatePR"] is False
    assert "CURSOR_API_KEY" not in result.stdout


def test_print_payload_repos_when_no_env(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("do the card\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--prompt-file",
        str(slip),
        "--pr",
        "https://github.com/juanwan99/pico/pull/683",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert "env" not in body
    assert body["repos"][0]["prUrl"] == "https://github.com/juanwan99/pico/pull/683"
    assert body["workOnCurrentBranch"] is True


def test_follow_up_payload_is_prompt_only(tmp_path: Path) -> None:
    slip = tmp_path / "wake.txt"
    slip.write_text("merge now\n", encoding="utf-8")
    result = _run(
        "--print-payload",
        "--agent",
        "bc-00000000-0000-0000-0000-000000000001",
        "--prompt-file",
        str(slip),
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {"prompt": {"text": "merge now"}}


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
    text = body["prompt"]["text"]
    assert "【续派 · 合部】" in text
    assert "issues/682" in text
    assert sha in text
    assert "第二张" in text


def test_empty_prompt_fails() -> None:
    result = _run("--print-payload", "--prompt", "   ")
    assert result.returncode == 2
    assert "empty prompt" in result.stderr
