"""Delivery policy — structural + session heuristics; no exam-phrase overfit."""

from __future__ import annotations

from pico_orchestrator.delivery_policy import (
    ENGINEERING_SKILL_ID,
    REMOVED_OVERFIT_PHRASES,
    analyze_delivery,
    count_user_artifacts,
    normalize_artifact_title,
)


def test_d0_removed_overfit_phrases_not_in_source() -> None:
    """D0: deleted exam-isomorphic phrases must not appear as dedicated triggers."""
    import inspect

    from pico_orchestrator import delivery_policy as mod

    # Pattern objects only (not REMOVED_* audit tuple / comments).
    pattern_blobs = []
    for name in (
        "_MULTI_PHRASE",
        "_IMPLICIT_PACKAGE",
        "_PIPELINE_PHRASE",
        "_REVISION_PHRASE",
        "_CHANGE_OF_MIND",
        "_RUNNABLE_MEDIA",
        "_HTML_SURFACE",
    ):
        pattern_blobs.append(getattr(mod, name).pattern)
    joined = "\n".join(pattern_blobs)
    for banned in ("只做低成本", "别的顺延", "番茄钟", "广播稿"):
        assert banned not in joined, banned
    # E3: sample-face domain filters must not live as dedicated regex tokens
    # in the parallel-list cleaner source body (grammar filters only).
    cleaner_src = inspect.getsource(mod._count_parallel_list_items)
    for banned in ("日记页", "知识页", "小测验", "分页", "测验"):
        assert banned not in cleaner_src, banned
        assert banned in REMOVED_OVERFIT_PHRASES
    assert "_DELIVERABLE_NOUN" not in dir(mod)
    assert "只做低成本" in REMOVED_OVERFIT_PHRASES
    assert "番茄钟" in REMOVED_OVERFIT_PHRASES
    assert inspect.isfunction(mod.analyze_delivery)


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
    assert plan.structure_item_count >= 3


def test_pipeline_stages_generic() -> None:
    prompt = (
        "做观察流水线，每阶段独立文件：\n"
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


def test_revision_with_prior_artifacts_change_of_mind() -> None:
    """D2: isomorphic soft revision without exam phrases; binds prior artifacts."""
    plan = analyze_delivery(
        "上次推荐太激进了，改成保守方案，只保留零成本动作。请更新决策文件。",
        prior_artifact_titles=["现状摘要.md", "选项对比.md", "推荐决策.md"],
    )
    assert plan.revision is True
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1
    assert plan.prior_artifact_count >= 3
    assert "会话改口" in plan.instruction or "修订" in plan.instruction


def test_revision_change_mind_without_prior_still_if_mentions_file() -> None:
    plan = analyze_delivery(
        "推翻上次结论，收窄成只保留两项，更新推荐决策文件。"
    )
    assert plan.revision is True
    assert plan.force_agent is True


def test_exam_soft_phrase_alone_not_required() -> None:
    """X-PHRASE: old P1 soft phrases must not be the only green path."""
    # Without prior + without generic change-of-mind / file mention structure,
    # pure exam leftover should not be specially handled (those phrases deleted).
    plan = analyze_delivery("别的顺延吧")
    # May or may not force — must NOT specially key on 顺延 alone as revision.
    # 顺延 alone is not in CHANGE_OF_MIND; expect no force.
    assert plan.force_agent is False
    assert plan.revision is False


def test_casual_rewrite_not_forced_to_files() -> None:
    plan = analyze_delivery("把刚才的回答改成更短一点，语气友好一些。")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0


def test_runnable_html_media_only() -> None:
    """D3: HTML media words fire; no app-name dependency."""
    plan = analyze_delivery(
        "生成单页 HTML：简易待办列表，本地 file 打开可用，开始添加/勾选。请自检。"
    )
    assert plan.runnable_html is True
    assert plan.force_agent is True
    assert plan.min_artifacts >= 1
    assert plan.multi_deliverable is False


def test_single_html_courseware_not_multi_file() -> None:
    """G1: content sections of one HTML must not force multi-file fail-closed."""
    plan = analyze_delivery(
        "请生成一份可离线互动 HTML 课件：潮汐与月相观察日记（入门），"
        "3 页知识+日记页+小测验，浏览器本地打开可用。"
    )
    assert plan.runnable_html is True
    assert plan.multi_deliverable is False
    assert plan.min_artifacts == 1
    assert plan.force_agent is True


def test_single_unit_new_surface_not_multi() -> None:
    """E3: new prompt surface (no sample-face 日记页/小测验) stays single-file."""
    plan = analyze_delivery(
        "请生成一份可离线互动 HTML：城市骑行安全入门，"
        "含三段图文与自测题，浏览器本地打开可用。"
    )
    assert plan.runnable_html is True
    assert plan.multi_deliverable is False
    assert plan.min_artifacts == 1
    assert plan.force_agent is True


def test_office_markdown_long_material_single_file() -> None:
    """O1: long office material → one Markdown file, not multi fail-closed."""
    plan = analyze_delivery(
        "根据以下材料，请整理成一份可下载的「客户拜访纪要」Markdown 文件"
        "（单文件即可，visit-notes.md）。历史文档格式杂（pdf/docx/截图）。"
        "请输出结构化纪要。"
    )
    assert plan.multi_deliverable is False
    assert plan.min_artifacts == 1
    assert plan.force_agent is True


def test_same_session_revision_not_multi_from_change_list() -> None:
    """O2: 改一版 + 改成…并新增… is one-file revision, not two deliverables."""
    plan = analyze_delivery(
        "请在同一会话里改一版：把行动项里「3 个工作日内发试点方案」改成「5 个工作日内」，"
        "并新增一条「客户法务条款对齐」由我方法务跟进；输出更新版 Markdown"
        "（visit-notes-v2.md），文件须可再下载打开。",
        prior_artifact_titles=["visit-notes.md"],
    )
    assert plan.revision is True
    assert plan.multi_deliverable is False
    assert plan.min_artifacts == 1


def test_single_html_features_with_he_not_multi() -> None:
    """G1: 「含分页和测验」is one document's features, not two files."""
    plan = analyze_delivery("写一个 HTML 互动页，含分页和测验，本地打开可用")
    assert plan.runnable_html is True
    assert plan.multi_deliverable is False
    assert plan.min_artifacts == 1


def test_explicit_multi_still_forces_min() -> None:
    """G1: true multi intent still requires ≥2 files."""
    plan = analyze_delivery(
        "请分别交付两个独立文件：A 规格说明、B 验收清单。禁止合并成一个文件。"
    )
    assert plan.multi_deliverable is True
    assert plan.min_artifacts >= 2


def test_runnable_not_require_app_name() -> None:
    sticky = analyze_delivery("请做一个会议倒计时说明文档，纯文字即可")
    assert sticky.runnable_html is False
    assert sticky.force_agent is False


def test_short_chat_not_forced() -> None:
    plan = analyze_delivery("你是什么模型")
    assert plan.force_agent is False
    assert plan.min_artifacts == 0
    assert plan.multi_deliverable is False


def test_structure_enumeration_new_domain() -> None:
    """D1: same structure, different domain nouns → multi via structure count."""
    plan = analyze_delivery(
        "请准备一套「开源社区双月会」物料：议程、贡献者指南、会议主持卡、会后纪要模板。"
        "按完整会议需要自行拆成多份独立可下载文件，不必问我要几个文件。"
    )
    assert plan.multi_deliverable is True
    assert plan.implicit_package is True
    assert plan.structure_item_count >= 4
    assert plan.min_artifacts >= 4
    assert plan.force_agent is True


def test_structure_enumeration_without_package_word() -> None:
    """Parallel list alone can lift multi when ≥2 structural siblings."""
    plan = analyze_delivery(
        "请交付：议程草案、发言人须知、直播检查单。分别写成独立文件。"
    )
    assert plan.multi_deliverable is True
    assert plan.min_artifacts >= 2


def test_no_exam_keyword_required_for_multi() -> None:
    plan = analyze_delivery(
        "请分别交付两个独立文件：A 规格说明、B 验收清单。禁止合并成一个文件。"
    )
    assert plan.multi_deliverable is True
    assert plan.min_artifacts >= 2


def test_implicit_package_neutral_corpus_suite() -> None:
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


def test_pipeline_arrow_chain_three_stages() -> None:
    plan = analyze_delivery(
        "先做三阶段文件：现状摘要 → 选项对比 → 推荐决策。每阶段独立文件。"
    )
    assert plan.pipeline is True or plan.min_artifacts >= 3
    assert plan.force_agent is True
    assert plan.min_artifacts >= 3


def test_meta_phase_label_not_pipeline() -> None:
    """Bare「阶段一…」meta prefix must not inflate min_artifacts / fail-close chat."""
    plan = analyze_delivery(
        "【阶段一验收·当场新题】随便聊聊：你能用一句话说适合处理哪类办公杂事吗？不要生成文件。"
    )
    assert plan.pipeline is False
    assert plan.multi_deliverable is False
    assert plan.min_artifacts == 0
    assert plan.force_agent is False


def test_single_office_markdown_not_multi_from_sections() -> None:
    """One Markdown + content sections (顿号) stays single-unit; not multi min=3."""
    plan = analyze_delivery(
        "【阶段一验收】请做一份给创业团队的「客户拜访纪要」Markdown 单文件交付。"
        "文件名建议 visit-notes.md。内容含：拜访对象、讨论要点、承诺事项、下次跟进。"
        "只要这一份文件，不要拆成多文件。"
    )
    assert plan.multi_deliverable is False
    assert plan.pipeline is False
    assert plan.min_artifacts == 1
    assert plan.force_agent is True


def test_true_numbered_pipeline_stages_still_multi() -> None:
    plan = analyze_delivery(
        "做观察流水线，每阶段独立文件：\n"
        "阶段1 信息源清单 → 阶段2 三条洞察 → 阶段3 一页行动建议。"
    )
    assert plan.pipeline is True
    assert plan.min_artifacts >= 3


def test_normalize_extension_typo_mdd() -> None:
    """D4: .mdd → .md."""
    fixed, note = normalize_artifact_title("阶段3_本周行动_v2.mdd")
    assert fixed.endswith(".md")
    assert note is not None
    assert ".mdd" in note


def test_count_user_artifacts_skips_bookkeeping() -> None:
    rows = [
        ("file", "回复摘要", 10),
        ("file", "rules.md", 100),
        ("file", "schedule.md", 100),
        ("file", "rules.md", 100),
        ("table", "工具产物", 50),
    ]
    assert count_user_artifacts(rows) == 2


def test_engineering_skill_id_stable() -> None:
    assert ENGINEERING_SKILL_ID == "skill-engineering-delivery"
