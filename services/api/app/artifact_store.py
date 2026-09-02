"""Artifact-ledger adapter for orchestrator workspace tools."""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

from pico_orchestrator.gateway import Principal, ToolError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import ArtifactRow, PersonalFolderRow, RunRow, TaskRow, append_event, new_id

ENCODING_UTF8 = "utf8"
ENCODING_BASE64 = "base64"
# GET /v1/tasks/{id} is polled every 2s. Vendored Pico CSS alone is ~71KiB;
# six inlined PNGs became ~12MiB and froze the result-area chips.
TASK_LIST_INLINE_MAX_BYTES = 8_192
logger = logging.getLogger(__name__)


def artifact_inline_for_list(
    *,
    encoding: str | None,
    inline: str | None,
    byte_size: int,
) -> str | None:
    """Metadata chips only. Open/download uses GET …/content."""
    enc = (encoding or ENCODING_UTF8).strip().lower() or ENCODING_UTF8
    if enc != ENCODING_UTF8:
        return None
    size = int(byte_size or 0)
    if size <= 0 and isinstance(inline, str):
        size = len(inline.encode("utf-8"))
    if size > TASK_LIST_INLINE_MAX_BYTES:
        return None
    return inline


def encode_artifact_payload(content: str | bytes) -> tuple[str, str, int, str]:
    """Return (stored_inline, encoding, byte_size, sha256_hex)."""
    if isinstance(content, bytes):
        raw = content
        stored = base64.b64encode(raw).decode("ascii")
        encoding = ENCODING_BASE64
    elif isinstance(content, str):
        raw = content.encode("utf-8")
        stored = content
        encoding = ENCODING_UTF8
    else:
        raise ToolError("tool.invalid_arguments", "content must be str or bytes")
    digest = hashlib.sha256(raw).hexdigest()
    return stored, encoding, len(raw), digest


def decode_artifact_payload(inline: str | None, encoding: str | None) -> bytes:
    """Restore original bytes from ledger storage."""
    enc = (encoding or ENCODING_UTF8).strip().lower() or ENCODING_UTF8
    payload = inline or ""
    if enc == ENCODING_BASE64:
        try:
            return base64.b64decode(payload.encode("ascii"), validate=False)
        except Exception as exc:
            raise ToolError("artifact.corrupt", "Binary artifact payload is corrupt") from exc
    return payload.encode("utf-8")


class LedgerArtifactStore:
    """Persist tools as tenant + membership scoped Artifact rows."""

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        task_id: str | None = None,
        run_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        self._factory = factory
        self._task_id = task_id
        self._run_id = run_id
        self._conversation_id = str(conversation_id or "").strip() or None

    async def _task_for_write(
        self,
        session: AsyncSession,
        principal: Principal,
        title: str,
    ) -> TaskRow:
        task_id = self._task_id
        if self._run_id:
            run = await session.get(RunRow, self._run_id)
            if run is None:
                raise ToolError("artifact.context_invalid", "Run context not found")
            if task_id and run.task_id != task_id:
                raise ToolError("artifact.context_invalid", "Run/task context mismatch")
            task_id = run.task_id

        if task_id:
            task = await session.get(TaskRow, task_id)
            if task is None:
                raise ToolError("artifact.context_invalid", "Task context not found")
            if (
                task.school_id != principal.school_id
                or task.membership_id != principal.membership_id
            ):
                raise ToolError("tenant.cross_membership", "Artifact task owner mismatch")
            return task

        task = TaskRow(
            id=new_id(),
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            title=f"工具工作区 · {title}"[:512],
        )
        session.add(task)
        await session.flush()
        return task

    async def write(
        self,
        principal: Principal,
        *,
        title: str,
        content: str | bytes,
        kind: str,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        stored, encoding, byte_size, digest = encode_artifact_payload(content)
        async with self._factory() as session:
            task = await self._task_for_write(session, principal, title)
            explicit_folder = folder_id is not None and str(folder_id).strip() != ""
            if explicit_folder:
                folder_id = str(folder_id).strip()
            else:
                folder_id = ""
            convo = self._conversation_id or getattr(task, "conversation_id", None)
            if convo and not explicit_folder:
                try:
                    from app.edu_school import load_archive_folder_id

                    folder_id = await load_archive_folder_id(
                        session,
                        principal.school_id,
                        principal.membership_id,
                        str(convo),
                    )
                except Exception as exc:  # noqa: BLE001 — folder miss must not swallow the file
                    logger.warning("archive folder lookup failed: %s", type(exc).__name__)
                    folder_id = ""
            if folder_id:
                folder = await session.get(PersonalFolderRow, folder_id)
                if (
                    folder is None
                    or folder.school_id != principal.school_id
                    or folder.membership_id != principal.membership_id
                ):
                    folder_id = ""
            artifact = ArtifactRow(
                id=new_id(),
                task_id=task.id,
                run_id=self._run_id,
                kind=kind,
                title=title,
                inline=stored,
                content_encoding=encoding,
                content_sha256=digest,
                byte_size=byte_size,
                folder_id=folder_id,
            )
            session.add(artifact)
            await session.flush()
            if self._run_id:
                await append_event(
                    session,
                    self._run_id,
                    "artifact.created",
                    {
                        "artifact_id": artifact.id,
                        "title": artifact.title,
                        "user_label": artifact.title,
                        "kind": artifact.kind,
                        "source": "workspace_write_file",
                        "content_encoding": encoding,
                        "byte_size": byte_size,
                        "content_sha256": digest,
                        "download_path": (
                            f"/v1/artifacts/{artifact.id}/content?download=true"
                        ),
                    },
                    commit=False,
                )
            await session.commit()
            out = {
                "artifact_id": artifact.id,
                "task_id": task.id,
                "run_id": artifact.run_id,
                "title": artifact.title,
                "user_label": artifact.title,
                "kind": artifact.kind,
                "size": byte_size,
                "byte_size": byte_size,
                "content_encoding": encoding,
                "content_sha256": digest,
                "download_path": f"/v1/artifacts/{artifact.id}/content?download=true",
                "folder_id": getattr(artifact, "folder_id", "") or "",
            }
        try:
            from pico_orchestrator.meili_kb import project_material_artifact

            project_material_artifact(
                principal,
                artifact_id=str(out["artifact_id"]),
                title=title,
                kind=kind,
                content=content,
            )
        except Exception as exc:  # noqa: BLE001 — projection must not block the ledger
            logger.warning("meili project after write failed: %s", type(exc).__name__)
        try:
            from pico_orchestrator.sandbox_persist import persist_office_to_owner_disk

            persist_office_to_owner_disk(
                principal.school_id,
                principal.membership_id,
                title,
                kind,
                content,
            )
        except Exception as exc:  # noqa: BLE001 — disk projection must not swallow the ledger
            logger.warning("owner-disk persist after write failed: %s", type(exc).__name__)
        return out

    def _owned_artifacts(self, principal: Principal):
        stmt = (
            select(ArtifactRow)
            .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
            .where(
                TaskRow.school_id == principal.school_id,
                TaskRow.membership_id == principal.membership_id,
            )
        )
        if self._conversation_id:
            # This conversation + uploads that arrived before the first message
            # (task.conversation_id is null). Never dump other cabinets.
            stmt = stmt.where(
                or_(
                    TaskRow.conversation_id == self._conversation_id,
                    TaskRow.conversation_id.is_(None),
                )
            )
        return stmt

    @staticmethod
    def _artifact_dict(artifact: ArtifactRow, *, content: bool) -> dict[str, Any]:
        encoding = getattr(artifact, "content_encoding", None) or ENCODING_UTF8
        byte_size = int(getattr(artifact, "byte_size", 0) or 0)
        if byte_size <= 0:
            # Legacy rows before byte_size column.
            if encoding == ENCODING_BASE64:
                try:
                    byte_size = len(decode_artifact_payload(artifact.inline, encoding))
                except ToolError:
                    byte_size = 0
            else:
                byte_size = len((artifact.inline or "").encode("utf-8"))
        digest = getattr(artifact, "content_sha256", None) or ""
        if not digest:
            try:
                digest = hashlib.sha256(
                    decode_artifact_payload(artifact.inline, encoding)
                ).hexdigest()
            except ToolError:
                digest = ""
        data: dict[str, Any] = {
            "artifact_id": artifact.id,
            "task_id": artifact.task_id,
            "run_id": artifact.run_id,
            "title": artifact.title,
            "kind": artifact.kind,
            "size": byte_size,
            "byte_size": byte_size,
            "content_encoding": encoding,
            "content_sha256": digest,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }
        if content:
            if encoding == ENCODING_BASE64:
                # Do not pretend binary is UTF-8 text.
                data["content_base64"] = artifact.inline or ""
                data["content"] = None
            else:
                data["content"] = artifact.inline or ""
        return data

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        if artifact_id:
            statement = (
                select(ArtifactRow)
                .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
                .where(
                    TaskRow.school_id == principal.school_id,
                    TaskRow.membership_id == principal.membership_id,
                    ArtifactRow.id == artifact_id,
                )
            )
        else:
            statement = (
                self._owned_artifacts(principal)
                .where(ArtifactRow.title == title)
                .order_by(ArtifactRow.created_at.desc())
            )
        async with self._factory() as session:
            result = await session.execute(statement.limit(1))
            artifact = result.scalar_one_or_none()
            return self._artifact_dict(artifact, content=True) if artifact else None

    async def list(
        self,
        principal: Principal,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        statement = self._owned_artifacts(principal).order_by(
            ArtifactRow.created_at.desc()
        )
        async with self._factory() as session:
            result = await session.execute(statement.limit(limit))
            return [
                self._artifact_dict(artifact, content=False)
                for artifact in result.scalars().all()
            ]
