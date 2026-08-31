"""T-MEMORY-UPSTREAM · file memory per membership, no Memory OS."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.config import (
    delete_memory_file,
    list_memory_files,
    memory_extension_path,
    persist_memory_dir,
)


def test_memory_extension_is_vendored() -> None:
    path = memory_extension_path()
    assert path.is_file()
    assert (path.parent / "lib.ts").is_file()
    assert "pi-mem-1.2.0" in str(path)


def test_membership_dirs_do_not_overlap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_TRUE_PI_MEMORY_ROOT", str(tmp_path))
    a = persist_memory_dir(school_id="school-a", membership_id="member-1")
    b = persist_memory_dir(school_id="school-b", membership_id="member-1")
    assert a is not None and b is not None
    assert a != b
    (a / "MEMORY.md").write_text("简体", encoding="utf-8")
    (b / "MEMORY.md").write_text("secret-b", encoding="utf-8")
    names_a = {row["name"] for row in list_memory_files(a)}
    texts_a = {row["text"] for row in list_memory_files(a)}
    assert names_a == {"MEMORY.md"}
    assert "简体" in next(iter(texts_a))
    assert "secret-b" not in next(iter(texts_a))


def test_delete_refuses_escape(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_TRUE_PI_MEMORY_ROOT", str(tmp_path))
    root = persist_memory_dir(school_id="s", membership_id="m")
    assert root is not None
    (root / "MEMORY.md").write_text("x", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("no", encoding="utf-8")
    assert delete_memory_file(root, "../outside.md") is False
    assert outside.is_file()
    assert delete_memory_file(root, "MEMORY.md") is True
    assert not (root / "MEMORY.md").is_file()


def test_missing_principal_does_not_share_dir() -> None:
    assert persist_memory_dir(school_id="", membership_id="m") is None
    assert persist_memory_dir(school_id="s", membership_id="") is None
