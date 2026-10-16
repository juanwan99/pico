"""HDS2: final_text human package hard gate.

pico#1320: sanitize_user_facing_text no longer strips jargon / process chrome /
self-check / English monologue lines, and no longer force-injects a filename
card when the model's own words don't mention the title. It only strips pasted
HTML documents, model-identity claims, ANSI and the plan-mode passphrase; an
empty cleaned reply with artifact titles still gets a plain download card.
"""

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
    assert "<html" not in out.lower()
    assert "artifact_id" not in out.lower()


def test_fenced_html_stripped() -> None:
    raw = "见代码：\n```html\n<html><body><button>x</button></body></html>\n```\n"
    out = sanitize_user_facing_text(raw, artifact_titles=["x.html"])
    assert "```html" not in out
    assert "<html" not in out.lower()


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
            ("sandbox_pptx_lib", {"title": "上限.pptx", "artifact_id": "4"}),
        ]
    )
    assert titles == ["a.html", "b.md", "上限.pptx"]


def test_titles_hide_sidecar_images_when_office_file_exists() -> None:
    titles = titles_from_tool_results(
        [
            ("generate_image", {"title": "决策会封面图.jpg", "artifact_id": "img-1"}),
            ("generate_diagram", {"title": "传导图.png", "artifact_id": "img-2"}),
            ("generate_pptx_document", {"title": "办公尺752.pptx", "artifact_id": "deck-1"}),
        ]
    )
    assert titles == ["办公尺752.pptx"]
    images_only = titles_from_tool_results(
        [
            ("generate_image", {"title": "示意图.jpg", "artifact_id": "img-1"}),
        ]
    )
    assert images_only == ["示意图.jpg"]


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
    """Only a reply that cleans to nothing gets the plain download card (pico#1320)."""
    out = sanitize_user_facing_text("", artifact_titles=["lost-found.html"])
    assert "lost-found.html" in out
    assert "下载" in out


def test_preserves_human_filename_and_clarification() -> None:
    """Clarifications pass through untouched; the model's own words stand (pico#1320)."""
    clarify = "请问需要几个栏目？主色是蓝还是绿？"
    out = sanitize_user_facing_text(clarify, artifact_titles=[])
    assert "栏目" in out
    assert "主色" in out

    named = sanitize_user_facing_text(
        "已准备好失物招领板，文件名见下：失物招领板.html",
        artifact_titles=["失物招领板.html"],
    )
    assert "失物招领板.html" in named


def test_strips_backend_model_self_id_keeps_pico() -> None:
    out = sanitize_user_facing_text("我是 DeepSeek 开发的助手，可以帮你改这份表。", artifact_titles=[])
    assert "DeepSeek" not in out
    assert "Pico" in out
    assert "开发的助手" not in out
    assert "改这份表" in out
    out_en = sanitize_user_facing_text("I am GPT-5.6 and I can help.", artifact_titles=[])
    assert "GPT" not in out_en
    assert "Pico" in out_en
    assert "can help" in out_en
    news = sanitize_user_facing_text("今天 DeepSeek 发布了新模型。", artifact_titles=[])
    assert "DeepSeek" in news
