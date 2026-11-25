"""Daily backup, restore drill, and local retention on upload failure."""

import os
import subprocess
from pathlib import Path

import pytest

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


def _run_backup(tmp_path: Path, fail_step: str = "") -> subprocess.CompletedProcess[str]:
    commands = {
        "curl": "exit 0\n",
        "docker": """
set -eu
if [[ "$1" == run ]]; then
  for arg; do
    case "$arg" in
      type=bind,source=*,target=/backup)
        dir="${arg#type=bind,source=}"
        printf 'snapshot\n' >"${dir%,target=/backup}/pico.db"
        ;;
    esac
  done
else
  printf 'fixture\n'
fi
""",
        "rclone": """
shift 12
if [[ "$1" == "$BACKUP_TEST_FAIL_STEP" ]]; then
  exit 1
fi
if [[ "$1" == copyto ]]; then
  test -s "$2"
fi
""",
    }
    for name, body in commands.items():
        fake = tmp_path / name
        fake.write_text("#!/bin/bash\n" + body, encoding="utf-8")
        fake.chmod(0o755)
    env_file = tmp_path / "pico.env"
    env_file.write_text("MEILI_MASTER_KEY=test\n", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PICO_BACKUP_ENV": str(env_file),
        "PICO_BACKUP_WORK": str(tmp_path / "work"),
        "PICO_BACKUP_KEEP_DIR": str(tmp_path / "keep"),
        "PICO_BACKUP_LOG_DIR": str(tmp_path / "logs"),
        "PICO_BACKUP_STATUS_JSON": str(tmp_path / "status.json"),
        "PICO_BACKUP_ALERT": str(tmp_path / "no-alert"),
        "PICO_BACKUP_REMOTE": "gdrive:fixture",
        "PICO_BACKUP_RCLONE": str(tmp_path / "rclone"),
        "PICO_BACKUP_RETRY_MAX": "1",
        "PICO_BACKUP_PART_MB": "128",
        "BACKUP_TEST_FAIL_STEP": fail_step,
    }
    return subprocess.run(
        ["bash", SCRIPT, "run"], env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(
    ("step", "reason"),
    [("copy", "upload ("), ("check", "remote size check"), ("copyto", "upload COMPLETE")],
)
def test_failed_upload_keeps_local_backup(tmp_path: Path, step: str, reason: str) -> None:
    result = _run_backup(tmp_path, step)
    assert result.returncode == 1, result.stdout
    assert f"FAIL {reason}" in result.stdout
    (kept,) = (tmp_path / "keep").iterdir()
    assert f"backup kept at {kept}" in result.stdout
    assert (kept / "mongo.archive.gz").read_text(encoding="utf-8") == "fixture\n"
    assert (kept / "SHA256SUMS").stat().st_size > 0
    assert not list((tmp_path / "work").glob("20*"))


def test_successful_upload_cleans_work_without_keeping_a_copy(tmp_path: Path) -> None:
    result = _run_backup(tmp_path)
    assert result.returncode == 0, result.stdout
    assert " OK " in result.stdout
    assert not (tmp_path / "keep").exists()
    assert not list((tmp_path / "work").glob("20*"))


def test_failed_upload_prunes_only_oldest_kept_backup(tmp_path: Path) -> None:
    keep = tmp_path / "keep"
    old_stamps = [f"2020010{day}T021000+0000" for day in range(1, 8)]
    for stamp in reversed(old_stamps):
        (keep / stamp).mkdir(parents=True)
    (keep / "2020-not-a-backup").mkdir()
    stale_work = tmp_path / "work" / old_stamps[-1]
    stale_work.mkdir(parents=True)

    result = _run_backup(tmp_path, "copy")
    assert result.returncode == 1, result.stdout
    assert not list((tmp_path / "work").glob("20*"))
    assert not (keep / old_stamps[0]).exists()
    assert (keep / "2020-not-a-backup").is_dir()
    retained = sorted(path.name for path in keep.glob("20*T*"))
    assert retained[:-1] == old_stamps[1:]
    assert (keep / retained[-1] / "SHA256SUMS").is_file()
