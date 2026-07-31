"""Artifact-ledger adapter for orchestrator workspace tools."""

from __future__ import annotations

from typing import Any

from pico_orchestrator.gateway import Principal, ToolError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import ArtifactRow, RunRow, TaskRow, append_event, new_id


class LedgerArtifactStore:
    """Persist tools as tenant + membership scoped Artifact rows."""

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        task_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._factory = factory
        self._task_id = task_id
        self._run_id = run_id

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
        content: str,
        kind: str,
    ) -> dict[str, Any]:
        async with self._factory() as session:
            task = await self._task_for_write(session, principal, title)
            artifact = ArtifactRow(
                id=new_id(),
                task_id=task.id,
                run_id=self._run_id,
                kind=kind,
                title=title,
                inline=content,
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
                        "kind": artifact.kind,
                        "source": "workspace_write_file",
                    },
                    commit=False,
                )
            await session.commit()
            return {
                "artifact_id": artifact.id,
                "task_id": task.id,
                "run_id": artifact.run_id,
                "title": artifact.title,
                "kind": artifact.kind,
                "size": len(content.encode("utf-8")),
            }

    def _owned_artifacts(self, principal: Principal):
        return (
            select(ArtifactRow)
            .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
            .where(
                TaskRow.school_id == principal.school_id,
                TaskRow.membership_id == principal.membership_id,
            )
        )

    @staticmethod
    def _artifact_dict(artifact: ArtifactRow, *, content: bool) -> dict[str, Any]:
        data: dict[str, Any] = {
            "artifact_id": artifact.id,
            "task_id": artifact.task_id,
            "run_id": artifact.run_id,
            "title": artifact.title,
            "kind": artifact.kind,
            "size": len((artifact.inline or "").encode("utf-8")),
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }
        if content:
            data["content"] = artifact.inline or ""
        return data

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        statement = self._owned_artifacts(principal)
        if artifact_id:
            statement = statement.where(ArtifactRow.id == artifact_id)
        else:
            statement = statement.where(ArtifactRow.title == title).order_by(
                ArtifactRow.created_at.desc()
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
