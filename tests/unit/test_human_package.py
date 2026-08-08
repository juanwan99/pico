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
