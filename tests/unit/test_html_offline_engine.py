"""#780 HTML offline engine: CDN/import fail-closed, CSP not glue-truncated."""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import title_protected_extension
from pico_orchestrator.document_generators import (
    HTML_INTERACTIVE_CSP,
    HTML_REMOTE_ENGINE_ERROR,
    build_html_document,
    html_engine_violations,
    html_remote_violations,
)
from pico_orchestrator.gateway import Principal, ToolError
from pico_orchestrator.tools_builtin import build_default_gateway


class _P:
    school_id = "s1"
    membership_id = "m1"
    scopes: ClassVar[list[str]] = ["ai:run"]


class _MemStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    async def write(
        self, principal: Principal, *, title: str, content: str | bytes, kind: str
    ) -> dict[str, Any]:
        aid = f"a-{len(self.items)+1}"
        body = content if isinstance(content, str) else content.decode("utf-8", "replace")
        self.items[aid] = {
            "artifact_id": aid,
            "title": title,
            "kind": kind,
            "content": body,
            "byte_size": len(body.encode("utf-8")),
        }
        return self.items[aid]

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        if artifact_id and artifact_id in self.items:
            return self.items[artifact_id]
        if title:
            for item in self.items.values():
                if item["title"] == title:
                    return item
        return None

    async def list(self, principal: Principal, *, limit: int) -> list[dict[str, Any]]:
        return list(self.items.values())[:limit]


def _csp_metas(html: str) -> list[str]:
    return re.findall(
        r"<meta[^>]*Content-Security-Policy[^>]*>", html, flags=re.IGNORECASE
    )


V1_IMPORT = """<!DOCTYPE html>
<html><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; base-uri 'none'; form-action 'none'; frame-ancestors 'none';" />
<title>rod</title>
</head><body>
<div id="scene"></div>
<script type="module">
  import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.161.0/build/three.module.js';
  import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.161.0/examples/jsm/controls/OrbitControls.js';
  document.getElementById('scene').appendChild(new THREE.WebGLRenderer().domElement);
</script>
</body></html>
"""

V3_CANVAS = """<!DOCTYPE html>
<html><head><title>rod-offline</title></head>
<body>
<button type="button" id="split">分裂演示</button>
<canvas id="c" width="320" height="200"></canvas>
<script>
  const c = document.getElementById('c');
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#38bdf8';
  ctx.fillRect(10, 10, 40, 40);
</script>
</body></html>
"""

GLUED_CSP_INLINE = """<!DOCTYPE html>
<html><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';'none'; img-src data:; script-src 'unsafe-inline' https://cdn.jsdelivr.net" />
<title>t</title></head>
<body>
<button type="button">ok</button>
<canvas id="c" width="40" height="40"></canvas>
<script>
  document.querySelector('button').onclick = function () {};
  document.getElementById('c').getContext('2d').fillRect(0,0,10,10);
</script>
</body></html>
"""


def test_three_import_fail_closed() -> None:
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="v1.html", marker="physics-rod-ball-3d-v1", body=V1_IMPORT)
    assert "es_import" in html_remote_violations(V1_IMPORT)


def test_script_src_chart_fail_closed() -> None:
    body = (
        "<!DOCTYPE html><html><body>"
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        "<canvas id='chart'></canvas></body></html>"
    )
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="chart.html", marker="CHART1", body=body)


def test_importmap_fail_closed() -> None:
    body = """<!DOCTYPE html><html><body>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three"}}</script>
<script type="module">import * as THREE from 'three';</script>
</body></html>"""
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="map.html", marker="MAP1", body=body)


def test_iframe_youtube_fail_closed() -> None:
    body = (
        '<!DOCTYPE html><html><body>'
        '<iframe src="https://www.youtube.com/embed/abc"></iframe>'
        "</body></html>"
    )
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="yt.html", marker="YT1", body=body)


def test_img_https_fail_closed() -> None:
    body = '<!DOCTYPE html><html><body><img src="https://example.com/a.png" alt="x"></body></html>'
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="img.html", marker="IMG1", body=body)


def test_fetch_https_fail_closed() -> None:
    body = (
        "<!DOCTYPE html><html><body><script>"
        "fetch('https://api.example.com/x')</script></body></html>"
    )
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="fetch.html", marker="F1", body=body)


def test_google_fonts_stripped_page_still_lands() -> None:
    body = """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">
</head><body>
<button type="button">ok</button>
<script>document.querySelector('button').onclick=function(){}</script>
</body></html>"""
    text = build_html_document(title="fonts.html", marker="FONT1", body=body).decode("utf-8")
    assert "fonts.googleapis.com" not in text
    assert "stripped remote stylesheet" in text
    assert "<button" in text.lower()
    assert ";'none'" not in text
    assert HTML_INTERACTIVE_CSP in text
    assert html_remote_violations(text) == ()


def test_inline_canvas_succeeds_and_csp_is_single_legal_policy() -> None:
    text = build_html_document(
        title="v3.html", marker="physics-rod-ball-animation-v3", body=V3_CANVAS
    ).decode("utf-8")
    assert "<canvas" in text.lower()
    assert "jsdelivr" not in text
    assert ";'none'" not in text
    metas = _csp_metas(text)
    assert len(metas) == 1
    assert HTML_INTERACTIVE_CSP in metas[0]
    assert "https://" not in metas[0]
    assert html_remote_violations(text) == ()


def test_glued_csp_replaced_not_truncated() -> None:
    text = build_html_document(
        title="glued.html", marker="GLUE1", body=GLUED_CSP_INLINE
    ).decode("utf-8")
    assert ";'none'" not in text
    assert "jsdelivr" not in text
    metas = _csp_metas(text)
    assert len(metas) == 1
    assert metas[0].count("script-src") == 1
    assert HTML_INTERACTIVE_CSP in metas[0]


def test_fragment_cdn_fail_closed() -> None:
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(
            title="frag.html",
            marker="FRAG1",
            body='<button>ok</button><script src="https://unpkg.com/three"></script>',
        )


def test_anchor_https_allowed() -> None:
    body = (
        "<!DOCTYPE html><html><body>"
        '<p>资料见 <a href="https://example.com/doc">链接</a></p>'
        "<button type='button'>ok</button>"
        "</body></html>"
    )
    text = build_html_document(title="a.html", marker="A1", body=body).decode("utf-8")
    assert "https://example.com/doc" in text
    assert html_remote_violations(text) == ()


def test_workspace_write_still_blocks_html() -> None:
    assert title_protected_extension("page.html") == ".html"


def test_generate_tool_rejects_cdn_and_accepts_canvas() -> None:
    store = _MemStore()
    gw = build_default_gateway(store)

    async def _cdn() -> None:
        await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "generate_html_document",
            {"title": "v1.html", "marker": "V1", "body": V1_IMPORT},
        )

    with pytest.raises(ToolError) as ei:
        asyncio.run(_cdn())
    assert ei.value.code == "tool.invalid_arguments"
    assert "外网资源" in ei.value.message

    async def _ok() -> dict[str, Any]:
        created = await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "generate_html_document",
            {"title": "v3.html", "marker": "V3", "body": V3_CANVAS},
        )
        verified = await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"artifact_id": created["artifact_id"]},
        )
        return {"created": created, "verified": verified}

    out = asyncio.run(_ok())
    assert out["created"]["kind"] == "html"
    assert out["verified"]["overall"] in {"pass", "partial"}
    names = {c["name"]: c for c in out["verified"]["checks"]}
    assert names["no_remote_script"]["status"] == "pass"


def test_verify_inline_import_fails_l0() -> None:
    gw = build_default_gateway(_MemStore())

    async def _run() -> dict[str, Any]:
        return await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"content": V1_IMPORT},
        )

    out = asyncio.run(_run())
    assert out["ok"] is False
    assert out["overall"] == "fail"
    names = {c["name"]: c for c in out["checks"]}
    assert names["no_remote_script"]["status"] == "fail"
    assert "es_import" in names["no_remote_script"]["detail"]


def test_error_constant_mentions_canvas() -> None:
    assert "canvas" in HTML_REMOTE_ENGINE_ERROR
    assert "Three.js" in HTML_REMOTE_ENGINE_ERROR
    assert "window.THREE" in HTML_REMOTE_ENGINE_ERROR


def test_protocol_relative_script_fail_closed() -> None:
    body = (
        "<!DOCTYPE html><html><body>"
        '<script src="//cdn.jsdelivr.net/npm/three@0.161.0/build/three.min.js"></script>'
        "<div id='scene'></div></body></html>"
    )
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="proto.html", marker="PR1", body=body)
    assert "script_src" in html_remote_violations(body)


def test_v2_three_global_without_cdn_fail_closed() -> None:
    body = """<!DOCTYPE html><html><body>
<div id="scene"></div>
<p id="status">已暂停</p>
<script>
  if (!window.THREE) {
    document.getElementById('status').textContent = 'Three.js加载失败';
  }
</script>
</body></html>"""
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="v2.html", marker="physics-rod-ball-3d-v2", body=body)
    assert "three_global" in html_engine_violations(body)


def test_bare_three_specifier_fail_closed() -> None:
    body = """<!DOCTYPE html><html><body>
<script type="module">import * as THREE from 'three';</script>
</body></html>"""
    with pytest.raises(ValueError, match="外网资源"):
        build_html_document(title="bare.html", marker="BARE1", body=body)
    assert "three_import" in html_engine_violations(body)


def test_canvas_only_fragment_not_escaped() -> None:
    body = '<canvas id="c" width="80" height="60"></canvas>'
    text = build_html_document(title="c.html", marker="CAN1", body=body).decode("utf-8")
    assert "<canvas" in text.lower()
    assert "&lt;canvas" not in text


def test_rod_ball_offline_fixture_lands_and_draws() -> None:
    fixture = (
        ROOT / "tests" / "fixtures" / "html" / "physics-rod-ball-offline.html"
    ).read_text(encoding="utf-8")
    text = build_html_document(
        title="轻杆小球运动与分裂.html",
        marker="physics-rod-ball-offline-v4",
        body=fixture,
    ).decode("utf-8")
    assert "<canvas" in text.lower()
    assert 'getContext("2d")' in text
    assert "分裂演示" in text
    assert "jsdelivr" not in text
    assert "window.THREE" not in text
    assert html_remote_violations(text) == ()
    assert html_engine_violations(text) == ()
    assert HTML_INTERACTIVE_CSP in text
    assert ";'none'" not in text


def test_verify_v2_three_global_fails_l0() -> None:
    gw = build_default_gateway(_MemStore())
    v2 = """<!DOCTYPE html><html><body>
<script>if (!window.THREE) {}</script>
</body></html>"""

    async def _run() -> dict[str, Any]:
        return await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"content": v2},
        )

    out = asyncio.run(_run())
    assert out["ok"] is False
    names = {c["name"]: c for c in out["checks"]}
    assert names["no_remote_script"]["status"] == "fail"
    assert "three_global" in names["no_remote_script"]["detail"]


def test_pi_visible_offline_html_words() -> None:
    sys_md = (
        ROOT
        / "services"
        / "orchestrator"
        / "pico_orchestrator"
        / "agent_assets"
        / "system.md"
    ).read_text(encoding="utf-8")
    ts = (
        ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts"
    ).read_text(encoding="utf-8")
    assert "no network" in sys_md
    assert "Three.js" in sys_md
    assert "window.THREE" in sys_md
    assert "课件" not in sys_md
    assert "run offline" in ts
    assert "fails closed" in ts
    assert "window.THREE" in ts


def test_public_and_preview_csp_still_deny_cdn() -> None:
    from pico_orchestrator.html_public import PUBLIC_CSP

    assert "jsdelivr" not in PUBLIC_CSP.lower()
    assert "script-src 'unsafe-inline'" in PUBLIC_CSP
    assert "https:" not in PUBLIC_CSP


def test_unbalanced_inline_script_fails_closed() -> None:
    from pico_orchestrator.document_generators import HTML_SCRIPT_SYNTAX_ERROR

    body = (
        "<!DOCTYPE html><html><head></head><body>"
        "<script>(function(){ var x = 1; })(); }</script>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="括号不配对"):
        build_html_document(title="lab.html", marker="js-bad", body=body)
    assert "括号不配对" in HTML_SCRIPT_SYNTAX_ERROR


def test_js_delimiters_skip_strings_and_comments() -> None:
    from pico_orchestrator.document_generators import js_delimiters_balanced

    assert js_delimiters_balanced("var x = '{'; /* } */") is True
    assert js_delimiters_balanced("var x = 1; }") is False
    assert js_delimiters_balanced("(function(){ var x = 1; })();") is True


def test_verify_unbalanced_inline_script_fails_l0() -> None:
    gw = build_default_gateway(_MemStore())
    body = (
        "<!DOCTYPE html><html><body>"
        "<button type='button'>go</button>"
        "<script>(function(){ var x = 1; })(); }</script>"
        "</body></html>"
    )

    async def _run() -> dict[str, Any]:
        return await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"content": body},
        )

    out = asyncio.run(_run())
    assert out["ok"] is False
    names = {c["name"]: c for c in out["checks"]}
    assert names["no_remote_script"]["status"] == "fail"
    assert "script_syntax" in names["no_remote_script"]["detail"]


def test_balanced_inline_script_still_lands() -> None:
    body = (
        "<!DOCTYPE html><html><head></head><body>"
        "<button id='go'>go</button>"
        "<script>(function(){ var x = 1; document.getElementById('go'); })();</script>"
        "</body></html>"
    )
    raw = build_html_document(title="lab.html", marker="js-ok", body=body)
    text = raw.decode("utf-8")
    assert "var x = 1" in text
    assert "js-ok" in text
