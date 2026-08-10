"""HDS2: final_text human package hard gate."""

from __future__ import annotations

from pico_orchestrator.human_package import (
    sanitize_user_facing_text,
    titles_from_tool_results,
)


def test_strips_full_html_when_artifact_exists() -> None:
    html = (
        "<!DOCTYPE html><html><head><title>x</title></head>"
        "<body><button>添加</button><script>1</script></body></html>"
    )
    out = sanitize_user_facing_text(
        f"如下是源码：\n{html}\n",
        artifact_titles=["todo-checklist.html"],
    )
    assert "<!DOCTYPE" not in out
    assert "<html" not in out.lower() or "html" in out.lower() and "<html" not in out
    assert "todo-checklist.html" in out
    assert "下载" in out
    assert "artifact_id" not in out.lower()


def test_strips_machine_jargon_lines() -> None:
    raw = (
        "课件做好了\n"
        "artifact_id: abc-123-uuid\n"
        "verification_level=L0_structure\n"
        "interaction_status=not_run\n"
        "L0_structure: pass\n"
        "请下载使用"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=["孟德尔遗传定律课件.html"])
    assert "artifact_id" not in out.lower()
    assert "verification_level" not in out.lower()
    assert "L0_structure" not in out
    assert "interaction_status" not in out.lower()
    assert "孟德尔遗传定律课件.html" in out or "课件" in out


def test_injects_filename_card_when_missing() -> None:
    out = sanitize_user_facing_text(
        "搞定了，请查收。",
        artifact_titles=["议程.md", "主持卡.md", "纪要模板.docx"],
    )
    assert "议程.md" in out
    assert "主持卡.md" in out
    assert "纪要模板.docx" in out
    assert "下载" in out


def test_chat_only_no_artifacts_unchanged_enough() -> None:
    raw = "我是 Pico，面向学校场景的 AI 助手。"
    out = sanitize_user_facing_text(raw, artifact_titles=[])
    assert "Pico" in out
    assert "下载" not in out


def test_titles_from_tool_results() -> None:
    titles = titles_from_tool_results(
        [
            ("generate_html_document", {"title": "a.html", "artifact_id": "1"}),
            ("verify_html_document", {"overall": "pass", "verification_level": "L0"}),
            ("workspace_write_file", {"title": "b.md", "artifact_id": "2"}),
            ("workspace_write_file", {"title": "回复摘要", "artifact_id": "3"}),
        ]
    )
    assert titles == ["a.html", "b.md"]


def test_fenced_html_stripped() -> None:
    raw = "见代码：\n```html\n<html><body><button>x</button></body></html>\n```\n"
    out = sanitize_user_facing_text(raw, artifact_titles=["x.html"])
    assert "```html" not in out
    assert "x.html" in out


def test_strips_tool_process_chrome_from_bubble() -> None:
    """G2: tool/process lines must not remain in user-facing package."""
    raw = (
        "〔调用工具 generate_html_document〕\n"
        "〔工具完成〕\n"
        "课件已就绪，请下载使用。\n"
        "artifact_id: should-go\n"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=["demo.html"])
    assert "调用工具" not in out
    assert "工具完成" not in out
    assert "artifact_id" not in out.lower()
    assert "demo.html" in out


def test_strips_tool_parameter_monologue() -> None:
    """M3: generate_*/JSON-escape diary must not remain in user bubble."""
    raw = (
        "Let me build the generate_html_document body parameter with JSON escape.\n"
        "I'll call workspace_write_file next after fixing the arguments.\n"
        "课件已写好，请下载打开。"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=["demo-board.html"])
    assert "generate_html_document" not in out
    assert "JSON escape" not in out
    assert "workspace_write" not in out.lower()
    assert "demo-board.html" in out
    assert "下载" in out


def test_looks_like_tool_monologue_detects_planning() -> None:
    from pico_orchestrator.human_package import looks_like_tool_monologue

    assert looks_like_tool_monologue(
        "Let me construct the tool parameters for generate_html_document"
    )
    assert looks_like_tool_monologue("调用工具 generate_html_document 并写入 body")
    assert not looks_like_tool_monologue("请问需要横版还是竖版布局？")


def test_clarification_questions_preserved() -> None:
    raw = (
        "为了做好失物招领板，请确认：\n"
        "1. 需要几个栏目？\n"
        "2. 主色是蓝还是绿？\n"
        "3. 是否需要搜索框？"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=[])
    assert "栏目" in out
    assert "主色" in out
    assert "搜索框" in out


def test_empty_sanitize_with_titles_yields_card() -> None:
    out = sanitize_user_facing_text(
        "generate_html_document body JSON escape workspace_write_file",
        artifact_titles=["lost-found.html"],
    )
    assert "lost-found.html" in out
    assert "generate_html" not in out


def test_strips_l0_selfcheck_wall_from_main_bubble() -> None:
    """#394 Y1: L0/structure self-check engineer wall must not remain in final_text."""
    raw = (
        "正在准备...\n"
        "HTML 已生成并落盘。由于系统侧对该产物做了二进制编码存储，"
        "静态自检无法直接读取其文本，但文件已正常写入账本、可下载。"
        "我如实说明：页面按标准完整 HTML 生成，含真实按钮与脚本，"
        "本地浏览器打开即可用；未经真机点击测试，不夸大其可用性。\n"
        "已生成文件：物业值班备忘板.html\n"
        "如何打开：在结果区点下载或打开。"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=["物业值班备忘板.html"])
    assert "L0" not in out
    assert "结构自检" not in out
    assert "静态自检" not in out
    assert "系统侧" not in out
    assert "二进制编码" not in out
    assert "账本" not in out
    assert "真机点击" not in out
    assert "不夸大" not in out
    assert "verification_level" not in out.lower()
    assert "物业值班备忘板.html" in out
    # Human how-to kept or re-injected via card
    assert "下载" in out or "打开" in out


def test_strips_system_side_verification_english() -> None:
    """#399 R3: English system-side verification voice must leave main bubble."""
    raw = (
        "正在准备...\n"
        "Now let me run the system-side verification check on the HTML."
        "课件已做好并完成结构校验，页面为完整可运行的 HTML。\n"
        "文件：孟德尔遗传定律_入门课件.html\n"
        "怎么打开：在结果区点下载。"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=["孟德尔遗传定律_入门课件.html"])
    assert "system-side" not in out.lower()
    assert "let me run" not in out.lower()
    assert "verification check" not in out.lower()
    assert "完成结构校验" not in out
    assert "孟德尔遗传定律_入门课件.html" in out
    assert "下载" in out or "打开" in out


def test_strips_ill_create_planning_prefix() -> None:
    """#399 R3: I'll create… planning glued to Chinese product copy."""
    raw = (
        "I'll create an interactive HTML quiz about photosynthesis."
        "小测已经做好了，文件是：光合作用入门-互动小测.html\n"
        "怎么打开：点下载。"
    )
    out = sanitize_user_facing_text(raw, artifact_titles=["光合作用入门-互动小测.html"])
    assert "I'll create" not in out
    assert "interactive HTML quiz" not in out
    assert "光合作用入门-互动小测.html" in out


def test_preserves_human_filename_and_clarification_not_l0() -> None:
    """Clarifications + human filenames survive; monologue/#375 posture unchanged."""
    clarify = "请问需要几个栏目？主色是蓝还是绿？"
    out = sanitize_user_facing_text(clarify, artifact_titles=[])
    assert "栏目" in out
    assert "主色" in out

    named = sanitize_user_facing_text(
        "已准备好失物招领板，文件名见下。",
        artifact_titles=["失物招领板.html"],
    )
    assert "失物招领板.html" in named
    assert "结构自检" not in named
