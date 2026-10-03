"""tool.call step_line names what the call works on, not「正在调工具」(#1169)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.client import RpcEvent
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.workbench_progress import workbench_call_step_line


@pytest.mark.parametrize(
    ("tool", "args", "line"),
    [
        ("read", {"path": "/workspace/attachments/秋天的雨.docx"}, "正在读 秋天的雨.docx"),
        ("read", {"path": "/workspace/attachments/"}, "正在读 attachments"),
        ("write", {"path": "/workspace/outputs/教案.docx", "content": "x"}, "正在写 教案.docx"),
        ("edit", {"path": "/workspace/make_doc.py", "edits": []}, "正在改 make_doc.py"),
        ("bash", {"command": "cd /workspace && python3 make_doc.py\necho ok"}, "正在执行：python3 make_doc.py"),
        ("bash", {"command": "ls -la /workspace /workspace/outputs"}, "正在执行：ls -la outputs"),
        ("web_search", {"query": "课后服务 政策"}, "正在检索：课后服务 政策"),
        ("kb_search", {"query": "观察与记录", "limit": 10}, "正在查材料：观察与记录"),
        ("web_fetch", {"url": "https://www.moe.gov.cn/a/b.html"}, "正在阅读网页：moe.gov.cn"),
        ("generate_html_document", {"title": "家长指引", "body": "<p/>"}, "正在写网页：家长指引"),
        ("sandbox_document_open", {"filename": "教案.docx"}, "正在打开文档：教案.docx"),
        ("memory_write", {"content": "x"}, "正在记进记忆"),
        ("workspace_read_file", {"artifact_id": "a1"}, "正在读文件"),
        ("bash", {}, "正在调工具"),
        ("write", None, "正在调工具"),
        ("", {}, ""),
    ],
)
def test_call_step_line(tool: str, args: dict[str, Any] | None, line: str) -> None:
    assert workbench_call_step_line(tool, args) == line


def test_long_detail_is_cut() -> None:
    line = workbench_call_step_line("web_search", {"query": "字" * 80})
    assert line.endswith("…")
    assert len(line.split("：", 1)[1]) == 40


def test_tool_call_event_carries_the_named_line() -> None:
    out: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        out.append((kind, payload))

    raw = {
        "type": "tool_execution_start",
        "toolName": "read",
        "toolCallId": "c1",
        "args": {"path": "/workspace/attachments/秋天的雨.docx"},
    }
    asyncio.run(map_event(RpcEvent(raw), emit=emit, state=EventMapState()))
    calls = [p for k, p in out if k == "tool.call"]
    assert calls and calls[0]["step_line"] == "正在读 秋天的雨.docx"
