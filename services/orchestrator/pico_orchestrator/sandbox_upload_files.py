"""Resolve browser upload filenames against run artifacts and workspace outputs."""

from __future__ import annotations

import base64
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
) -> tuple[list[str], list[str], list[dict[str, str]], dict[str, str]]:
    if not run_id or not filenames:
        return filenames, [], [], {}

    from pico_orchestrator.true_pi import runner

    artifacts = await with_io_timeout(
        cast(_RunArtifactStore, store).list_run_titles(principal, run_id=run_id),
        what="list current run artifact titles",
    )

    disk_names: list[str] = []
    artifact_ids: list[str] = []
    workspace_files: list[dict[str, str]] = []
    entry = runner.proxy_entry(run_id)
    workspace = entry.workspace_key if entry else None
    for name in filenames:
        path = PurePosixPath(name)
        if path.parent not in _OUTPUT_PARENTS or not path.name:
            disk_names.append(name)
            continue
        artifact_id = artifacts.get(path.name)
        if artifact_id:
            deny_secret_filename(path.name)
            artifact_ids.append(artifact_id)
        elif workspace is not None:
            deny_secret_filename(path.name)
            try:
                raw = await runner.fetch_output(workspace, f"outputs/{path.name}")
            except runner.RunnerOutputNotFound:
                disk_names.append(name)
            else:
                workspace_files.append(
                    {"name": path.name, "b64": base64.b64encode(raw).decode("ascii")}
                )
        else:
            disk_names.append(name)
    return disk_names, artifact_ids, workspace_files, artifacts


async def upload_file_not_found(
    exc: ToolError, artifacts: dict[str, str], run_id: str | None
) -> ToolError:
    from pico_orchestrator.true_pi import runner

    files = "、".join(
        f"《{title}》({artifact_id})"
        for title, artifact_id in list(artifacts.items())[:_SUGGESTION_COUNT]
    )
    message = f"{exc.message}。本次 Run 可传产物：{files or '暂无'}。"
    entry = runner.proxy_entry(run_id) if run_id else None
    if entry and entry.workspace_key is not None:
        outputs = await runner.list_outputs(entry.workspace_key, allow_busy=True)
        names = [path for path in outputs if PurePosixPath(path).parent == PurePosixPath("outputs")]
        message += f"盒内 outputs 文件：{'、'.join(names[:_SUGGESTION_COUNT]) or '暂无'}。"
    return ToolError(exc.code, f"{message}也可用 artifact_ids 指定产物。")
