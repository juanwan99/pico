"""Symlink-proof file access inside a workspace (runner runs as root).

The box owns everything under the workspace and may plant symlinks,
FIFOs or swap directories. Every access here walks from the workspace
root one component at a time with ``O_NOFOLLOW`` directory fds and only
reads or writes regular files, so nothing can steer the runner outside.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

WS_UID = 65532
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class UnsafePath(OSError):
    pass


def _open_dir(name: str, dir_fd: int) -> int:
    return os.open(name, _DIR_FLAGS, dir_fd=dir_fd)


def open_chain(ws: Path, parts: tuple[str, ...], *, create: bool) -> int:
    """fd of ``ws/parts...`` (a directory), never following a symlink."""
    fd = os.open(ws, _DIR_FLAGS)
    try:
        for part in parts:
            try:
                nfd = _open_dir(part, fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=fd)
                with contextlib.suppress(OSError):
                    os.chown(part, WS_UID, WS_UID, dir_fd=fd, follow_symlinks=False)
                nfd = _open_dir(part, fd)
            except OSError as exc:
                # ELOOP / ENOTDIR: a symlink or file where a dir should be.
                if not create or exc.errno not in {errno.ELOOP, errno.ENOTDIR}:
                    raise UnsafePath(exc.errno, f"unsafe path component {part!r}") from exc
                os.unlink(part, dir_fd=fd)
                os.mkdir(part, 0o755, dir_fd=fd)
                with contextlib.suppress(OSError):
                    os.chown(part, WS_UID, WS_UID, dir_fd=fd, follow_symlinks=False)
                nfd = _open_dir(part, fd)
            os.close(fd)
            fd = nfd
        return fd
    except BaseException:
        os.close(fd)
        raise


def ensure_dirs(ws: Path, rel: str) -> None:
    fd = open_chain(ws, tuple(PurePosixPath(rel).parts), create=True)
    os.close(fd)


def write_file(ws: Path, rel: PurePosixPath, data: bytes) -> None:
    dfd = open_chain(ws, tuple(rel.parts[:-1]), create=True)
    name = rel.parts[-1]
    try:
        with contextlib.suppress(FileNotFoundError):
            st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                raise UnsafePath(errno.EISDIR, "target is a directory")
            os.unlink(name, dir_fd=dfd)
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o644,
            dir_fd=dfd,
        )
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            with contextlib.suppress(OSError):
                os.fchown(fh.fileno(), WS_UID, WS_UID)
    finally:
        os.close(dfd)


def _open_regular(name: str, dir_fd: int) -> tuple[int, os.stat_result]:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dir_fd)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise UnsafePath(errno.EINVAL, "not a regular file")
    return fd, st


def read_file(ws: Path, rel: PurePosixPath, *, max_bytes: int) -> bytes:
    dfd = open_chain(ws, tuple(rel.parts[:-1]), create=False)
    try:
        fd, st = _open_regular(rel.parts[-1], dfd)
    finally:
        os.close(dfd)
    with os.fdopen(fd, "rb") as fh:
        if st.st_size > max_bytes:
            raise UnsafePath(errno.EFBIG, "file too large")
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UnsafePath(errno.EFBIG, "file too large")
    return data


@dataclass
class OutputRow:
    path: str
    size: int
    mtime: float
    sha256: str


def list_regular(
    ws: Path, top: str, *, max_files: int, max_total: int, max_file: int
) -> tuple[list[OutputRow], bool]:
    """Regular files under ``ws/top`` (no symlinks followed). Returns (rows, truncated)."""
    rows: list[OutputRow] = []
    total = 0
    truncated = False
    try:
        top_fd = open_chain(ws, (top,), create=False)
    except (FileNotFoundError, UnsafePath):
        return rows, False
    try:
        for dirpath, _dirs, files, dfd in os.fwalk(".", dir_fd=top_fd, follow_symlinks=False):
            for name in sorted(files):
                try:
                    st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode) or st.st_size > max_file:
                    continue
                if len(rows) >= max_files or total + st.st_size > max_total:
                    truncated = True
                    return rows, truncated
                try:
                    fd, _ = _open_regular(name, dfd)
                except OSError:
                    continue
                h = hashlib.sha256()
                with os.fdopen(fd, "rb") as fh:
                    for chunk in iter(lambda fh=fh: fh.read(1 << 20), b""):
                        h.update(chunk)
                rel = os.path.normpath(os.path.join(top, dirpath, name))
                rows.append(OutputRow(path=rel, size=st.st_size, mtime=st.st_mtime, sha256=h.hexdigest()))
                total += st.st_size
    finally:
        os.close(top_fd)
    return rows, truncated


def usage(paths: list[Path]) -> tuple[int, int]:
    """(bytes on disk, entry count) under ``paths``; fd-based, never follows links."""
    used = 0
    count = 0
    for base in paths:
        try:
            top = os.open(base, _DIR_FLAGS)
        except OSError:
            continue
        try:
            for _dirpath, dirs, files, dfd in os.fwalk(".", dir_fd=top, follow_symlinks=False):
                for name in files + dirs:
                    count += 1
                    with contextlib.suppress(OSError):
                        used += os.stat(name, dir_fd=dfd, follow_symlinks=False).st_blocks * 512
        finally:
            os.close(top)
    return used, count
