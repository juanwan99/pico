"""Resolve browser upload filenames against the current run's ledger artifacts."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol, cast

from pico_orchestrator.gateway import ArtifactStore, Principal, ToolError
from pico_orchestrator.sandbox_s1 import deny_secret_filename, with_io_timeout

_OUTPUT_PARENTS = {PurePosixPath(p) for p in (".", "outputs", "/workspace/outputs")}
_SUGGESTION_COUNT = 5


class _RunArtifactStore(Protocol):
    async def list_run_titles(self, principal: Principal, *, run_id: str) -> dict[str, str]: ...


async def resolve_upload_filenames(
    store: ArtifactStore,
    principal: Principal,
    run_id: str | None,
    filenames: list[str],
) -> tuple[list[str], list[str], dict[str, str]]:
    if not run_id or not filenames:
        return filenames, [], {}

    artifacts = await with_io_timeout(
        cast(_RunArtifactStore, store).list_run_titles(principal, run_id=run_id),
        what="list current run artifact titles",
    )

    disk_names: list[str] = []
    artifact_ids: list[str] = []
    for name in filenames:
        path = PurePosixPath(name)
        artifact_id = artifacts.get(path.name) if path.parent in _OUTPUT_PARENTS else None
        if artifact_id:
            deny_secret_filename(path.name)
            artifact_ids.append(artifact_id)
        else:
            disk_names.append(name)
    return disk_names, artifact_ids, artifacts


def upload_file_not_found(exc: ToolError, artifacts: dict[str, str]) -> ToolError:
    files = "、".join(
        f"《{title}》({artifact_id})"
        for title, artifact_id in list(artifacts.items())[:_SUGGESTION_COUNT]
    )
    return ToolError(
        exc.code,
        f"{exc.message}。本次 Run 可传产物：{files or '暂无'}。也可用 artifact_ids 指定产物。",
    )
