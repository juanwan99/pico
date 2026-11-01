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


def _fn(text: str, name: str) -> str:
    body = text[text.index(f"{name}() {{") :]
    return body[: body.index("\n}\n") + 3]


def test_drill_picks_newest_complete_backup(tmp_path: Path) -> None:
    """pico#1376: a newer folder still uploading (no COMPLETE) must not be drilled."""
    fake = tmp_path / "rclone"
    fake.write_text(
        "#!/bin/bash\n"
        '[[ "$*" == *"--include /*/COMPLETE"* ]] || exit 3\n'
        "printf '%s\\n' 20261029T111000-0700/COMPLETE 20261101T063518-0800/COMPLETE 20261030T111008-0700/COMPLETE\n"
    )
    fake.chmod(0o755)
    text = SCRIPT.read_text(encoding="utf-8")
    script = f"set -euo pipefail\nRCLONE_BIN={fake}\nREMOTE=gdrive:x\n{_fn(text, 'latest_complete')}\nlatest_complete"
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)
    assert out.returncode == 0 and out.stdout.strip() == "20261101T063518-0800"


def test_complete_marker_goes_up_after_the_size_check() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    run = text[text.index("cmd_run()") : text.index("cmd_drill()")]
    assert run.index("--size-only") < run.index('"$REMOTE/$stamp/COMPLETE"') < run.index("write_status OK")
    drill = text[text.index("cmd_drill()") : text.index("cmd_watch()")]
    assert "latest_complete" in drill and "--dirs-only" not in drill


def test_leftovers_of_a_killed_run_are_cleaned() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    run = text[text.index("cmd_run()") : text.index("cmd_drill()")]
    assert run.index("flock -n 9") < run.index("-name '20*' -exec rm -rf") < run.index('mkdir -p "$dir"')
    drill = text[text.index("cmd_drill()") : text.index("cmd_watch()")]
    assert 'rm -rf "$WORK"/drill-*' in drill


def test_backup_timeout_leaves_room() -> None:
    unit = (SCRIPT.parents[1] / "deploy" / "systemd" / "pico-backup.service").read_text(encoding="utf-8")
    assert "TimeoutStartSec=6h" in unit
