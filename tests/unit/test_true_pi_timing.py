"""edu-core#5227: a finished turn ledgers run.timing marks on the loop clock."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.true_pi.timing import TurnTiming


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


def test_rounds_take_first_model_output_only() -> None:
    t = TurnTiming(10.0)
    t.see("agent_start", {}, 10.5)
    t.see("turn_start", {}, 10.6)
    t.see("message_start", {"message": {"role": "user"}}, 10.7)
    t.see("message_end", {"message": {"role": "user"}}, 10.71)
    t.see("text_delta", {}, 11.6)
    t.see("text_delta", {}, 11.9)
    t.see("turn_start", {}, 12.0)
    t.see("message_start", {"message": {"role": "assistant"}}, 12.4)
    t.see("agent_end", {}, 13.0)
    t.see("agent_end", {}, 13.5)
    got = t.payload(13.8)
    assert got["rounds_ms"] == [[600, 1600], [2000, 2400]]
    assert got["ms"] == {"pi_first": 500, "agent_end": 3000, "done": 3800}


@pytest.mark.asyncio
async def test_succeeded_turn_ledgers_timing_before_status() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    reply = {"role": "assistant", "content": [{"type": "text", "text": "好"}]}
    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_start", "message": reply},
            {"type": "message_end", "message": reply},
            {"type": "turn_end", "message": reply, "toolResults": []},
            {"type": "agent_end", "willRetry": False, "messages": [reply]},
        ],
        assistant_text="好",
    )
    result = await run_true_pi_agent(
        prompt="你好",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=30, max_steps=4),
        transport=transport,
        run_id="timing-1",
    )
    assert result.status == "succeeded"
    kinds = [k for k, _ in events]
    timing = dict(events)["run.timing"]
    assert kinds.index("run.timing") < max(i for i, k in enumerate(kinds) if k == "run.status")
    ms = timing["ms"]
    for key in ("ready", "prompt_sent", "pi_first", "agent_end", "done"):
        assert isinstance(ms[key], int) and ms[key] >= 0, key
    assert ms["ready"] <= ms["prompt_sent"] <= ms["agent_end"] <= ms["done"]
    assert len(timing["rounds_ms"]) == 1 and timing["rounds_ms"][0][1] is not None


def _report():
    spec = importlib.util.spec_from_file_location(
        "latency_report", ROOT / "scripts" / "pico-sidebar-latency-report.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_report_splits_run_timing() -> None:
    fine = _report().split_timing(
        {
            "ms": {"ready": 90, "prompt_sent": 95, "pi_first": 900, "agent_end": 4000, "landed": 4700, "done": 4800},
            "rounds_ms": [[950, 2300], [2600, 3100]],
        }
    )
    assert fine == {
        "就绪": 0.09,
        "Pi 起": 0.81,
        "首字合计": 1.85,
        "生成与工具": 1.2,
        "收尾": 0.8,
        "等落盘": 0.7,
    }
    assert _report().split_timing({"ms": {"ready": 1}, "rounds_ms": []}) is None
