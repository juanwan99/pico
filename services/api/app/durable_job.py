"""Server-owned durable staged job (package B).

Wall-clock long runs with checkpoints that survive client disconnect.
Not a substitute for multi-worker HA — process restart still needs 续跑.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from app.auth import Principal
from app.db import ArtifactRow, RunRow, TaskRow, append_event, new_id, session_factory
from app.run_service import _json_dict, _utcnow
from app.settings import get_settings

# In-process registry so continue can find active stage state after detach.
_ACTIVE: dict[str, asyncio.Task[None]] = {}


def _checkpoint_meta(run: RunRow) -> dict[str, Any]:
    data = _json_dict(run.token_usage_json)
    cp = data.get("durable_checkpoint")
    return cp if isinstance(cp, dict) else {}


def _write_checkpoint_blob(
    existing: str | None,
    *,
    stage: int,
    total_stages: int,
    wall_seconds: int,
    elapsed: float,
    status: str,
) -> str:
    base = _json_dict(existing)
    base["durable_checkpoint"] = {
        "kind": "durable_job",
        "stage": stage,
        "total_stages": total_stages,
        "wall_seconds": wall_seconds,
        "elapsed_seconds": int(elapsed),
        "status": status,
        "updated_at": _utcnow().isoformat() + "Z",
    }
    base["estimated"] = True
    return json.dumps(base, ensure_ascii=False)


async def start_durable_job(
    *,
    principal: Principal,
    wall_seconds: int,
    stages: int | None = None,
    title: str | None = None,
    conversation_id: str | None = None,
    resume_from_run_id: str | None = None,
) -> dict[str, Any]:
    """Create ledger rows and schedule the staged runner in-process."""
    settings = get_settings()
    max_wall = max(1, int(settings.pico_run_durable_max_seconds))
    wall = max(1, min(int(wall_seconds), max_wall))
    # Prefer ~30s stages for long gold paths; at least 2 stages.
    if stages is None:
        stages = max(2, min(60, wall // 30))
    stages = max(2, min(int(stages), 120))

    start_stage = 0
    factory = session_factory()
    task_id = new_id()
    run_id = new_id()

    if resume_from_run_id:
        async with factory() as session:
            source = await session.get(RunRow, resume_from_run_id)
            if source is None:
                raise ValueError("source run not found")
            if source.status not in ("failed", "cancelled", "succeeded"):
                raise ValueError("only terminal durable runs can be continued")
            meta = _checkpoint_meta(source)
            if meta.get("kind") != "durable_job":
                raise ValueError("source run is not a durable_job")
            start_stage = int(meta.get("stage") or 0)
            # Continue remaining work on the same task when possible.
            task_id = source.task_id
            wall = int(meta.get("wall_seconds") or wall)
            stages = int(meta.get("total_stages") or stages)
            if start_stage >= stages:
                raise ValueError("durable job already completed all stages")

    async with factory() as session:
        if resume_from_run_id is None:
            session.add(
                TaskRow(
                    id=task_id,
                    school_id=principal.school_id,
                    membership_id=principal.membership_id,
                    title=(title or f"durable-job {wall}s")[:80],
                    conversation_id=conversation_id,
                )
            )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=f"durable_job wall={wall}s stages={stages} from={start_stage}",
                model="pico-durable-job",
                started_at=_utcnow(),
                token_usage_json=_write_checkpoint_blob(
                    None,
                    stage=start_stage,
                    total_stages=stages,
                    wall_seconds=wall,
                    elapsed=0,
                    status="running",
                ),
            )
        )
        await session.commit()
        await append_event(
            session,
            run_id,
            "run.durable",
            {
                "kind": "durable_job",
                "wall_seconds": wall,
                "stages": stages,
                "start_stage": start_stage,
                "detach_on_disconnect": settings.pico_run_detach_on_disconnect,
                "resume_from_run_id": resume_from_run_id,
            },
        )
        await append_event(
            session,
            run_id,
            "run.status",
            {"status": "running", "runtime": "durable-job"},
        )

    bg = asyncio.create_task(
        _run_stages(
            run_id=run_id,
            task_id=task_id,
            wall_seconds=wall,
            stages=stages,
            start_stage=start_stage,
        )
    )
    _ACTIVE[run_id] = bg
    bg.add_done_callback(lambda _t, rid=run_id: _ACTIVE.pop(rid, None))
    return {
        "task_id": task_id,
        "run_id": run_id,
        "wall_seconds": wall,
        "stages": stages,
        "start_stage": start_stage,
    }


async def _run_stages(
    *,
    run_id: str,
    task_id: str,
    wall_seconds: int,
    stages: int,
    start_stage: int,
) -> None:
    factory = session_factory()
    t0 = time.monotonic()
    stage_seconds = wall_seconds / stages
    try:
        for stage in range(start_stage, stages):
            # Cooperative cancel
            async with factory() as session:
                run = await session.get(RunRow, run_id)
                if run is None:
                    return
                if run.cancel_requested or run.status == "cancelled":
                    run.status = "cancelled"
                    run.ended_at = _utcnow()
                    await session.commit()
                    await append_event(
                        session, run_id, "run.status", {"status": "cancelled"}
                    )
                    return

            # Sleep in small slices so cancel is responsive.
            deadline = t0 + stage_seconds * (stage - start_stage + 1)
            # Align total wall from job start for first leg after resume.
            if start_stage == 0:
                deadline = t0 + stage_seconds * (stage + 1)
            else:
                # Resume: only remaining wall from now.
                remaining_stages = stages - start_stage
                remaining_wall = wall_seconds * remaining_stages / stages
                deadline = t0 + remaining_wall * ((stage - start_stage + 1) / remaining_stages)

            last_beat = 0.0
            while True:
                async with factory() as session:
                    run = await session.get(RunRow, run_id)
                    if run and (run.cancel_requested or run.status == "cancelled"):
                        run.status = "cancelled"
                        run.ended_at = _utcnow()
                        await session.commit()
                        await append_event(
                            session, run_id, "run.status", {"status": "cancelled"}
                        )
                        return
                now = time.monotonic()
                if now >= deadline:
                    break
                slice_s = min(1.0, deadline - now)
                await asyncio.sleep(slice_s)
                # Heartbeat at most every 15s (not every second).
                if now - last_beat >= 15.0:
                    last_beat = now
                    async with factory() as session:
                        await append_event(
                            session,
                            run_id,
                            "run.heartbeat",
                            {
                                "elapsed_seconds": int(time.monotonic() - t0),
                                "stage": stage + 1,
                                "total_stages": stages,
                                "runtime": "durable-job",
                            },
                        )

            elapsed = time.monotonic() - t0
            # Checkpoint + artifact for this stage
            marker = f"DURABLE_STAGE_{stage + 1}_OF_{stages}"
            body = (
                f"durable checkpoint stage {stage + 1}/{stages}\n"
                f"elapsed_seconds={int(elapsed)}\n"
                f"wall_target={wall_seconds}\n"
                f"marker={marker}\n"
            )
            raw = body.encode("utf-8")
            art_id = new_id()
            async with factory() as session:
                run = await session.get(RunRow, run_id)
                if run is None:
                    return
                run.token_usage_json = _write_checkpoint_blob(
                    run.token_usage_json,
                    stage=stage + 1,
                    total_stages=stages,
                    wall_seconds=wall_seconds,
                    elapsed=elapsed,
                    status="running",
                )
                session.add(
                    ArtifactRow(
                        id=art_id,
                        task_id=task_id,
                        run_id=run_id,
                        kind="file",
                        title=f"durable-stage-{stage + 1:02d}.txt",
                        inline=body,
                        content_encoding="utf8",
                        content_sha256=hashlib.sha256(raw).hexdigest(),
                        byte_size=len(raw),
                    )
                )
                await session.commit()
                await append_event(
                    session,
                    run_id,
                    "run.checkpoint",
                    {
                        "kind": "durable_job",
                        "stage": stage + 1,
                        "total_stages": stages,
                        "elapsed_seconds": int(elapsed),
                        "artifact_id": art_id,
                        "marker": marker,
                    },
                )
                await append_event(
                    session,
                    run_id,
                    "artifact.created",
                    {
                        "artifact_id": art_id,
                        "title": f"durable-stage-{stage + 1:02d}.txt",
                        "kind": "file",
                    },
                )

        # Success
        elapsed = time.monotonic() - t0
        final = (
            f"durable job completed\n"
            f"stages={stages}\n"
            f"wall_target={wall_seconds}\n"
            f"elapsed_seconds={int(elapsed)}\n"
            f"school_scope=ok\n"
        )
        raw = final.encode("utf-8")
        art_id = new_id()
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            if run is None:
                return
            if run.cancel_requested:
                run.status = "cancelled"
                run.ended_at = _utcnow()
                await session.commit()
                await append_event(
                    session, run_id, "run.status", {"status": "cancelled"}
                )
                return
            run.status = "succeeded"
            run.ended_at = _utcnow()
            run.token_usage_json = _write_checkpoint_blob(
                run.token_usage_json,
                stage=stages,
                total_stages=stages,
                wall_seconds=wall_seconds,
                elapsed=elapsed,
                status="succeeded",
            )
            session.add(
                ArtifactRow(
                    id=art_id,
                    task_id=task_id,
                    run_id=run_id,
                    kind="file",
                    title="durable-final.txt",
                    inline=final,
                    content_encoding="utf8",
                    content_sha256=hashlib.sha256(raw).hexdigest(),
                    byte_size=len(raw),
                )
            )
            await session.commit()
            await append_event(
                session,
                run_id,
                "message.final",
                {
                    "text": f"长任务已完成（{int(elapsed)}s / {stages} 段检查点）。",
                    "role": "assistant",
                },
            )
            await append_event(
                session,
                run_id,
                "artifact.created",
                {"artifact_id": art_id, "title": "durable-final.txt", "kind": "file"},
            )
            await append_event(
                session,
                run_id,
                "run.status",
                {"status": "succeeded", "runtime": "durable-job", "elapsed_seconds": int(elapsed)},
            )
    except asyncio.CancelledError:
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            if run and run.status not in ("succeeded", "failed", "cancelled"):
                run.status = "cancelled"
                run.ended_at = _utcnow()
                run.error = "durable job cancelled"
                await session.commit()
                await append_event(
                    session, run_id, "run.status", {"status": "cancelled"}
                )
        raise
    except Exception as exc:  # noqa: BLE001
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            if run and run.status not in ("succeeded", "failed", "cancelled"):
                run.status = "failed"
                run.ended_at = _utcnow()
                run.error = f"durable job error: {type(exc).__name__}"
                await session.commit()
                await append_event(
                    session,
                    run_id,
                    "run.status",
                    {
                        "status": "failed",
                        "reason": run.error,
                        "user_message": "长任务失败。可点「再跑一次」或从检查点续跑。",
                    },
                )
