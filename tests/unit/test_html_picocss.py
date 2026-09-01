"""T-HTML-PICO-CSS: vendored @picocss/pico classless is inlined, no CDN."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.document_generators import (
    PICO_CSS_ATTR,
    build_html_document,
    picocss_classless_text,
)


def test_vendor_file_is_classless_not_cdn() -> None:
    css = picocss_classless_text()
    assert "--pico-font-family" in css
    assert "jsdelivr" not in css.lower()
    assert "cdn." not in css.lower()
    version = (
        ROOT
        / "services/orchestrator/pico_orchestrator/agent_assets/vendor/picocss/VERSION"
    ).read_text(encoding="utf-8").strip()
    assert version == "2.1.1"


def test_prose_shell_uses_picocss_not_six_line_system_ui() -> None:
    text = build_html_document(title="note.html", marker="CSS1", body="一段说明。").decode(
        "utf-8"
    )
    assert PICO_CSS_ATTR in text
    assert "--pico-font-family" in text
    assert "max-width: 48rem" not in text
    assert "jsdelivr" not in text.lower()
    assert text.count(PICO_CSS_ATTR) == 1


def test_fragment_shell_uses_picocss() -> None:
    text = build_html_document(
        title="frag.html",
        marker="CSS2",
        body="<main><article><h2>题</h2><p>正文</p></article></main>",
    ).decode("utf-8")
    assert PICO_CSS_ATTR in text
    assert "<article>" in text
    assert "--pico-font-family" in text


def test_full_document_keeps_later_model_style() -> None:
    body = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><title>t</title>
<style>.hero{color:hotpink}</style>
</head>
<body>
  <header><h1>封面</h1></header>
  <main><p>内容</p></main>
</body></html>"""
    text = build_html_document(title="full.html", marker="CSS3", body=body).decode(
        "utf-8"
    )
    assert PICO_CSS_ATTR in text
    assert ".hero{color:hotpink}" in text
    assert text.index(PICO_CSS_ATTR) < text.index(".hero{color:hotpink}")
    assert "jsdelivr" not in text.lower()
    assert "cdn.jsdelivr" not in text


def test_system_and_gateway_say_semantic_base_not_library_identity() -> None:
    system = (
        ROOT / "services/orchestrator/pico_orchestrator/agent_assets/system.md"
    ).read_text(encoding="utf-8")
    ts = (
        ROOT / "services/true_pi_bridge/pico-gateway-tools.ts"
    ).read_text(encoding="utf-8")
    assert "semantic classless visual base" in system
    assert "semantic classless visual base" in ts
    assert "Do not name the stylesheet" in system
    assert "Do not name the stylesheet" in ts
    assert "picocss.com" not in system
    assert "picocss.com" not in ts
