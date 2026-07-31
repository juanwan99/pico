from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import Principal
from pico_orchestrator.provider import ProviderConfig
from pico_orchestrator.runner import run_agent_loop


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(
        self,
        _principal: Principal,
        *,
        title: str,
        content: str,
        kind: str,
    ) -> dict[str, Any]:
        row = {
            "artifact_id": "artifact-1",
            "title": title,
            "content": content,
            "kind": kind,
        }
        self.rows.append(row)
        return {key: value for key, value in row.items() if key != "content"}

    async def read(
        self,
        _principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in self.rows
                if (artifact_id and row["artifact_id"] == artifact_id)
                or (not artifact_id and row["title"] == title)
            ),
            None,
        )

    async def list(
        self,
        _principal: Principal,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in row.items() if key != "content"}
            for row in self.rows[:limit]
        ]


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **request: Any) -> Any:
        self.calls += 1
        assert "evil.shell" not in {
            tool["function"]["name"] for tool in request["tools"]
        }
        if self.calls == 1:
            message = SimpleNamespace(
                content="",
                tool_calls=[
                    _tool_call("c1", "calculator", {"expression": "6 * 7"}),
                    _tool_call(
                        "c2",
                        "structured_outline",
                        {"text": "# Result\n- Answer"},
                    ),
                    _tool_call(
                        "c3",
                        "workspace_write_file",
                        {
                            "title": "answer.md",
                            "content": "# Result\n42",
                            "kind": "file",
                        },
                    ),
                ],
            )
        elif self.calls == 2:
            message = SimpleNamespace(
                content="",
                tool_calls=[
                    _tool_call("c4", "workspace_list_files", {}),
                    _tool_call("c5", "workspace_read_file", {"title": "answer.md"}),
                ],
            )
        else:
            message = SimpleNamespace(content="已计算并保存 answer.md。", tool_calls=[])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(total_tokens=10),
        )


class FakeAsyncOpenAI:
    completions = FakeCompletions()

    def __init__(self, **_kwargs: Any) -> None:
        self.chat = SimpleNamespace(completions=self.completions)


@pytest.mark.asyncio
async def test_pico_agent_really_invokes_multiple_new_tools(monkeypatch) -> None:
    from pico_orchestrator import runner

    FakeAsyncOpenAI.completions = FakeCompletions()
    monkeypatch.setattr(runner, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(
        runner,
        "resolve_provider",
        lambda: ProviderConfig("test", "key", "https://example.invalid/v1", "test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        events.append((event_type, payload))

    async def is_cancelled() -> bool:
        return False

    store = MemoryArtifactStore()
    result = await run_agent_loop(
        prompt="计算 6*7，整理大纲，保存后再列出并读取产物。",
        principal=P("school-a", "member-a", ["ai:run"]),
        emit=emit,
        is_cancelled=is_cancelled,
        artifact_store=store,
    )

    assert result.status == "succeeded"
    assert result.final_text == "已计算并保存 answer.md。"
    assert store.rows[0]["content"] == "# Result\n42"
    called = [payload["tool"] for kind, payload in events if kind == "tool.call"]
    assert called == [
        "calculator",
        "structured_outline",
        "workspace_write_file",
        "workspace_list_files",
        "workspace_read_file",
    ]
    results = [payload for kind, payload in events if kind == "tool.result"]
    assert len(results) == 5
    assert all(payload["ok"] for payload in results)


@pytest.mark.asyncio
async def test_cancel_during_provider_request_wins_over_token_cap(monkeypatch) -> None:
    from pico_orchestrator import runner

    class TokenCapCompletions:
        async def create(self, **_request: Any) -> Any:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="late", tool_calls=[]),
                    )
                ],
                usage=SimpleNamespace(total_tokens=9000),
            )

    class TokenCapClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=TokenCapCompletions())

    monkeypatch.setattr(runner, "AsyncOpenAI", TokenCapClient)
    monkeypatch.setattr(
        runner,
        "resolve_provider",
        lambda: ProviderConfig("test", "key", "https://example.invalid/v1", "test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []
    cancel_checks = 0

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        events.append((event_type, payload))

    async def is_cancelled() -> bool:
        nonlocal cancel_checks
        cancel_checks += 1
        return cancel_checks >= 2

    result = await run_agent_loop(
        prompt="long request",
        principal=P("school-a", "member-a", ["ai:run"]),
        emit=emit,
        is_cancelled=is_cancelled,
    )

    assert result.status == "cancelled"
    assert events[-1] == ("run.status", {"status": "cancelled"})
    assert not any(payload.get("code") == "token_cap" for _, payload in events)


@pytest.mark.asyncio
async def test_cancel_after_final_provider_response_wins_over_success(monkeypatch) -> None:
    from pico_orchestrator import runner

    class FinalCompletions:
        async def create(self, **_request: Any) -> Any:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="late answer", tool_calls=[]),
                    )
                ],
                usage=SimpleNamespace(total_tokens=10),
            )

    class FinalClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=FinalCompletions())

    monkeypatch.setattr(runner, "AsyncOpenAI", FinalClient)
    monkeypatch.setattr(
        runner,
        "resolve_provider",
        lambda: ProviderConfig("test", "key", "https://example.invalid/v1", "test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []
    cancel_checks = 0

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        events.append((event_type, payload))

    async def is_cancelled() -> bool:
        nonlocal cancel_checks
        cancel_checks += 1
        return cancel_checks >= 3

    result = await run_agent_loop(
        prompt="finish while cancellation arrives",
        principal=P("school-a", "member-a", ["ai:run"]),
        emit=emit,
        is_cancelled=is_cancelled,
    )

    assert result.status == "cancelled"
    assert events[-1] == ("run.status", {"status": "cancelled"})
    assert not any(payload.get("status") == "succeeded" for _, payload in events)
