"""scripts/catch_guard.py：只查新改的行，两种吞错都红，swallow-ok 和 apps/ 不红（edu-core#5197）。"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "catch_guard", Path(__file__).resolve().parents[2] / "scripts" / "catch_guard.py"
)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

OLD = """\
def old():
    try:
        return 1
    except Exception:
        pass
"""

NEW = OLD + """\

def a():
    try:
        return 1
    except ValueError:
        pass


def b():
    try:
        return 1
    except Exception:
        return None


def c(items):
    for i in items:
        try:
            i()
        except KeyError:
            continue


def d():
    try:
        return 1
    except Exception:
        return {"ok": False, "items": []}


def logged(log):
    try:
        return 1
    except Exception as e:
        log.warning("x %s", e)
        return None


def reraise():
    try:
        return 1
    except Exception:
        raise


def exempt():
    try:
        return 1
    except ImportError:  # swallow-ok: 可选依赖，没装就不用
        return None
"""


def _repo(tmp_path: Path) -> Path:
    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    (tmp_path / "services").mkdir()
    (tmp_path / "apps" / "librechat").mkdir(parents=True)
    (tmp_path / "services" / "m.py").write_text(OLD)
    (tmp_path / "apps" / "librechat" / "x.py").write_text("")
    run("add", "-A")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    (tmp_path / "services" / "m.py").write_text(NEW)
    (tmp_path / "apps" / "librechat" / "x.py").write_text(NEW)
    return tmp_path


def test_only_new_lines_red(tmp_path):
    root = _repo(tmp_path)
    bad = cg.check(root, "HEAD", None)
    lines = NEW.splitlines()
    want = sorted(
        i + 1
        for i, s in enumerate(lines)
        if s.strip().startswith("except") and i >= len(OLD.splitlines())
        and "swallow-ok" not in s and "as e" not in s
        and lines[i + 1].strip() != "raise"
    )
    got = sorted(int(b.split(":")[1].split()[0]) for b in bad)
    assert got == want, bad
    assert all(b.startswith("services/m.py:") for b in bad)  # apps/ 不查、旧行 old() 不红
    assert any("空 except" in b for b in bad) and any("不记原因就走" in b for b in bad)


def test_committed_head(tmp_path):
    root = _repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "new"],
        cwd=root, check=True,
    )
    assert len(cg.check(root, "HEAD^1", "HEAD")) == 4
    assert cg.check(root, "HEAD", "HEAD") == []
