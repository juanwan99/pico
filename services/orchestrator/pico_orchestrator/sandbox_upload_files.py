"""Resolve browser upload filenames against the current run's ledger artifacts."""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

from pico_orchestrator.gateway import ArtifactStore, Principal, ToolError
from pico_orchestrator.sandbox_s1 import deny_secret_filename

_OUTPUT_PARENTS = {PurePosixPath(p) for p in (".", "outputs", "/workspace/outputs")}
_SUGGESTION_COUNT = 5


async def resolve_upload_filenames(
    store: ArtifactStore,
    principal: Principal,
    run_id: str | None,
    filenames: list[str],
) -> tuple[list[str], list[str], dict[str, str]]:
    if not run_id or not filenames:
        return filenames, [], {}

    # list() sorts newest first. Filter by run before limiting the suggestions,
    # so another run's artifacts cannot shadow a title from this run.
    artifacts: dict[str, str] = {}
    for row in await store.list(principal, limit=sys.maxsize):
        if row.get("run_id") == run_id and row.get("title") and row.get("artifact_id"):
            artifacts.setdefault(row["title"], row["artifact_id"])

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
