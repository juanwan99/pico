"""One-teacher-one-disk: host bind, not a micro-VM.

Owner tree = school_id + membership_id (no run_id).
Destroying a sandbox session must not delete this tree.
"""

from __future__ import annotations

import errno
import logging
import os
import shutil
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NoReturn

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
OFFICE_DISK_KINDS = frozenset({"pptx", "docx", "xlsx"})
# The sandbox container user (services/sandbox_worker/Dockerfile). pico-api runs as
# root on the same bind mount, so whatever it creates is handed over (#1267).
SANDBOX_DISK_UID = 65532

logger = logging.getLogger(__name__)


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


def _disk_uid() -> int:
    raw = (os.environ.get("PICO_SANDBOX_DISK_UID") or "").strip()
    return int(raw) if raw.isdigit() else SANDBOX_DISK_UID


def _hand_fd(fd: int) -> None:
    """Root-created dirs / files go to the sandbox user, or it cannot open pages
    or save into this teacher's disk (#1267). On the open fd, so nothing is followed.
    No-op when not running as root."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    uid = _disk_uid()
    try:
        if os.fstat(fd).st_uid != uid:
            os.fchown(fd, uid, uid)
    except OSError:
        logger.warning("teacher disk chown failed", exc_info=True)


def _refuse_link(where: str) -> NoReturn:
    # The sandbox user owns these dirs, so it can plant a link before a teacher's first
    # open; pico-api is root. Following it would read / write / chown / clear anywhere.
    logger.error("teacher disk: refused a symlink or hard link at %s", where)
    raise ToolError("sandbox.path_denied", "老师盘路径异常，已拒绝")


_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


@contextmanager
def _owner_dir_fd(school_id: str, membership_id: str, *, create: bool) -> Iterator[int]:
    """fd of this teacher's disk dir, walked down from disk_root() one name at a time
    with O_NOFOLLOW: a symlink anywhere below disk_root is refused, never followed.
    Everything after uses this fd (dir_fd / fchown), so there is no check-then-use gap."""
    base = disk_root()
    if create:
        base.mkdir(parents=True, exist_ok=True)
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for seg in (
            safe_segment(school_id, fallback="school"),
            safe_segment(membership_id, fallback="member"),
        ):
            if create:
                try:
                    os.mkdir(seg, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                nfd = os.open(seg, _DIR_FLAGS, dir_fd=fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    _refuse_link(seg)
                raise
            os.close(fd)
            fd = nfd
            if create:
                _hand_fd(fd)
        yield fd
    finally:
        os.close(fd)


def ensure_owner_disk_dir(school_id: str, membership_id: str) -> Path:
    with _owner_dir_fd(school_id, membership_id, create=True):
        pass
    return owner_disk_dir(school_id, membership_id)


def _usage_bytes(dir_fd: int) -> int:
    total = 0
    for _dir, _subdirs, files, dfd in os.fwalk(".", dir_fd=dir_fd, follow_symlinks=False):
        for name in files:
            try:
                st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
    return total


def owner_disk_usage_bytes(school_id: str, membership_id: str) -> int:
    try:
        with _owner_dir_fd(school_id, membership_id, create=False) as dfd:
            return _usage_bytes(dfd)
    except FileNotFoundError:
        return 0


def _assert_quota(dir_fd: int, *, add_bytes: int, replace_bytes: int = 0) -> None:
    quota = owner_disk_quota_bytes()
    projected = _usage_bytes(dir_fd) - max(0, replace_bytes) + max(0, add_bytes)
    if projected > quota:
        raise ToolError("sandbox.quota", QUOTA_COPY)


def list_owner_disk_names(school_id: str, membership_id: str) -> list[str]:
    try:
        with _owner_dir_fd(school_id, membership_id, create=False) as dfd:
            return sorted(
                e.name
                for e in os.scandir(dfd)
                if e.is_file(follow_symlinks=False) and not e.name.startswith(".")
            )
    except FileNotFoundError:
        return []


def _disk_name(filename: str) -> str:
    deny_secret_filename(filename)
    name = Path(filename or "").name
    if not name or name in {".", ".."}:
        raise ToolError("sandbox.path_denied", "文件名非法")
    return name


def owner_disk_file(school_id: str, membership_id: str, filename: str) -> Path:
    root = ensure_owner_disk_dir(school_id, membership_id)
    return join_workspace_path(root, _disk_name(filename))


def _open_file(name: str, flags: int, dfd: int) -> int:
    try:
        fd = os.open(name, flags | _NOFOLLOW, 0o644, dir_fd=dfd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            _refuse_link(name)
        raise
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
        os.close(fd)
        _refuse_link(name)
    return fd


def persist_office_to_owner_disk(
    school_id: str,
    membership_id: str,
    title: str,
    kind: str,
    content: str | bytes,
) -> bool:
    """Same title replaces the file the teacher opens. Ledger stays the source.

    No-op when PICO_SANDBOX_DISK is unset (unit tests without a teacher disk).
    """
    if not os.environ.get("PICO_SANDBOX_DISK", "").strip():
        return False
    low = str(kind or "").lower().lstrip(".")
    if low not in OFFICE_DISK_KINDS:
        return False
    name = Path(title or "").name
    if not name:
        return False
    payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    write_owner_disk_file(school_id, membership_id, name, payload)
    return True


def write_owner_disk_file(
    school_id: str,
    membership_id: str,
    filename: str,
    data: bytes,
) -> Path:
    name = _disk_name(filename)
    with _owner_dir_fd(school_id, membership_id, create=True) as dfd:
        try:
            old = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            old_size = old.st_size if stat.S_ISREG(old.st_mode) else 0
        except FileNotFoundError:
            old_size = 0
        _assert_quota(dfd, add_bytes=len(data), replace_bytes=old_size)
        fd = _open_file(name, os.O_WRONLY | os.O_CREAT, dfd)
        try:
            os.ftruncate(fd, 0)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view) :]
            _hand_fd(fd)
        finally:
            os.close(fd)
    return owner_disk_dir(school_id, membership_id) / name


def read_owner_disk_file(school_id: str, membership_id: str, filename: str) -> bytes:
    name = _disk_name(filename)
    with _owner_dir_fd(school_id, membership_id, create=True) as dfd:
        try:
            fd = _open_file(name, os.O_RDONLY, dfd)
        except (FileNotFoundError, IsADirectoryError):
            raise ToolError("sandbox.file_not_found", "老师盘上没有这个文件") from None
        with os.fdopen(fd, "rb") as f:
            return f.read()


def clear_owner_disk(school_id: str, membership_id: str) -> dict[str, Any]:
    removed = 0
    try:
        with _owner_dir_fd(school_id, membership_id, create=False) as dfd:
            for entry in list(os.scandir(dfd)):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        shutil.rmtree(entry.name, dir_fd=dfd)
                    else:
                        os.unlink(entry.name, dir_fd=dfd)
                    removed += 1
                except OSError:
                    continue
    except FileNotFoundError:
        pass
    return {
        "ok": True,
        "cleared": True,
        "removed": removed,
        "files": list_owner_disk_names(school_id, membership_id),
    }


def owner_disk_meta(school_id: str, membership_id: str) -> dict[str, Any]:
    names = list_owner_disk_names(school_id, membership_id)
    used = owner_disk_usage_bytes(school_id, membership_id)
    return {
        "ok": True,
        "persist": True,
        "files": [{"name": name} for name in names],
        "disk_bytes": used,
        "disk_quota_bytes": owner_disk_quota_bytes(),
        "human_copy": PERSIST_COPY,
    }
