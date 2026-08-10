"""T-PACK-P4-CAPABILITY-EXCEL: W2 content-pipeline + O1 office-chain min truth.

Locks P4 S3 root causes (natural phrasing broke heuristics → min over-inflated
→ false failure):
- W2: 「做一篇…」 creative single-piece prompts must be single-unit even with
  numbered tutorial steps (①…⑥) and the word 流水线 as the method name.
- O1: an explicit stated floor 「至少 N 个真文件」 must be respected as the
  min (not overridden by structure enumeration), so N..N+k real files pass.
- Explicit multi-file language must still force multi (unchanged).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def test_w2_content_pipeline_single_piece_not_multi_minned() -> None:
    """RC: 做一篇/写一首 + numbered tutorial steps + 流水线-as-method = ONE piece."""
    from pico_orchestrator.delivery_policy import analyze_delivery

    prompts = [
        (
            "请按内容流水线做一篇悬疑短篇：①流水线（扫榜→拆前三章→设定→正文）；"
            "②拆标杆开局钩子/核心设定/节奏/章末钩子（骨架表）；③给出设定；"
            "④写正文第一章（至少800字，非大纲）；⑤去AI味检查（模板句/感官/节奏）；"
            "⑥同会话续写一段。工具落盘。"
        ),
        (
            "请按内容流水线写一首主题歌：①流水线；②拆标杆钩子/副歌记忆点；"
            "③设定；④写主歌+副歌；⑤去AI味检查；⑥同会话续写。工具落盘。"
        ),
        (
            "请按内容流水线做一篇短篇科幻小说：①先给流水线（扫榜→选标杆→"
            "拆前三章→设定候选→正文）；②拆一个标杆的开局钩子/核心设定/节奏/"
            "章末钩子（骨架表）；③给出选定设定；④写正文第一章（至少800字，非大纲）；"
            "⑤做去AI味检查（模板句/感官/节奏）；⑥同会话续写一段。工具落盘交付文档。"
        ),
    ]
    for prompt in prompts:
        plan = analyze_delivery(prompt)
        assert plan.min_artifacts <= 2, prompt
        assert plan.multi_deliverable is False, prompt


def test_o1_office_chain_respects_stated_min_floor() -> None:
    """RC: 「至少 N 个真文件」 must cap min at N (not structure-inflated)."""
    from pico_orchestrator.delivery_policy import analyze_delivery

    plan = analyze_delivery(
        "请为\"年度合作伙伴答谢晚宴\"做一套材料：主议程、嘉宾名单、后勤保障单"
        "（至少 3 个真文件，可下载），内容相互咬合一致。工具落盘。"
    )
    assert plan.min_artifacts == 3, plan.min_artifacts

    plan2 = analyze_delivery(
        "请为\"新品发布会\"做一套完整材料：议程表、嘉宾/环节清单、会务后勤单"
        "（至少 3 个真文件，可下载），内容相互咬合一致。完成后用人话说明。"
    )
    assert plan2.min_artifacts == 3, plan2.min_artifacts


def test_explicit_multi_file_still_forced() -> None:
    """假绿 guard: 分别交付 N 个独立文件 still forces multi (gate not closed)."""
    from pico_orchestrator.delivery_policy import analyze_delivery

    assert analyze_delivery("请分别交付 3 个独立 HTML 文件：A.html B.html C.html。").min_artifacts >= 3
    assert analyze_delivery("请交付 4 个独立可下载文件：甲.md 乙.md 丙.md 丁.md。").min_artifacts == 4


def test_single_piece_with_landing_intent_requires_one_file() -> None:
    """假绿 guard: 单件创作题带「工具落盘」必须 min=1，防聊天-only 冒充交付。

    W2-R2B 曾以 min=0 让「纯聊天回复摘要」succeeded（0 真文件）——W2 正文/续写
    必须可下载，聊天复述不能算交付。
    """
    from pico_orchestrator.delivery_policy import analyze_delivery

    plan = analyze_delivery(
        "请按内容流水线做一篇悬疑短篇：①流水线；②拆标杆；③设定；"
        "④写正文第一章（至少800字）；⑤去AI味检查；⑥同会话续写一段。工具落盘。"
    )
    assert plan.min_artifacts >= 1, plan.min_artifacts
    assert plan.multi_deliverable is False

    # 纯闲聊（无交付/落盘意图）仍不强制 agent、不需要文件。
    casual = analyze_delivery("你是什么模型")
    assert casual.force_agent is False
    assert casual.min_artifacts == 0
