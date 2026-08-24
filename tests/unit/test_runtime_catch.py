"""T-RUNTIME-CATCH: Pi compact mapping, lane models, office-10 delivery gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import resolve_model_id, runtime_policy_for_model
from pico_orchestrator.true_pi.client import (
    RpcEvent,
    SubprocessTransport,
    official_compaction_settings,
)
from pico_orchestrator.true_pi.events import COMPACTION_HUMAN, EventMapState, map_event

# 10 office prompts: 改稿 / 纪要 / 多文件套件 / 可改一版. Empty success forbidden.
OFFICE_BENCH_10: list[tuple[str, int]] = [
    ("请把下面这段家长通知改成 Word 文档并下载。", 1),
    ("根据今天班主任会写一份会议纪要，交付可下载 docx。", 1),
    ("请分别交付 3 个独立可下载文件：通知.md、名单.csv、议程.docx。", 3),
    ("请把刚才的会议纪要改成 Word 文档并下载。", 1),
    ("生成一份教师培训课件 pptx，含三页提纲。", 1),
    ("请把课件第三页改成 Word 文档并下载。", 1),
    ("写一封可下载的家长会通知 HTML 网页。", 1),
    ("请把通知再改成 Word 文档并下载，不要只在对话里贴正文。", 1),
    ("交付全套材料包：课表.md 与说明.docx 两个独立文件。", 2),
    ("请把课表改成 Markdown 文件并下载。", 1),
]


def test_compaction_human_is_process_line() -> None:
    assert COMPACTION_HUMAN == "在整理上文"


@pytest.mark.asyncio
async def test_compaction_events_keep_search_sources() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "tool_execution_end",
                "toolName": "kb_search",
                "toolCallId": "c1",
                "result": {
                    "retrieved": True,
                    "honest_miss": False,
                    "sources": [{"title": "校历.md", "artifact_id": "art-1", "url": ""}],
                },
            }
        ),
        emit=emit,
        state=state,
    )
    await map_event(RpcEvent({"type": "compaction_start", "reason": "threshold"}), emit=emit, state=state)
    await map_event(RpcEvent({"type": "compaction_end", "reason": "threshold"}), emit=emit, state=state)
    kinds = [k for k, _ in events]
    assert "search.sources" in kinds
    assert "compaction.begin" in kinds
    assert "compaction.end" in kinds
    sources = next(p for k, p in events if k == "search.sources")
    assert sources["sources"][0]["artifact_id"] == "art-1"
    assert any(COMPACTION_HUMAN in str(p.get("text")) for k, p in events if k == "message.delta")


def test_prepare_agent_home_writes_official_compaction_settings(tmp_path: Path) -> None:
    t = SubprocessTransport(
        session_dir=tmp_path / "sess",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-compact",
        model="deepseek-v4-flash",
        thinking=False,
        spawn_cwd=tmp_path / "sess",
    )
    home = t.prepare_agent_home()
    agent_settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    project_settings = json.loads(
        (tmp_path / "sess" / ".pi" / "settings.json").read_text(encoding="utf-8")
    )
    for blob in (agent_settings, project_settings):
        compact = blob["compaction"]
        assert compact["enabled"] is True
        # Fast 128k lane: trigger at 56k used (128k - 72k). Short one-shot stays under.
        assert compact["keepRecentTokens"] == 16000
        assert compact["reserveTokens"] == 72000
        assert 128_000 - compact["reserveTokens"] == 56_000


def test_prepare_agent_home_deep_lane_compaction_fires_on_long_office(tmp_path: Path) -> None:
    t = SubprocessTransport(
        session_dir=tmp_path / "sess-deep",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-compact-deep",
        model="deepseek-reasoner",
        thinking=True,
        max_context=256_000,
        spawn_cwd=tmp_path / "sess-deep",
    )
    home = t.prepare_agent_home()
    compact = json.loads((home / "settings.json").read_text(encoding="utf-8"))["compaction"]
    assert compact["enabled"] is True
    assert compact["keepRecentTokens"] == 20000
    assert compact["reserveTokens"] == 192000
    trigger_at = 256_000 - compact["reserveTokens"]
    assert trigger_at == 64_000
    # One-shot office (~20k) stays quiet; multi-turn long run crosses 64k.
    assert trigger_at > 30_000
    # After compact, last turn + current files stay (not a collapsed window).
    assert compact["keepRecentTokens"] >= 16_000
    assert official_compaction_settings(256_000)["compaction"] == compact


def test_lane_models_flash_vs_reasoner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek-key-32chars-long")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    from pico_orchestrator.provider import ProviderConfig

    cfg = ProviderConfig(
        name="deepseek",
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-flash",
    )
    assert resolve_model_id("pico-fast", cfg) == "deepseek-v4-flash"
    assert resolve_model_id("pico-deep", cfg) == "deepseek-reasoner"
    assert runtime_policy_for_model("pico-fast")["backend_model"] == "deepseek-v4-flash"
    assert runtime_policy_for_model("pico-deep")["backend_model"] == "deepseek-reasoner"


def test_office_bench_10_routing_does_not_guess() -> None:
    from app.openai_compat import _this_round_delivery_plan

    assert len(OFFICE_BENCH_10) == 10
    for prompt, _need in OFFICE_BENCH_10:
        plan = _this_round_delivery_plan(prompt)
        assert plan.force_agent is False, prompt
        assert plan.min_artifacts == 0, (prompt, plan.min_artifacts)


def test_casual_chat_still_zero_artifacts() -> None:
    from app.openai_compat import _this_round_delivery_plan

    plan = _this_round_delivery_plan("你好，今天天气怎么样？")
    assert plan.min_artifacts == 0
    assert plan.force_agent is False
