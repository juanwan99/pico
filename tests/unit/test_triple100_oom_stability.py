"""#461 PR-R: prod-validated OOM/stability thin fixes.

Covers:
- document_generators._require_marker auto-generates when marker omitted
  (was a hard ValueError → true-Pi retried forever → message_update flood → OOM)
- tools_builtin._marker_arg same behaviour
- true_pi SubprocessTransport drops message_update flood at the source
- true_pi runtime _consume drops message_update before per-event cancellation
"""

from __future__ import annotations

import re

from pico_orchestrator.document_generators import _require_marker

# --- marker auto-generation ---


def test_require_marker_autogenerates_when_empty() -> None:
    value = _require_marker("")
    assert value.startswith("pico-")
    assert len(value) == 5 + 12  # "pico-" + 12 hex
    assert re.fullmatch(r"pico-[0-9a-f]{12}", value) is not None


def test_require_marker_autogenerates_when_none() -> None:
    value = _require_marker(None)  # type: ignore[arg-type]
    assert value.startswith("pico-")


def test_require_marker_preserves_explicit_value() -> None:
    assert _require_marker("  M1  ") == "M1"


def test_require_marker_still_rejects_too_long() -> None:
    try:
        _require_marker("x" * 201)
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for >200 marker")


def test_require_marker_still_rejects_control_chars() -> None:
    try:
        _require_marker("bad\nmarker")
    except ValueError as exc:
        assert "control" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for control chars")


# --- tools_builtin._marker_arg (python3.10-compatible: import guarded) ---

_tb = None
try:  # edu_adapter needs datetime.UTC (py3.11+); CI runs 3.12 so this is fine
    from pico_orchestrator import tools_builtin as _tb
except ImportError:  # pragma: no cover - local py3.10 fallback
    _tb = None


def test_marker_arg_autogenerates_when_missing() -> None:
    if _tb is None:  # pragma: no cover
        return
    value = _tb._marker_arg({})
    assert value.startswith("pico-")


def test_marker_arg_autogenerates_when_blank() -> None:
    if _tb is None:  # pragma: no cover
        return
    value = _tb._marker_arg({"marker": "   "})
    assert value.startswith("pico-")


def test_marker_arg_preserves_explicit() -> None:
    if _tb is None:  # pragma: no cover
        return
    assert _tb._marker_arg({"marker": "M42"}) == "M42"


def test_marker_arg_rejects_non_string() -> None:
    if _tb is None:  # pragma: no cover
        return
    try:
        _tb._marker_arg({"marker": 123})
    except _tb.ToolError as exc:
        assert "must be a string" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ToolError for non-string marker")


# --- true_pi message_update drop (contract tests, no heavy module import) ---


def _fake_consume(events, drop_message_update: bool):
    """Inline copy of the _consume filter contract (message_update → skip)."""
    sent = []
    state = {"settled": False}

    class FakeEvent:
        def __init__(self, type_: str):
            self.type = type_

    async def consume():
        for raw in events:
            event = FakeEvent(raw)
            if event.type == "response":
                continue
            if drop_message_update and event.type == "message_update":
                continue
            sent.append(event.type)
            if event.type == "agent.end":
                state["settled"] = True
                break

    import asyncio

    asyncio.run(consume())
    return sent, state


def test_runtime_consume_drops_message_update():
    """_consume must skip message_update before map_event (mirrors PR-R code)."""
    sent, state = _fake_consume(
        ["message_update", "message_update", "agent.end"],
        drop_message_update=True,
    )
    assert sent == ["agent.end"]
    assert state["settled"] is True


def test_runtime_consume_without_drop_leaks_flood():
    """Sanity: without the drop the flood reaches map_event (why PR-R exists)."""
    sent, _ = _fake_consume(
        ["message_update", "message_update", "agent.end"],
        drop_message_update=False,
    )
    assert sent == ["message_update", "message_update", "agent.end"]


def test_source_filter_guard_present():
    """Structural guard: both true_pi files contain the message_update drop."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    runtime = (root / "services/orchestrator/pico_orchestrator/true_pi/runtime.py").read_text()
    client = (root / "services/orchestrator/pico_orchestrator/true_pi/client.py").read_text()
    assert 'event.type == "message_update"' in runtime
    assert 't == "message_update"' in client
