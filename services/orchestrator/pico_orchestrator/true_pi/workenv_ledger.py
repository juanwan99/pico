"""Workenv cancel + collect ledger gate (host-side). Overlay does not write the ledger."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pico_orchestrator.artifact_types import is_valid_ooxml_package, title_protected_extension
from pico_orchestrator.gateway import ArtifactStore, Principal

COLLECT_GLOBS = ("*.xlsx", "*.docx", "*.pptx", "*.html", "*.png")


class WorkenvCollectRejected(RuntimeError):
    """collect-after-cancel or invalid bytes must not mint Artifact rows."""


@dataclass
class MemoryArtifactStore:
    """In-process ArtifactStore for the isolated PoC. Not a second product ledger."""

    rows: list[dict[str, Any]] = field(default_factory=list)

    async def write(
        self,
        principal: Principal,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        del principal
        raw = content.encode("utf-8") if isinstance(content, str) else content
        row = {
            "id": f"art-{len(self.rows) + 1}",
            "title": title,
            "kind": kind,
            "n": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        self.rows.append(row)
        return row

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        del principal
        for row in self.rows:
            if artifact_id and row["id"] == artifact_id:
                return row
            if title and row["title"] == title:
                return row
        return None

    async def list(self, principal: Principal, *, limit: int) -> list[dict[str, Any]]:
        del principal
        return list(self.rows[:limit])


@dataclass
class WorkenvCancelGate:
    """Single cancel gate from PLAN-WORKENV-UPSTREAM.

    Stop → sticky cancelling → abort duplex → SIGTERM pg → refuse store.write
    → destroy-run → cancelled. collect-after-cancel discards bytes.
    """

    status: str = "running"
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def begin_cancel(self) -> None:
        if self.status not in {"cancelled", "failed"}:
            self.status = "cancelling"

    def finish_cancel(self) -> None:
        if self.status == "cancelling":
            self.status = "cancelled"

    def fail_destroy(self) -> None:
        self.status = "failed"

    def collect_allowed(self) -> bool:
        return self.status not in {"cancelling", "cancelled"}

    async def ingest_collect(
        self,
        principal: Principal,
        store: ArtifactStore,
        files: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not self.collect_allowed():
            raise WorkenvCollectRejected("collect-after-cancel discarded")
        written: list[dict[str, Any]] = []
        for item in files:
            name = str(item.get("name") or "file.bin")
            raw = item.get("bytes")
            if not isinstance(raw, (bytes, bytearray)):
                raise WorkenvCollectRejected(f"missing bytes for {name}")
            blob = bytes(raw)
            ext = title_protected_extension(name)
            if ext in {".docx", ".pptx", ".xlsx"} and not is_valid_ooxml_package(blob, ext):
                raise WorkenvCollectRejected(f"invalid ooxml {name}")
            kind = ext.lstrip(".") if ext else "file"
            row = await store.write(principal, title=name, content=blob, kind=kind)
            written.append(row)
            self.artifacts.append(row)
        return written


def files_from_workdir(work: Path, globs: tuple[str, ...] = COLLECT_GLOBS) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not work.is_dir():
        return out
    for pattern in globs:
        for path in sorted(work.glob(pattern)):
            if path.is_file():
                out.append({"name": path.name, "bytes": path.read_bytes()})
    return out
