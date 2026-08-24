"""T-PACK-P1-RELIABLE-LAND: new-session long chains land real files.

Locks the two P1 root causes:
- RC-1: Pico ledger markers (【Pico-User】【Pico-Convo】【权限】…) masked
  delivery intent in the routing prompt → misrouted to direct deepseek-chat.
  Fixed by marker-stripping BEFORE _resolve_skill_for_prompt (and in history).
- RC-2: _extract_file_artifacts only matched ASCII filenames, dropping
  Chinese-named file: code blocks → 0 real artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

MARKED = (
    "【Pico-User:6a7288292914888fa4aeb92e】 "
    "【Pico-Convo:pending_24f3eaba-7ee6-4fad-8897-d38190413a26】 "
    "【权限：默认沙箱】\n"
)
PROMPT = (
    "【P1S1-2】请把下面这段「季度复盘会议转写」一次做完一整条交付链："
    "①先写150字要点；②生成正式复盘文档（可下载Markdown，含成绩/不足/改进措施三节）；"
    "③提取整改清单（责任人+截止日+勾选框）；④写成可复制的执行通知文案。"
    "材料：本季度新签客户18家但续费率降到71%。"
    "请交付真实可下载文件（至少：复盘+整改清单）。"
)


def test_pico_markers_mask_delivery_intent_until_stripped() -> None:
    """RC-1: markers still stripped. T-GROK-PATH: no auto skill bind."""
    from app.openai_compat import _resolve_skill_for_prompt, _strip_pico_markers
    from pico_orchestrator.delivery_policy import analyze_delivery

    marked = analyze_delivery(MARKED + PROMPT)
    assert marked.force_agent is False
    assert marked.min_artifacts == 0

    clean = _strip_pico_markers(MARKED + PROMPT)
    assert "【Pico-User" not in clean
    assert "【权限" not in clean
    plan = analyze_delivery(clean)
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1

    skill, routed_plan = _resolve_skill_for_prompt(clean, None, history=None)
    assert skill is None
    # Markdown 复盘链 is not 做成 Word; post-run min stays 0 unless named Office/HTML.
    assert routed_plan.min_artifacts == 0
    assert routed_plan.force_agent is False


def test_extract_file_artifacts_chinese_filenames() -> None:
    """RC-2: file: code blocks with Chinese filenames become real artifacts."""
    from app.openai_compat import _extract_file_artifacts

    text = (
        "### 复盘\n"
        "```file:季度复盘会议纪要2025Q2.md\n"
        "# 季度复盘\n正文内容\n```\n"
        "### 清单\n"
        "```file:整改清单_2025Q3.md\n"
        "- [ ] 事项\n```\n"
    )
    files = _extract_file_artifacts(text)
    titles = [name for name, _ in files]
    assert "季度复盘会议纪要2025Q2.md" in titles
    assert "整改清单_2025Q3.md" in titles
    assert any("正文内容" in body for _, body in files)

    # ASCII names still work.
    assert _extract_file_artifacts("```file:meeting-2025Q2.md\nhi\n```") == [
        ("meeting-2025Q2.md", "hi")
    ]


def test_history_for_agent_strips_pico_markers() -> None:
    """RC-1 (sticky): history turns are cleaned so continuation intent binds too."""
    from types import SimpleNamespace

    from app.openai_compat import _history_for_agent

    def msg(role: str, content: str) -> SimpleNamespace:
        return SimpleNamespace(role=role, content=content)

    messages = [
        msg("user", MARKED + PROMPT),
        msg("assistant", "我确认一下需求，稍等。"),
        msg("user", MARKED + "继续，全部做。交付真实文件。"),
    ]
    history = _history_for_agent(messages)
    assert all("【Pico-User" not in h["content"] for h in history)
    assert all("【权限" not in h["content"] for h in history)
    assert history[0]["content"].startswith("【P1S1-2】")
