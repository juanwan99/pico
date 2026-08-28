from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "spawn-grok-ecs.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_empty_prompt_fails() -> None:
    result = _run("--print-cmd", "--prompt", "   ")
    assert result.returncode == 2
    assert "empty prompt" in result.stderr


def test_print_cmd_has_ecs_grok_and_no_secrets(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("## 派发\n派发 · T-TEST · 用 grok-ecs\n", encoding="utf-8")
    result = _run("--print-cmd", "--prompt-file", str(slip), "--issue", "744")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "ssh ecs" in out
    assert "/home/ops/.grok/bin/grok" in out
    assert "--cwd /opt/pico" in out
    assert "pico-grok-slip-744.txt" in out
    assert "auth.json" not in out.lower()
    assert "CURSOR_API_KEY" not in out
    assert "prompt_chars=" in out
    # slip body stays off the command line
    assert "T-TEST" not in out


def test_always_approve_is_opt_in(tmp_path: Path) -> None:
    slip = tmp_path / "slip.txt"
    slip.write_text("do the card\n", encoding="utf-8")
    off = _run("--print-cmd", "--prompt-file", str(slip))
    assert "--always-approve" not in off.stdout
    on = _run(
        "--print-cmd",
        "--prompt-file",
        str(slip),
        env={"GROK_ECS_ALWAYS_APPROVE": "1"},
    )
    assert on.returncode == 0, on.stderr
    assert "--always-approve" in on.stdout


def test_missing_prompt_file_fails(tmp_path: Path) -> None:
    result = _run("--print-cmd", "--prompt-file", str(tmp_path / "nope.txt"))
    assert result.returncode == 2
    assert "prompt file missing" in result.stderr
