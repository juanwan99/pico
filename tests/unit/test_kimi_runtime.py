"""Legacy Kimi path tests — optional (need kimi-agent-sdk).

Gate/routing coverage for Pi default lives in test_pi_runtime.py.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from app.settings import Settings
from pico_orchestrator.run_types import RunResult
from pico_orchestrator.runtime import run_agent_runtime

pytest.importorskip("kimi_agent_sdk")


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _noop_emit(_kind: str, _payload: dict[str, Any]) -> None:
    return None


@pytest.mark.asyncio
async def test_runtime_canary_gate_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def kimi_loop(**_kwargs: Any) -> RunResult:
        calls.append("kimi")
        return RunResult(status="succeeded", final_text="kimi")

    import pico_orchestrator.runtime as rt

    monkeypatch.setattr(rt, "_KIMI_IMPL", kimi_loop)

    principal = Principal()
    joint = (principal.school_id, principal.membership_id)
    gate_off = await run_agent_runtime(
        use_pi_agent=False,
        use_kimi_agent=False,
        kimi_agent_canary_principals={joint},
        principal=principal,
        prompt="hello",
        emit=_noop_emit,
    )
    allowlisted = await run_agent_runtime(
        use_pi_agent=False,
        use_kimi_agent=True,
        kimi_agent_canary_principals={joint},
        principal=principal,
        prompt="hello",
        emit=_noop_emit,
    )
    assert gate_off.status == "failed"
    assert allowlisted.final_text == "kimi"
    assert calls == ["kimi"]


def test_settings_legacy_kimi_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_KIMI_AGENT_RUNTIME", raising=False)
    monkeypatch.delenv("PICO_LEGACY_KIMI_AGENT_RUNTIME", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.legacy_kimi_enabled is False
    assert defaults.pico_pi_agent_runtime is True


def test_runtime_no_import_of_removed_runner() -> None:
    root = Path(__file__).resolve().parents[2]
    runner = root / "services" / "orchestrator" / "pico_orchestrator" / "runner.py"
    assert not runner.is_file()
    assert importlib.util.find_spec("pico_orchestrator.runner") is None
