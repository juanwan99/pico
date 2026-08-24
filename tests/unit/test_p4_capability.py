"""T-PACK-P4-CAPABILITY-EXCEL: routing does not guess min from phrasing.

W2 / O1 / explicit-multi prompts used to drive a word-list supervisor.
T-HARNESS-SLIM: routing min_arts is always 0; the live gate is claim vs disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.openai_compat import _this_round_delivery_plan


def test_w2_content_pipeline_routing_does_not_guess() -> None:
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
        plan = _this_round_delivery_plan(prompt)
        assert plan.min_artifacts == 0, prompt
        assert plan.force_agent is False, prompt
        assert plan.multi_deliverable is False, prompt


def test_o1_office_chain_routing_does_not_guess() -> None:
    plan = _this_round_delivery_plan(
        "请为\"年度合作伙伴答谢晚宴\"做一套材料：主议程、嘉宾名单、后勤保障单"
        "（至少 3 个真文件，可下载），内容相互咬合一致。工具落盘。"
    )
    assert plan.min_artifacts == 0
    assert plan.force_agent is False


def test_explicit_multi_file_routing_does_not_guess() -> None:
    plan = _this_round_delivery_plan(
        "请分别交付 3 个独立 HTML 文件：A.html B.html C.html。"
    )
    assert plan.min_artifacts == 0
    assert plan.force_agent is False
    plan2 = _this_round_delivery_plan(
        "请交付 4 个独立可下载文件：甲.md 乙.md 丙.md 丁.md。"
    )
    assert plan2.min_artifacts == 0
    assert plan2.force_agent is False


def test_single_piece_and_casual_routing_do_not_guess() -> None:
    plan = _this_round_delivery_plan(
        "请按内容流水线做一篇悬疑短篇：①流水线；②拆标杆；③设定；"
        "④写正文第一章（至少800字）；⑤去AI味检查；⑥同会话续写一段。工具落盘。"
    )
    assert plan.min_artifacts == 0
    assert plan.force_agent is False
    casual = _this_round_delivery_plan("你是什么模型")
    assert casual.force_agent is False
    assert casual.min_artifacts == 0
