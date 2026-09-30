"""Shared bits for coding-case checkers (#1090).

A checker runs inside the workspace image with no network, read-only /w:
  /w/out   the conversation's delivered files (zips also unpacked to /w/out/<stem>/)
  /w/in    the case attachments as uploaded
  /w/check this directory
cwd is a writable tmpfs. The last stdout line is JSON:
  {"points": int, "pass": bool, "notes": [str]}
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

OUT = "/w/out"
IN = "/w/in"


def find(name: str, root: str = OUT) -> str | None:
    """Shallowest file called ``name`` under ``root``."""
    best = None
    for dirpath, _dirs, files in os.walk(root):
        if name in files:
            path = os.path.join(dirpath, name)
            if best is None or path.count(os.sep) < best.count(os.sep):
                best = path
    return best


def workdir(src: str, name: str = "work") -> str:
    """Writable copy of ``src`` (a directory) under cwd."""
    dst = os.path.abspath(name)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    return dst


def run(cmd: list[str], cwd: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env, check=False
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"timeout after {timeout}s")


def tail(text: str, n: int = 160) -> str:
    return " ".join((text or "").split())[-n:]


class Score:
    def __init__(self) -> None:
        self.points = 0
        self.notes: list[str] = []
        self.essential_ok = True

    def check(self, ok: bool, note: str, *, essential: bool = True) -> bool:
        if ok:
            self.points += 1
        else:
            self.notes.append(note)
            if essential:
                self.essential_ok = False
        return ok

    def fail(self, note: str) -> None:
        self.notes.append(note)
        self.essential_ok = False

    def emit(self) -> None:
        print(
            json.dumps(
                {"points": self.points, "pass": self.essential_ok, "notes": self.notes},
                ensure_ascii=False,
            )
        )
        sys.exit(0)
