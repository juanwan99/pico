"""Render one mermaid diagram in isolated Chromium.

Upstream: official mermaid UMD + Playwright. Pico does not layout graphs.
"""

from __future__ import annotations

import base64
import logging
import os
import re
from pathlib import Path
from typing import Any

from pico_orchestrator.gateway import ToolError

from sandbox_worker.browser import PNG_MAGIC, _ensure_browser
from sandbox_worker.mermaid_pin import DEFAULT_MERMAID_PATH, MERMAID_VERSION

MAX_SOURCE_CHARS = 32_000
RENDER_TIMEOUT_MS = 20_000
MAX_SVG_RETURN = 120_000
logger = logging.getLogger(__name__)
_FENCE = re.compile(
    r"^\s*```(?:mermaid|d2)?[ \t]*\n(.*)\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def mermaid_js_path() -> Path | None:
    env = (os.environ.get("PICO_MERMAID_JS_PATH") or "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(DEFAULT_MERMAID_PATH))
    candidates.append(Path(__file__).resolve().parent / "vendor" / "mermaid.min.js")
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 10_000:
                return path
        except OSError:
            continue
    return None


def mermaid_js_ready() -> bool:
    return mermaid_js_path() is not None


def strip_diagram_fences(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    matched = _FENCE.match(text)
    if matched:
        return matched.group(1).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def normalize_kind(raw: str | None) -> str:
    kind = (raw or "mermaid").strip().lower() or "mermaid"
    if kind == "mermaid":
        return kind
    if kind == "d2":
        raise ToolError(
            "diagram.unsupported",
            "这一档只支持 mermaid。D2 还没接，不能假装画出结构图。",
        )
    raise ToolError(
        "diagram.unsupported",
        f"不认识的结构图类型 {kind}。这一档只支持 mermaid，不能假装画出结构图。",
    )


def normalize_source(raw: str, *, kind: str = "mermaid") -> str:
    normalize_kind(kind)
    source = strip_diagram_fences(raw)
    if not source:
        raise ToolError(
            "tool.invalid_arguments",
            "结构图源码是空的。请给出 mermaid 文本，不能假装画出结构图。",
        )
    if len(source) > MAX_SOURCE_CHARS:
        raise ToolError(
            "tool.invalid_arguments",
            f"结构图源码超过 {MAX_SOURCE_CHARS} 字。请拆短后再画，不能假装画出结构图。",
        )
    return source


def _require_mermaid_js() -> Path:
    path = mermaid_js_path()
    if path is None:
        raise ToolError(
            "diagram.missing_engine",
            "沙箱还没装 mermaid 渲染库，结构图画不出来。请管理员重部 pico-sandbox 后再试。",
        )
    return path


async def render_diagram(*, source: str, kind: str = "mermaid") -> dict[str, Any]:
    """Return png_base64 + optional svg. Never invent pixels."""
    kind = normalize_kind(kind)
    text = normalize_source(source, kind=kind)
    js_path = _require_mermaid_js()
    browser = await _ensure_browser()
    context = await browser.new_context(
        viewport={"width": 1600, "height": 1200},
        java_script_enabled=True,
    )
    page = context.pages[0] if context.pages else await context.new_page()
    page.set_default_timeout(RENDER_TIMEOUT_MS)
    try:
        await page.set_content(
            (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<style>html,body{margin:0;background:#fff;}"
                "#diagram{display:inline-block;padding:16px;}</style>"
                "</head><body><div id='diagram'></div></body></html>"
            ),
            wait_until="domcontentloaded",
        )
        await page.add_script_tag(path=str(js_path))
        outcome = await page.evaluate(
            """async (payload) => {
                const source = payload.source;
                const font = 'WenQuanYi Zen Hei, Noto Sans CJK SC, sans-serif';
                try {
                    if (typeof mermaid === 'undefined') {
                        return { ok: false, error: 'mermaid_global_missing' };
                    }
                    mermaid.initialize({
                        startOnLoad: false,
                        securityLevel: 'strict',
                        theme: 'neutral',
                        fontFamily: font,
                    });
                    const rendered = await mermaid.render('pico-diagram', source);
                    const svg = rendered && rendered.svg ? String(rendered.svg) : '';
                    if (!svg.includes('<svg')) {
                        return { ok: false, error: 'empty_svg' };
                    }
                    document.getElementById('diagram').innerHTML = svg;
                    return { ok: true, svg };
                } catch (err) {
                    const message = err && err.message ? String(err.message) : String(err);
                    return { ok: false, error: message };
                }
            }""",
            {"source": text},
        )
        if not isinstance(outcome, dict) or not outcome.get("ok"):
            detail = ""
            if isinstance(outcome, dict):
                detail = str(outcome.get("error") or "").strip()
            raise ToolError(
                "diagram.parse",
                "这段结构图语法不对，我没画出来。"
                + (f"（{detail[:160]}）" if detail else ""),
            )
        svg = str(outcome.get("svg") or "")
        locator = page.locator("#diagram")
        png = bytes(await locator.screenshot(type="png"))
        if not png.startswith(PNG_MAGIC):
            raise ToolError(
                "diagram.invalid",
                "结构图截图不是可打开的 png，未保存，不能假装画出结构图。",
            )
        box = await locator.bounding_box()
        width = int((box or {}).get("width") or 0)
        height = int((box or {}).get("height") or 0)
        if width < 8 or height < 8:
            raise ToolError(
                "diagram.invalid",
                "结构图画面是空的，未保存，不能假装画出结构图。",
            )
        payload: dict[str, Any] = {
            "ok": True,
            "kind": kind,
            "engine": f"mermaid@{MERMAID_VERSION}",
            "png_base64": base64.b64encode(png).decode("ascii"),
            "width": width,
            "height": height,
        }
        if len(svg) <= MAX_SVG_RETURN:
            payload["svg"] = svg
        else:
            payload["svg_omitted"] = True
        return payload
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(
            "sandbox.unavailable",
            "隔离沙箱没能画出结构图。请稍后重试，不能假装画出来。",
        ) from exc
    finally:
        try:
            await context.close()
        except Exception:
            logger.debug("diagram chromium context close failed", exc_info=True)
