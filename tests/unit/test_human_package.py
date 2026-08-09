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
