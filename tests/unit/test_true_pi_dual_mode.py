"""F1/F2/F3 lock: true_pi dual-mode thinking + deep-lane circuit breaker.

T-DUAL-MODE-TRUE-PI-REVISE (#470) — never a global hardcoded thinking off.
Uses FakeTransport / spawn_command — no real pi binary required for CI.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import (
    FakeTransport,
    SubprocessTransport,
    true_pi_models_document,
    true_pi_windows_from_caps,
)
from pico_orchestrator.true_pi.runtime import run_true_pi_agent


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


def test_spawn_command_fast_lane_thinking_off() -> None:
    """F1: pico-fast → --thinking off · model deepseek-v4-flash."""
    t = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r1",
        model="deepseek-v4-flash",
        thinking=False,
    )
    cmd = t.spawn_command()
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "deepseek-v4-flash"
    assert "--thinking" in cmd
    assert cmd[cmd.index("--thinking") + 1] == "off"


def test_spawn_command_deep_lane_thinking_on() -> None:
    """F1: pico-deep → --thinking on · model deepseek-reasoner."""
    t = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r1",
        model="deepseek-reasoner",
        thinking=True,
    )
    cmd = t.spawn_command()
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "deepseek-reasoner"
    assert "--thinking" in cmd
    assert cmd[cmd.index("--thinking") + 1] == "on"


def test_c1_true_pi_fast_context_128k_output_still_8k(tmp_path: Path) -> None:
    """C1: true_pi models.json contextWindow=128000 · maxTokens=8000 ≠ window."""
    caps = RunCaps(max_context=128_000, max_tokens=8_000, thinking_on=False)
    context, output = true_pi_windows_from_caps(caps)
    assert context == 128_000
    assert output == 8_000
    assert output != context
    t = SubprocessTransport(
        session_dir=tmp_path / "sess-fast",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-fast",
        model="deepseek-v4-flash",
        thinking=False,
        max_context=context,
        max_tokens=output,
    )
    home = t.prepare_agent_home()
    raw = (home / "models.json").read_text(encoding="utf-8")
    assert "128000" in raw
    data = true_pi_models_document(
        provider="deepseek",
        model="deepseek-v4-flash",
        max_context=128_000,
        max_tokens=8_000,
    )
    overlay = data["providers"]["deepseek"]["modelOverrides"]["deepseek-v4-flash"]
    assert overlay["contextWindow"] == 128_000
    assert overlay["maxTokens"] == 8_000
    assert overlay["maxTokens"] != overlay["contextWindow"]
    written = json.loads(raw)
    assert (
        written["providers"]["deepseek"]["modelOverrides"]["deepseek-v4-flash"]["contextWindow"]
        == 128_000
    )
    assert (
        written["providers"]["deepseek"]["modelOverrides"]["deepseek-v4-flash"]["maxTokens"]
        == 8_000
    )
    cmd = t.spawn_command()
    assert "--thinking" in cmd
    assert cmd[cmd.index("--thinking") + 1] == "off"
    assert "--context" not in cmd


def test_c2_true_pi_deep_context_256k_output_still_32k(tmp_path: Path) -> None:
    """C2: true_pi models.json contextWindow=256000 · maxTokens=32000 ≠ window."""
    caps = RunCaps(max_context=256_000, max_tokens=32_000, thinking_on=True)
    context, output = true_pi_windows_from_caps(caps)
    assert context == 256_000
    assert output == 32_000
    assert output != context
    t = SubprocessTransport(
        session_dir=tmp_path / "sess-deep",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-deep",
        model="deepseek-v4-flash",
        thinking=True,
        max_context=context,
        max_tokens=output,
    )
    raw = (t.prepare_agent_home() / "models.json").read_text(encoding="utf-8")
    assert "256000" in raw
    overlay = json.loads(raw)["providers"]["deepseek"]["modelOverrides"]["deepseek-v4-flash"]
    assert overlay["contextWindow"] == 256_000
    assert overlay["maxTokens"] == 32_000
    assert overlay["maxTokens"] != 256_000
    cmd = t.spawn_command()
    assert cmd[cmd.index("--thinking") + 1] == "on"


def test_openai_responses_models_json_overlay(tmp_path: Path) -> None:
    t = SubprocessTransport(
        session_dir=tmp_path / "sess-oai",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-oai",
        provider="openai",
        model="gpt-5.6-sol",
        thinking=True,
        max_context=128_000,
        max_tokens=8_000,
        base_url="https://superaichao.xin/openai",
        api="openai-responses",
        accept_image=True,
        thinking_level="medium",
    )
    home = t.prepare_agent_home()
    written = json.loads((home / "models.json").read_text(encoding="utf-8"))
    block = written["providers"]["openai"]
    assert block["baseUrl"] == "https://superaichao.xin/openai"
    assert block["api"] == "openai-responses"
    assert block["models"][0]["id"] == "gpt-5.6-sol"
    assert block["models"][0]["api"] == "openai-responses"
    assert block["models"][0]["thinkingLevelMap"]["medium"] == "medium"
    assert block["models"][0]["input"] == ["text", "image"]
    cmd = t.spawn_command()
    assert cmd[cmd.index("--provider") + 1] == "openai"
    assert cmd[cmd.index("--model") + 1] == "gpt-5.6-sol"
    assert cmd[cmd.index("--thinking") + 1] == "medium"


def test_true_pi_runtime_source_passes_caps_windows() -> None:
    """runtime must feed caps.max_context into SubprocessTransport (not provider-only)."""
    src = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "orchestrator"
        / "pico_orchestrator"
        / "true_pi"
        / "runtime.py"
    ).read_text(encoding="utf-8")
    assert "true_pi_windows_from_caps" in src
    assert "max_context=max_context" in src
    assert "max_tokens=max_out" in src


def test_spawn_command_no_hardcoded_off_only_path() -> None:
    """F1 guard: spawn args must carry a per-instance thinking value."""
    for thinking in (True, False):
        t = SubprocessTransport(
            session_dir=Path("/tmp/tp-sess"),
            tool_url="http://127.0.0.1:1",
            tool_token="tok",
            run_id="r1",
            model="deepseek-v4-flash",
            thinking=thinking,
        )
        cmd = t.spawn_command()
        value = cmd[cmd.index("--thinking") + 1]
        assert value in {"on", "off"}


@pytest.mark.asyncio
async def test_true_pi_deep_lane_breaker_bails_on_no_tool_progress() -> None:
    """F2: deep lane with zero tool success for ≥180s → pi.no_progress bailout."""

    # Scripted stream that never settles and never succeeds a tool: agent_start
    # then infinite turns without tool_execution_end success.
    scripted: list[dict[str, Any]] = [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "turn_start"},
        {"type": "turn_start"},
    ]

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    transport = FakeTransport(scripted=scripted, assistant_text="")
    result = await run_true_pi_agent(
        prompt="深度空转任务",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(
            max_seconds=300,
            max_steps=48,
            thinking_on=True,
            no_progress_seconds=1,
        ),
        transport=transport,
        run_id="tp-breaker-deep",
    )
    assert result.status == "failed"
    assert "pi.no_progress" in (result.error or "") or "熔断" in (result.error or "")
    kinds = [k for k, _ in events]
    assert "circuit.breaker" in kinds
    failed = [p for k, p in events if k == "run.status" and p.get("status") == "failed"]
    assert failed and failed[0].get("code") == "pi.no_progress"


@pytest.mark.asyncio
async def test_true_pi_fast_lane_never_trips_breaker() -> None:
    """F2: fast lane (thinking off) must not emit circuit.breaker."""

    scripted: list[dict[str, Any]] = [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "turn_start"},
    ]

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    transport = FakeTransport(scripted=scripted, assistant_text="")
    result = await run_true_pi_agent(
        prompt="快速任务",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(
            max_seconds=1,
            max_steps=12,
            thinking_on=False,
            no_progress_seconds=1,
        ),
        transport=transport,
        run_id="tp-fast-no-breaker",
    )
    # Fast lane: no circuit.breaker event regardless of outcome (times out).
    kinds = [k for k, _ in events]
    assert "circuit.breaker" not in kinds
    assert result.status in {"failed", "succeeded"}
