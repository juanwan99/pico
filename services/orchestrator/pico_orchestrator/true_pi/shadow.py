"""Dual-run (shadow) framework: hosted primary + true-Pi side report.

When PICO_TRUE_PI_SHADOW=1, after hosted multi-step finishes, run true Pi
with a non-ledger emit and write a diff summary. Failures never change the
hosted result.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pico_orchestrator.gateway import ArtifactStore, Principal
from pico_orchestrator.run_types import RunCaps, RunResult
from pico_orchestrator.true_pi.client import TruePiTransport
from pico_orchestrator.true_pi.config import RUNTIME_LABEL, session_root, shadow_enabled
from pico_orchestrator.true_pi.runtime import run_true_pi_agent

logger = logging.getLogger(__name__)


@dataclass
class ShadowReport:
    run_id: str
    prompt_preview: str
    hosted_status: str
    shadow_status: str
    hosted_event_kinds: list[str] = field(default_factory=list)
    shadow_event_kinds: list[str] = field(default_factory=list)
    hosted_artifact_writes: int = 0
    shadow_artifact_writes: int = 0
    hosted_tool_events: int = 0
    shadow_tool_events: int = 0
    notes: list[str] = field(default_factory=list)
    ok_for_phase1: bool = False
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def shadow_diff(
    *,
    hosted_status: str,
    shadow_status: str,
    hosted_events: list[tuple[str, dict[str, Any]]],
    shadow_events: list[tuple[str, dict[str, Any]]],
    hosted_writes: int = 0,
    shadow_writes: int = 0,
) -> ShadowReport:
    """Build a structural diff summary (no secrets)."""
    h_kinds = [k for k, _ in hosted_events]
    s_kinds = [k for k, _ in shadow_events]
    h_tools = sum(1 for k in h_kinds if k.startswith("tool."))
    s_tools = sum(1 for k in s_kinds if k.startswith("tool."))
    notes: list[str] = []
    if hosted_status != shadow_status:
        notes.append(f"status_mismatch hosted={hosted_status} shadow={shadow_status}")
    # False-green: shadow succeeded while writes insufficient is caught by runtime gate;
    # here flag if shadow succeeded with zero tool events when hosted used tools.
    if shadow_status == "succeeded" and s_tools == 0 and h_tools > 0:
        notes.append("shadow_succeeded_without_tool_events")
    if shadow_status == "succeeded" and shadow_writes == 0 and hosted_writes > 0:
        notes.append("shadow_succeeded_without_writes_while_hosted_wrote")
    ok = (
        "shadow_succeeded_without_tool_events" not in notes
        and "shadow_succeeded_without_writes_while_hosted_wrote" not in notes
    )
    return ShadowReport(
        run_id="",
        prompt_preview="",
        hosted_status=hosted_status,
        shadow_status=shadow_status,
        hosted_event_kinds=_uniq(h_kinds),
        shadow_event_kinds=_uniq(s_kinds),
        hosted_artifact_writes=hosted_writes,
        shadow_artifact_writes=shadow_writes,
        hosted_tool_events=h_tools,
        shadow_tool_events=s_tools,
        notes=notes,
        ok_for_phase1=ok,
    )


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


async def maybe_shadow_after_hosted(
    *,
    prompt: str,
    principal: Principal,
    hosted_result: RunResult,
    hosted_events: list[tuple[str, dict[str, Any]]] | None = None,
    caps: RunCaps | None = None,
    artifact_store: ArtifactStore | None = None,
    is_cancelled: Callable[[], Awaitable[bool]] | None = None,
    transport: TruePiTransport | None = None,
    report_dir: Path | None = None,
    force: bool = False,
) -> ShadowReport | None:
    """Run shadow true-Pi if enabled (or force=True for tests). Never raises out."""
    if not force and not shadow_enabled():
        return None

    rid = f"shadow-{uuid.uuid4().hex[:12]}"
    shadow_events: list[tuple[str, dict[str, Any]]] = []
    t0 = time.monotonic()

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        shadow_events.append((kind, payload))

    async def _not_cancelled() -> bool:
        return False

    cancel = is_cancelled or _not_cancelled
    try:
        result = await run_true_pi_agent(
            prompt=prompt,
            principal=principal,
            emit=emit,
            is_cancelled=cancel,
            caps=caps,
            artifact_store=artifact_store,
            transport=transport,
            shadow=True,
            run_id=rid,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("true_pi shadow failed (hosted unaffected): %s", type(exc).__name__)
        result = RunResult(status="failed", final_text="", error=type(exc).__name__)
        shadow_events.append(
            ("run.status", {"status": "failed", "runtime": RUNTIME_LABEL, "shadow": True})
        )

    from pico_orchestrator.pi_runtime import count_write_tool_successes

    # Approximate writes from tool.result events.
    s_writes = 0
    tool_pairs: list[tuple[str, dict[str, Any]]] = []
    for kind, payload in shadow_events:
        if kind == "tool.result" and payload.get("ok"):
            name = str(payload.get("tool") or "")
            try:
                body = json.loads(payload.get("result") or "{}")
            except json.JSONDecodeError:
                body = {}
            tool_pairs.append((name, body if isinstance(body, dict) else {}))
    s_writes = count_write_tool_successes(tool_pairs)

    h_events = hosted_events or [
        ("run.status", {"status": hosted_result.status, "runtime": "pi-agent"})
    ]
    report = shadow_diff(
        hosted_status=hosted_result.status,
        shadow_status=result.status,
        hosted_events=h_events,
        shadow_events=shadow_events,
        hosted_writes=0,
        shadow_writes=s_writes,
    )
    report.run_id = rid
    report.prompt_preview = (prompt or "")[:160]
    report.elapsed_ms = int((time.monotonic() - t0) * 1000)

    out_dir = report_dir or (session_root() / "shadow-reports")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{rid}.json"
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "true_pi shadow report run_id=%s path=%s ok=%s",
            rid,
            path,
            report.ok_for_phase1,
        )
    except OSError as exc:
        logger.warning("true_pi shadow report write failed: %s", type(exc).__name__)

    return report
