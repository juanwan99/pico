"""General delivery policy — no exam-case keyword special-cases."""

from __future__ import annotations

from pico_orchestrator.delivery_policy import (
    ENGINEERING_SKILL_ID,
    analyze_delivery,
    count_user_artifacts,
)


def test_multi_deliverable_independent_files() -> None:
    prompt = (
        "请为某社区活动一次性交付三个独立可下载文件：\n"
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


def test_soft_revision_without_file_keyword() -> None:
    """H5: soft change-of-mind still forces revision of prior stage outputs."""
    prompt = "算了，本周行动先只做低成本两项，别的顺延。请更新阶段3。"
    plan = analyze_delivery(prompt)
    assert plan.revision is True
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1
    assert "软改口" in plan.instruction or "修订" in plan.instruction


def test_soft_revision_priority_tweak() -> None:
    plan = analyze_delivery("优先级调一下：先做容易的，难的顺延，更新行动建议文件。")
    assert plan.revision is True
    assert plan.force_agent is True


def test_casual_rewrite_not_forced_to_files() -> None:
    plan = analyze_delivery("把刚才的回答改成更短一点，语气友好一些。")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_runnable_html_self_check_intent_neutral() -> None:
    """H2: must fire on neutral HTML wording — not sticky scene terms like 倒计时."""
    prompt = (
        "生成单页 HTML：简易「番茄钟」——开始/暂停/重置，本地 file 打开可用。"
        "请做自检并写明验证级别。"
    )
    plan = analyze_delivery(prompt)
    assert plan.runnable_html is True
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1
    assert "倒计时" not in plan.instruction


def test_runnable_not_require_countdown_keyword() -> None:
    """Regression guard: sticky scene word alone must not force runnable HTML (H2)."""
    sticky = analyze_delivery("请做一个会议倒计时说明文档，纯文字即可")
    # Without HTML/page surface, should not force runnable_html path.
    assert sticky.runnable_html is False
    assert sticky.force_agent is False


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


def test_implicit_package_no_n_files_said() -> None:
    """H1 core: package/kit wording without 'N independent files' → multi ≥2."""
    plan = analyze_delivery(
        "请做一套「校园义卖」筹备材料包：规则、摊位布局说明、志愿者须知、当日广播稿。"
        "直接交付可下载成品。不要问我要几个文件——按完整筹备需要自行拆成多份独立文件。"
    )
    assert plan.multi_deliverable is True
    assert plan.implicit_package is True
    assert plan.min_artifacts >= 2
    assert plan.force_agent is True
    assert "隐式包装" in plan.instruction or "多交付" in plan.instruction


def test_implicit_package_neutral_corpus_suite() -> None:
    """H1 unit: ≥3 neutral package phrases (no scenario exam names)."""
    samples = [
        "请交付完整方案包，含说明与清单。",
        "需要一整套材料：流程说明、注意事项、应急手册。",
        "给客户一份交付套件 full package，从调研到落地建议全套。",
    ]
    for s in samples:
        plan = analyze_delivery(s)
        assert plan.multi_deliverable is True, s
        assert plan.implicit_package is True, s
        assert plan.min_artifacts >= 2, s
        assert plan.force_agent is True, s


def test_explicit_multi_still_works_for_control() -> None:
    """P1-E control: explicit path must not regress (but cannot alone pass H1)."""
    plan = analyze_delivery(
        "请分别交付两个独立文件：A 名词解释十条；B 配套练习五题。禁止合并。"
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
