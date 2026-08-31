from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pr_ci_ready_shell_fixtures() -> None:
    script = ROOT / "scripts" / "pr-ci-ready.test.sh"
    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr-ci-ready.test.sh passed" in result.stdout
