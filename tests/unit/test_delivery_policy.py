"""General delivery policy — no exam-case keyword special-cases."""

from __future__ import annotations

from pico_orchestrator.delivery_policy import (
    ENGINEERING_SKILL_ID,
    analyze_delivery,
    count_user_artifacts,
)


def test_multi_deliverable_independent_files() -> None:
    prompt = (
        "请为「社区图书漂流」一次性交付三个独立可下载文件：\n"
        "1) 活动规则说明\n"
        "2) 志愿者排班表\n"
        "3) 给居民的通知短讯合集\n"
        "禁止合并成一个文件四个标题。"
    )
    plan = analyze_delivery(prompt)
    assert plan.multi_deliverable is True
    assert plan.min_artifacts >= 3
    assert plan.force_agent is True
    assert "独立" in plan.instruction or "多交付" in plan.instruction


def test_pipeline_stages_generic() -> None:
    prompt = (
        "做竞品周观察流水线，每阶段独立文件：\n"
        "阶段1 信息源清单 → 阶段2 三条洞察 → 阶段3 一页行动建议。"
    )
    plan = analyze_delivery(prompt)
    assert plan.pipeline is True
    assert plan.min_artifacts >= 3
    assert plan.force_agent is True


def test_revision_generic_not_exam_keyword() -> None:
    prompt = "把行动建议里优先级最高的改成下周再做，并更新对应文件。"
    plan = analyze_delivery(prompt)
    assert plan.revision is True
    assert plan.min_artifacts >= 1
    assert plan.force_agent is True


def test_casual_rewrite_not_forced_to_files() -> None:
    plan = analyze_delivery("把刚才的回答改成更短一点，语气友好一些。")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_runnable_html_self_check_intent() -> None:
    prompt = (
        "生成一个会议倒计时单页 HTML（本地可打开）："
        "输入会议名与时间。生成后请自检空提交。"
    )
    plan = analyze_delivery(prompt)
    assert plan.runnable_html is True
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1


def test_short_chat_not_forced() -> None:
    plan = analyze_delivery("你是什么模型")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0
    assert plan.multi_deliverable is False


def test_no_exam_keyword_required_for_multi() -> None:
    """Policy must fire on generic multi-file wording, not fixed scenario names."""
    plan = analyze_delivery(
        "请分别交付两个独立文件：A 规格说明、B 验收清单。禁止合并成一个文件。"
    )
    assert plan.multi_deliverable is True
    assert plan.min_artifacts >= 2


def test_count_user_artifacts_skips_bookkeeping() -> None:
    rows = [
        ("file", "回复摘要", 10),
        ("file", "rules.md", 100),
        ("file", "schedule.md", 100),
        ("file", "rules.md", 100),  # duplicate title
        ("table", "工具产物", 50),
    ]
    assert count_user_artifacts(rows) == 2


def test_engineering_skill_id_stable() -> None:
    assert ENGINEERING_SKILL_ID == "skill-engineering-delivery"
