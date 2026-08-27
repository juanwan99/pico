"""Thin client: mermaid source → sandbox Playwright PNG. No layout engine here."""

from __future__ import annotations

import base64
from typing import Any

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s2 import PNG_MAGIC
from pico_orchestrator.sandbox_sidecar import sidecar_json

# Re-export the same limits the sidecar enforces (fail before HTTP when possible).
MAX_SOURCE_CHARS = 32_000
DIAGRAM_TIMEOUT_S = 30.0
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _decode_png(raw_b64: str) -> bytes:
    try:
        raw = base64.b64decode(raw_b64.encode("ascii"), validate=False)
    except Exception as exc:
        raise ToolError(
            "diagram.invalid",
            "结构图结果不是可打开的 png，未保存，不能假装画出结构图。",
        ) from exc
    if not raw or len(raw) > _MAX_IMAGE_BYTES or not raw.startswith(PNG_MAGIC):
        raise ToolError(
            "diagram.invalid",
            "结构图结果不是可打开的 png，未保存，不能假装画出结构图。",
        )
    return raw


async def render_diagram_bytes(
    source: str,
    *,
    kind: str = "mermaid",
) -> tuple[bytes, str, dict[str, Any]]:
    """Return (png_bytes, svg_or_empty, meta). Fail closed — never invent pixels."""
    text = (source or "").strip()
    if not text:
        raise ToolError(
            "tool.invalid_arguments",
            "结构图源码是空的。请给出 mermaid 文本，不能假装画出结构图。",
        )
    if len(text) > MAX_SOURCE_CHARS:
        raise ToolError(
            "tool.invalid_arguments",
            f"结构图源码超过 {MAX_SOURCE_CHARS} 字。请拆短后再画，不能假装画出结构图。",
        )
    kind_name = (kind or "mermaid").strip().lower() or "mermaid"
    if kind_name == "d2":
        raise ToolError(
            "diagram.unsupported",
            "这一档只支持 mermaid。D2 还没接，不能假装画出结构图。",
        )
    if kind_name != "mermaid":
        raise ToolError(
            "diagram.unsupported",
            f"不认识的结构图类型 {kind_name}。这一档只支持 mermaid，不能假装画出结构图。",
        )
    out = await sidecar_json(
        "POST",
        "/v1/internal/diagram",
        json_body={"source": text, "kind": kind_name},
    )
    if not isinstance(out, dict):
        raise ToolError(
            "sandbox.unavailable",
            "隔离沙箱没能画出结构图。请稍后重试，不能假装画出来。",
        )
    png = _decode_png(str(out.get("png_base64") or ""))
    svg = out.get("svg")
    svg_text = svg if isinstance(svg, str) else ""
    meta = {
        "kind": str(out.get("kind") or kind_name),
        "engine": str(out.get("engine") or "mermaid"),
        "width": out.get("width"),
        "height": out.get("height"),
        "svg_omitted": bool(out.get("svg_omitted")),
    }
    return png, svg_text, meta
