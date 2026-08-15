"""One-teacher-one-disk: host bind, not a micro-VM.

Owner tree = school_id + membership_id (no run_id).
Destroying a sandbox session must not delete this tree.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s1 import (
    deny_secret_filename,
    join_workspace_path,
    safe_segment,
    sandbox_root,
)

DEFAULT_OWNER_DISK_QUOTA = 2 * 1024 * 1024 * 1024
QUOTA_COPY = "这台老师盘已满（上限 2GB）。关掉窗口不会删文件；请先清空不用的文件。"
PERSIST_COPY = "文件在这台老师盘上。关掉窗口或会话不会删文件。"


def disk_root() -> Path:
    raw = os.environ.get("PICO_SANDBOX_DISK", "").strip()
    if raw:
        return Path(raw)
    return sandbox_root() / "disks"


def owner_disk_quota_bytes() -> int:
    raw = (os.environ.get("PICO_SANDBOX_DISK_QUOTA_BYTES") or "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = DEFAULT_OWNER_DISK_QUOTA
        return max(1, value)
    return DEFAULT_OWNER_DISK_QUOTA


def owner_disk_dir(school_id: str, membership_id: str) -> Path:
    return (
        disk_root()
        / safe_segment(school_id, fallback="school")
        / safe_segment(membership_id, fallback="member")
    )


def owner_disk_usage_bytes(root: Path) -> int:
    if not root.is_dir():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def assert_owner_disk_quota(root: Path, *, add_bytes: int, replace_bytes: int = 0) -> None:
    quota = owner_disk_quota_bytes()
    projected = owner_disk_usage_bytes(root) - max(0, replace_bytes) + max(0, add_bytes)
    if projected > quota:
        raise ToolError("sandbox.quota", QUOTA_COPY)


def list_owner_disk_names(school_id: str, membership_id: str) -> list[str]:
    root = owner_disk_dir(school_id, membership_id)
    if not root.is_dir():
        return []
    names: list[str] = []
    for path in sorted(root.iterdir()):
        if path.is_file() and not path.name.startswith(".") and not path.is_symlink():
            names.append(path.name)
    return names


def owner_disk_file(school_id: str, membership_id: str, filename: str) -> Path:
    deny_secret_filename(filename)
    root = owner_disk_dir(school_id, membership_id)
    root.mkdir(parents=True, exist_ok=True)
    name = Path(filename or "").name
    if not name or name in {".", ".."}:
        raise ToolError("sandbox.path_denied", "文件名非法")
    return join_workspace_path(root, name)


def write_owner_disk_file(
    school_id: str,
    membership_id: str,
    filename: str,
    data: bytes,
) -> Path:
    dest = owner_disk_file(school_id, membership_id, filename)
    old = dest.stat().st_size if dest.is_file() else 0
    assert_owner_disk_quota(dest.parent, add_bytes=len(data), replace_bytes=old)
    dest.write_bytes(data)
    return dest


def read_owner_disk_file(school_id: str, membership_id: str, filename: str) -> bytes:
    dest = owner_disk_file(school_id, membership_id, filename)
    if not dest.is_file():
        raise ToolError("sandbox.file_not_found", "老师盘上没有这个文件")
    return dest.read_bytes()


def clear_owner_disk(school_id: str, membership_id: str) -> dict[str, Any]:
    root = owner_disk_dir(school_id, membership_id)
    removed = 0
    if root.is_dir():
        for path in list(root.iterdir()):
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                    removed += 1
                elif path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                    removed += 1
            except OSError:
                continue
    return {
        "ok": True,
        "cleared": True,
        "removed": removed,
        "files": list_owner_disk_names(school_id, membership_id),
    }


def owner_disk_meta(school_id: str, membership_id: str) -> dict[str, Any]:
    root = owner_disk_dir(school_id, membership_id)
    names = list_owner_disk_names(school_id, membership_id)
    used = owner_disk_usage_bytes(root)
    return {
        "ok": True,
        "persist": True,
        "files": [{"name": name} for name in names],
        "disk_bytes": used,
        "disk_quota_bytes": owner_disk_quota_bytes(),
        "human_copy": PERSIST_COPY,
    }
