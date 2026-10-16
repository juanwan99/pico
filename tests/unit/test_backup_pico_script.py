"""pico#1313: a live tree makes GNU tar exit 1 (file changed while read); that is not a failed backup."""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup-pico.sh"


def _live_tar(rc: int) -> subprocess.CompletedProcess[str]:
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("log() {")
    log_fn = text[start : text.index("\n", start)]
    body = text[text.index("live_tar() {") :]
    body = body[: body.index("\n}\n") + 3]
    script = f"set -euo pipefail\n{log_fn}\n{body}\nlive_tar sh -c 'echo data; exit {rc}' >/dev/null || exit 9\necho passed"
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


def test_tar_ok_passes() -> None:
    out = _live_tar(0)
    assert out.returncode == 0 and out.stdout.strip() == "passed"
    assert "changed while read" not in out.stderr


def test_tar_file_changed_is_logged_not_failed() -> None:
    out = _live_tar(1)
    assert out.returncode == 0 and out.stdout.strip() == "passed"
    assert "changed while read" in out.stderr


def test_broken_tar_still_fails() -> None:
    out = _live_tar(2)
    assert out.returncode == 9


def test_every_backup_tar_goes_through_live_tar() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    run = text[text.index("cmd_run()") : text.index("cmd_drill()")]
    lines = [ln for ln in run.splitlines() if " tar -C " in ln]
    assert len(lines) == 3
    assert all(ln.strip().startswith("live_tar ") for ln in lines)
