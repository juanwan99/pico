"""Facts about what a write/open tool just did.

Claude Code / Pi / OpenHands: tool result is an observation; the model
decides the next step. Not a rubric. Not a scene. No pass/fail.
"""

from __future__ import annotations

from typing import Any


def observe_write(
    *,
    kind: str,
    title: str,
    raw: bytes | str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra = extra or {}
    payload: bytes | None
    if isinstance(raw, str):
        payload = raw.encode("utf-8")
        text = raw
    elif isinstance(raw, (bytes, bytearray)):
        payload = bytes(raw)
        text = None
    else:
        payload = None
        text = None
    byte_size = extra.get("byte_size")
    if byte_size is None:
        byte_size = len(payload) if payload is not None else 0
    out: dict[str, Any] = {
        "kind": str(kind or "").strip() or "file",
        "title": str(title or "").strip(),
        "byte_size": int(byte_size or 0),
    }
    outline = _outline_for(str(kind or ""), payload, text)
    if outline:
        out["outline"] = outline
    return out


def _outline_for(
    kind: str, payload: bytes | None, text: str | None
) -> dict[str, Any] | None:
    low = kind.lower().lstrip(".")
    if low in {"pptx", "docx", "xlsx"} and payload:
        try:
            from pico_orchestrator.office.inspect import inspect_office_bytes

            return _compact_office(inspect_office_bytes(payload, f".{low}"))
        except (ValueError, TypeError, OSError, KeyError, ImportError):
            return {"unreadable": True}
    if low == "html":
        source = text
        if source is None and payload is not None:
            source = payload.decode("utf-8", errors="replace")
        if source is None:
            return None
        from pico_orchestrator.sandbox_s1 import extract_title_h1

        page_title, h1 = extract_title_h1(source)
        return {
            "title": page_title[:240],
            "h1": h1[:240],
            "chars": len(source),
        }
    if low in {"png", "jpg", "jpeg"} and payload:
        return {"format": low, "bytes": len(payload)}
    return None


def _compact_office(outline: dict[str, Any]) -> dict[str, Any]:
    kind = str(outline.get("kind") or "")
    if kind == "pptx":
        pages: list[dict[str, Any]] = []
        for unit in outline.get("units") or []:
            if not isinstance(unit, dict) or unit.get("kind") != "slide":
                continue
            bullets = unit.get("bullets") or []
            preview: list[str] = []
            if isinstance(bullets, list):
                for item in bullets[:3]:
                    text = str(item or "").strip()
                    if text:
                        preview.append(text[:80])
            page: dict[str, Any] = {
                "index": unit.get("index"),
                "title": unit.get("title"),
                "bullet_count": len(bullets) if isinstance(bullets, list) else 0,
                "images": unit.get("images") or 0,
            }
            if preview:
                page["preview"] = preview
            pages.append(page)
        compact = {
            "slides": outline.get("slides"),
            "images": outline.get("images"),
            "pages": pages,
        }
        if int(outline.get("images") or 0) <= 0:
            compact["hint"] = (
                "本份 PPT 未嵌入图片。要把已生成的图放进页内，"
                "用 spec.blocks[].image_artifact_id=图的 artifact id。"
                "body 里写 [image:…] 不会进页。"
            )
        return compact
    if kind == "docx":
        first = ""
        for unit in outline.get("units") or []:
            if isinstance(unit, dict) and unit.get("kind") in {"heading", "para"}:
                first = str(unit.get("text") or "").strip()[:160]
                if first:
                    break
        out = {
            "paragraphs": outline.get("paragraphs"),
            "tables": outline.get("tables"),
            "images": outline.get("images"),
        }
        if first:
            out["preview"] = first
        return out
    if kind == "xlsx":
        names: list[str] = []
        for unit in outline.get("units") or []:
            if isinstance(unit, dict) and unit.get("name"):
                names.append(str(unit.get("name"))[:80])
        out = {
            "sheets": outline.get("sheets"),
            "formulas": outline.get("formulas"),
        }
        if names:
            out["sheet_names"] = names[:12]
        return out
    return {"kind": kind}
