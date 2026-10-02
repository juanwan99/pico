"""#1160: mid-run, a model that keeps failing hands the same Pi session to a backup.

LX3 r2 R11 (2026-10-02) sat 51 minutes while gemini returned empty streams and
Pi retried the same model with growing backoff. After output, brain-HA cannot
restart on another model (the work would be redone); Pi's own ``set_model``
switches the live session instead and the next retry goes to the backup.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.brain_ha import SWITCH_AFTER_RETRIES, should_switch_mid_run
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import (
    PI_RETRY_MAX,
    FakeTransport,
    true_pi_models_document,
)
from pico_orchestrator.true_pi.runner import (
    ProxyEntry,
    proxy_entry,
    register_proxy,
    unregister_proxy,
)
from pico_orchestrator.true_pi.runtime import run_true_pi_agent

_CUT = "Stream ended without finish_reason"
_OVERLOADED = '503: {"message":"system cpu overloaded (current: 100.0%, threshold: 90%)"}'
_RID = "switch-t"


class Principal:
    school_id = "school-a"
    membership_id = "member-a"
    scopes = ("ai:run",)


class SpareTransport(FakeTransport):
    """Pi in RPC mode: events of a prompt arrive after its ack."""

    provider = "openai"
    model = "gemini-3.8-flash"

    def __init__(self, scripted: list[dict[str, Any]], backups: list[tuple[str, str]]) -> None:
        super().__init__(scripted=[], assistant_text="已补齐 a.md。")
        self.later = scripted
        self.backups = backups

    async def send(self, command: Any) -> None:
        await super().send(command)
        if command.get("type") == "prompt":
            for item in self.later:
                await self._event_q.put(_rpc(item))
            self.later = []


def _rpc(item: dict[str, Any]):
    from pico_orchestrator.true_pi.client import RpcEvent

    return RpcEvent(item)


def _retry(attempt: int, msg: str = _CUT) -> dict[str, Any]:
    return {
        "type": "auto_retry_start",
        "attempt": attempt,
        "maxAttempts": PI_RETRY_MAX,
        "delayMs": 3000,
        "errorMessage": msg,
    }


def _work() -> list[dict[str, Any]]:
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {
            "type": "tool_execution_start",
            "toolName": "workspace_write_file",
            "toolCallId": "c1",
            "args": {"title": "a.md", "content": "part 1"},
        },
        {
            "type": "tool_execution_end",
            "toolName": "workspace_write_file",
            "toolCallId": "c1",
            "isError": False,
            "result": {"content": [{"type": "text", "text": '{"title":"a.md"}'}]},
        },
    ]


def _done() -> list[dict[str, Any]]:
    done = {"role": "assistant", "content": [{"type": "text", "text": "已补齐 a.md。"}]}
    return [
        {"type": "message_end", "message": done},
        {"type": "turn_end", "message": done},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


async def _run(transport: FakeTransport) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    async def not_cancelled() -> bool:
        return False

    result = await run_true_pi_agent(
        prompt="做一份长报告",
        principal=Principal(),
        emit=emit,
        is_cancelled=not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=30),
        transport=transport,
        run_id=_RID,
    )
    return result, events


def _set_models(transport: FakeTransport) -> list[str]:
    return [str(c.get("modelId")) for c in transport.sent if c.get("type") == "set_model"]


@pytest.fixture
def pinned():
    register_proxy(
        ProxyEntry(
            run_id=_RID,
            llm_token="t",
            llm_upstream="http://up",
            llm_key="k",
            tool_url="",
            tool_token="",
            model="gemini-3.8-flash",
        )
    )
    yield
    unregister_proxy(_RID)


SPARES = [("grok-4.6", "openai-responses"), ("gpt-5.6-sol", "openai-responses")]


@pytest.mark.asyncio
async def test_repeated_cuts_after_output_switch_session_to_backup(pinned) -> None:
    transport = SpareTransport(
        [*_work(), _retry(1), _retry(2), _retry(3), *_done()], SPARES
    )
    result, events = await _run(transport)
    assert result.status == "succeeded", result.error
    sent = [c for c in transport.sent if c.get("type") == "set_model"]
    assert sent == [
        {"id": sent[0]["id"], "type": "set_model", "provider": "openai", "modelId": "grok-4.6"}
    ]
    assert proxy_entry(_RID).model == "grok-4.6"
    switch = [p for k, p in events if k == "model.switch"]
    assert switch and switch[0]["from"] == "gemini-3.8-flash" and switch[0]["to"] == "grok-4.6"
    assert switch[0]["reason"] == _CUT
    assert any("备用模型 grok-4.6" in str(p.get("text")) for k, p in events if k == "message.delta")
    # Only the teacher's original prompt: no restart, no resume prompt.
    assert len([c for c in transport.sent if c.get("type") == "prompt"]) == 1


@pytest.mark.asyncio
async def test_backup_gets_its_own_retries_before_the_next(pinned) -> None:
    retries = [_retry(n) for n in range(1, 7)]
    transport = SpareTransport([*_work(), *retries, *_done()], SPARES)
    result, _events = await _run(transport)
    assert result.status == "succeeded", result.error
    assert _set_models(transport) == ["grok-4.6", "gpt-5.6-sol"]


@pytest.mark.asyncio
async def test_no_switch_before_output_or_on_overload(pinned) -> None:
    # Before output brain-HA restarts on a backup; nothing here.
    transport = SpareTransport(
        [{"type": "agent_start"}, _retry(1), _retry(2), _retry(3), *_done()], SPARES
    )
    await _run(transport)
    assert _set_models(transport) == []
    # Load shedding hits every model; Pi's own backoff stays.
    transport = SpareTransport(
        [*_work(), *[_retry(n, _OVERLOADED) for n in (1, 2, 3, 4)], *_done()], SPARES
    )
    result, _events = await _run(transport)
    assert result.status == "succeeded"
    assert _set_models(transport) == []
    assert proxy_entry(_RID).model == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_a_success_between_failures_restarts_the_count(pinned) -> None:
    transport = SpareTransport(
        [*_work(), _retry(1), _retry(2), _retry(1), _retry(2), *_done()], SPARES
    )
    await _run(transport)
    assert _set_models(transport) == []


def test_switch_policy() -> None:
    assert SWITCH_AFTER_RETRIES == 3
    assert not should_switch_mid_run(2, _CUT)
    assert should_switch_mid_run(3, _CUT)
    assert should_switch_mid_run(3, "502 bad gateway")
    assert not should_switch_mid_run(5, "429 rate limit")


def test_models_document_lists_backups_on_their_own_wire() -> None:
    doc = true_pi_models_document(
        provider="openai",
        model="gemini-3.8-flash",
        max_context=256_000,
        max_tokens=8_000,
        base_url="http://proxy/l/r/v1",
        api="openai-completions",
        backups=SPARES,
    )
    prov = doc["providers"]["openai"]
    models = {m["id"]: m for m in prov["models"]}
    assert list(models) == ["gemini-3.8-flash", "grok-4.6", "gpt-5.6-sol"]
    assert prov["api"] == "openai-completions"
    assert models["gemini-3.8-flash"]["api"] == "openai-completions"
    assert models["grok-4.6"]["api"] == "openai-responses"
    assert models["grok-4.6"]["contextWindow"] == 256_000
    assert "compat" not in models["grok-4.6"]
    json.dumps(doc)  # models.json stays plain JSON
