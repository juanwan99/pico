"""pico#1331「我的接口」: a personal endpoint gets exactly one model attempt.

``run_true_pi_agent``'s outer HA loop normally retries a failed primary on
up to one backup model (``brain_candidates``). For a personal (teacher's own
OpenAI-compatible) endpoint that backup is a model the endpoint never
serves, which is the fallback-shape the card forbids — so the loop must
collapse to a single attempt on exactly the caller's own model.

This cannot be exercised through the existing ``transport=`` injection
pattern used by test_true_pi_resume.py / test_true_pi_p1.py etc.: passing a
transport takes ``run_true_pi_agent``'s early-return branch, which skips the
whole HA loop (and the real ``SubprocessTransport``/``pi_base`` construction
deeper in ``_run_true_pi_once``). So here we leave ``transport=None`` — the
real code path — and stub ``_run_true_pi_once`` itself (module-level name,
resolved at call time, same technique brain_ha tests use for should_failover
inputs) to avoid actually spawning Pi.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import ProviderConfig, personal_provider_scope
from pico_orchestrator.run_types import RunCaps, RunResult
from pico_orchestrator.true_pi import runtime as true_pi_runtime


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _personal_cfg() -> ProviderConfig:
    return ProviderConfig(
        name="personal",
        api_key="sk-teacher-own-key",
        base_url="https://teacher.example/v1",
        model="gpt-4o-mini",
    )


@pytest.mark.asyncio
async def test_personal_endpoint_failure_does_not_retry_on_backup_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model-level failure on the personal endpoint stops after one try.

    Without the pico#1331 guard, ``brain_candidates(primary)`` would append
    a school backup (e.g. grok-4.6) and this loop would attempt it against
    the *same* personal base_url — a model that endpoint never serves.
    """
    attempts: list[str] = []

    async def _fake_once(*, emit: Any, **kwargs: Any) -> RunResult:
        caps = kwargs["caps"]
        attempts.append(str(caps.backend_model))
        # A code should_failover() treats as retry-worthy on a first attempt
        # (see brain_ha._MODEL_FAIL_CODES) — proves the guard, not an
        # incidental non-retryable failure, is what stopped the loop.
        return RunResult(status="failed", final_text="", error="boom", code="true_pi.assistant_error")

    monkeypatch.setattr(true_pi_runtime, "_run_true_pi_once", _fake_once)

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    with personal_provider_scope(_personal_cfg()):
        result = await true_pi_runtime.run_true_pi_agent(
            prompt="hi",
            principal=Principal(),
            emit=emit,
            is_cancelled=_not_cancelled,
            caps=RunCaps(backend_model="gpt-4o-mini", ui_model="pico-fast"),
        )

    assert attempts == ["gpt-4o-mini"]
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_school_model_same_failure_does_retry_on_backup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: the same failure *without* a personal scope still fails over.

    Proves the single-attempt behaviour above is specific to the personal
    scope, not a change in should_failover()/brain_candidates() themselves.
    """
    attempts: list[str] = []

    async def _fake_once(*, emit: Any, **kwargs: Any) -> RunResult:
        caps = kwargs["caps"]
        attempts.append(str(caps.backend_model))
        return RunResult(status="failed", final_text="", error="boom", code="true_pi.assistant_error")

    monkeypatch.setattr(true_pi_runtime, "_run_true_pi_once", _fake_once)
    # brain_candidates is imported *inside* run_true_pi_agent on every call
    # (fresh `from pico_orchestrator.brain_ha import brain_candidates`), so
    # the patch target is the source module's attribute, not runtime's.
    from pico_orchestrator import brain_ha

    monkeypatch.setattr(brain_ha, "brain_candidates", lambda primary: [primary, "grok-4.6-backup"])

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        return None

    result = await true_pi_runtime.run_true_pi_agent(
        prompt="hi",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(backend_model="deepseek-v4-flash", ui_model="pico-fast"),
    )

    assert attempts == ["deepseek-v4-flash", "grok-4.6-backup"]
    assert result.status == "failed"
