"""pico.office.spec/v1 — validate / normalize. No rendering here."""

from __future__ import annotations

import json
import re
from typing import Any

SPEC_VERSION = "pico.office.spec/v1"
_DOCX_KINDS = frozenset({"docx"})
_PPTX_KINDS = frozenset({"pptx"})
_RESERVED_KINDS = frozenset({"xlsx"})
_DOCX_BLOCK_TYPES = frozenset({"heading", "para", "table", "image", "page_break"})
_PPTX_BLOCK_TYPES = frozenset({"slide"})

# Pipe table: header row + optional ---: separator + data rows.


class SpecError(ValueError):
    """Invalid office spec — fail closed, Chinese reason for the tool layer."""


def parse_spec(raw: Any) -> dict[str, Any]:
    """Accept dict or JSON string. Reject xlsx product surface (card 2)."""
    data = _as_dict(raw)
    version = str(data.get("version") or data.get("spec") or SPEC_VERSION).strip()
    if (
        version
        and version != SPEC_VERSION
        and not version.startswith("pico.office.spec/")
    ):
        raise SpecError(f"不认识的 spec 版本：{version}")
    kind = str(data.get("kind") or "").strip().lower()
    if kind in _RESERVED_KINDS:
        raise SpecError("Excel 产品面是卡 2，本卡不交 xlsx。请用 Word/PPT spec。")
    if kind not in _DOCX_KINDS | _PPTX_KINDS:
        raise SpecError("spec.kind 必须是 docx 或 pptx。")
    title = str(data.get("title") or "").strip()
    theme = _theme(data.get("theme"))
    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise SpecError("spec.blocks 不能为空。")
    normalized: list[dict[str, Any]] = []
    unsupported: list[str] = []
    for index, item in enumerate(blocks):
        if not isinstance(item, dict):
            raise SpecError(f"blocks[{index}] 必须是对象。")
        block, extra = _normalize_block(item, kind=kind, index=index)
        normalized.append(block)
        unsupported.extend(extra)
    if not _has_visible_content(normalized, kind=kind):
        raise SpecError("spec 没有可见正文（标题/段/表/页）。")
    out: dict[str, Any] = {
        "version": SPEC_VERSION,
        "kind": kind,
        "title": title,
        "theme": theme,
        "blocks": normalized,
    }
    marker = data.get("marker")
    if isinstance(marker, str) and marker.strip():
        out["marker"] = marker.strip()
    if unsupported:
        out["unsupported"] = unsupported
    return out


def spec_from_plain_body(
    *,
    kind: str,
    title: str,
    marker: str,
    body: str | None,
) -> dict[str, Any]:
    """Compile caller prose into v1 spec. Detect markdown tables in Word body."""
    kind = (kind or "").strip().lower()
    heading = (title or "").strip() or ("Pico DOCX" if kind == "docx" else "Pico PPTX")
    if kind == "docx":
        blocks: list[dict[str, Any]] = [
            {"type": "heading", "text": heading, "level": 0},
            {"type": "para", "text": f"标记：{marker}"},
        ]
        blocks.extend(_docx_blocks_from_body(body or ""))
        return parse_spec(
            {
                "version": SPEC_VERSION,
                "kind": "docx",
                "title": heading,
                "marker": marker,
                "blocks": blocks,
            }
        )
    if kind == "pptx":
        slides = _pptx_blocks_from_body(body or "", title=heading, marker=marker)
        return parse_spec(
            {
                "version": SPEC_VERSION,
                "kind": "pptx",
                "title": heading,
                "marker": marker,
                "blocks": slides,
            }
        )
    raise SpecError("spec.kind 必须是 docx 或 pptx。")


def attach_image_block(spec: dict[str, Any], *, artifact_id: str, alt: str = "") -> dict[str, Any]:
    """Append a generate_image artifact to the spec (Word end / last slide)."""
    aid = (artifact_id or "").strip()
    if not aid:
        raise SpecError("image artifact_id 不能为空。")
    data = parse_spec(spec)
    image = {"artifact_id": aid}
    if alt.strip():
        image["alt"] = alt.strip()
    if data["kind"] == "docx":
        data["blocks"].append({"type": "image", **image})
        return data
    slides = [b for b in data["blocks"] if b.get("type") == "slide"]
    if not slides:
        raise SpecError("PPT 没有页，不能插图。")
    slides[-1] = {**slides[-1], "image": image}
    data["blocks"] = slides
    return data


def _as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise SpecError("spec 不能为空。")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecError("spec 不是合法 JSON。") from exc
        if not isinstance(parsed, dict):
            raise SpecError("spec 必须是对象。")
        return parsed
    raise SpecError("spec 必须是对象或 JSON 字符串。")


def _theme(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("theme 必须是对象。")
    out: dict[str, str] = {}
    for key in ("heading_font", "body_font", "accent"):
        value = raw.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise SpecError(f"theme.{key} 必须是字符串。")
        out[key] = value.strip()
    return out


def _normalize_block(
    item: dict[str, Any], *, kind: str, index: int
) -> tuple[dict[str, Any], list[str]]:
    typ = str(item.get("type") or item.get("kind") or "").strip().lower()
    allowed = _DOCX_BLOCK_TYPES if kind == "docx" else _PPTX_BLOCK_TYPES
    if typ not in allowed:
        # Unknown field: keep teacher text as para, mark unsupported.
        text = str(item.get("text") or item.get("title") or "").strip()
        extra = [f"blocks[{index}].type={typ or 'missing'}"]
        if kind == "docx" and text:
            return {"type": "para", "text": text}, extra
        raise SpecError(f"blocks[{index}] 类型不支持：{typ or '空'}")
    if typ == "heading":
        text = str(item.get("text") or "").strip()
        if not text:
            raise SpecError(f"blocks[{index}] heading 不能为空。")
        level = item.get("level", 1)
        try:
            level_i = int(level)
        except (TypeError, ValueError) as exc:
            raise SpecError(f"blocks[{index}].level 必须是整数。") from exc
        return {"type": "heading", "text": text, "level": max(0, min(3, level_i))}, []
    if typ == "para":
        text = str(item.get("text") or "")
        if not str(text).strip():
            raise SpecError(f"blocks[{index}] para 不能为空。")
        return {"type": "para", "text": text}, []
    if typ == "table":
        headers = _str_row(item.get("headers"), allow_empty=True)
        rows_raw = item.get("rows")
        if not isinstance(rows_raw, list) or not rows_raw:
            raise SpecError(f"blocks[{index}] table.rows 不能为空。")
        rows = [_str_row(r, allow_empty=False) for r in rows_raw]
        width = len(headers) if headers else max(len(r) for r in rows)
        if width < 1:
            raise SpecError(f"blocks[{index}] 表没有列。")
        rows = [_pad_row(r, width) for r in rows]
        headers = _pad_row(headers, width) if headers else []
        out: dict[str, Any] = {"type": "table", "rows": rows}
        if headers:
            out["headers"] = headers
        caption = item.get("caption")
        if isinstance(caption, str) and caption.strip():
            out["caption"] = caption.strip()
        return out, []
    if typ == "image":
        return _image_ref(item, index=index), []
    if typ == "page_break":
        return {"type": "page_break"}, []
    if typ == "slide":
        title = str(item.get("title") or "").strip()
        if not title:
            raise SpecError(f"blocks[{index}] slide.title 不能为空。")
        bullets_raw = item.get("bullets") or []
        if not isinstance(bullets_raw, list):
            raise SpecError(f"blocks[{index}].bullets 必须是数组。")
        bullets = [str(b).strip() for b in bullets_raw if str(b).strip()]
        slide: dict[str, Any] = {"type": "slide", "title": title, "bullets": bullets}
        notes = item.get("notes")
        if isinstance(notes, str) and notes.strip():
            slide["notes"] = notes.strip()
        image = item.get("image")
        if image:
            slide["image"] = _image_ref(image if isinstance(image, dict) else {"artifact_id": image}, index=index)
        return slide, []
    raise SpecError(f"blocks[{index}] 无法规范化。")


def _image_ref(item: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SpecError(f"blocks[{index}] image 必须是对象。")
    out: dict[str, Any] = {"type": "image"}
    aid = item.get("artifact_id")
    b64 = item.get("bytes_b64") or item.get("data_b64")
    if isinstance(aid, str) and aid.strip():
        out["artifact_id"] = aid.strip()
    if isinstance(b64, str) and b64.strip():
        out["bytes_b64"] = b64.strip()
    if "artifact_id" not in out and "bytes_b64" not in out:
        raise SpecError(f"blocks[{index}] image 需要 artifact_id 或 bytes_b64。")
    alt = item.get("alt")
    if isinstance(alt, str) and alt.strip():
        out["alt"] = alt.strip()
    return out


def _str_row(raw: Any, *, allow_empty: bool) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError("表的 headers/rows 必须是数组。")
    cells = [str(c) for c in raw]
    if not allow_empty and not any(c.strip() for c in cells):
        raise SpecError("表行不能全空。")
    return cells


def _pad_row(row: list[str], width: int) -> list[str]:
    if len(row) >= width:
        return row[:width]
    return row + [""] * (width - len(row))


def _has_visible_content(blocks: list[dict[str, Any]], *, kind: str) -> bool:
    if kind == "pptx":
        return any(b.get("type") == "slide" and str(b.get("title") or "").strip() for b in blocks)
    for block in blocks:
        typ = block.get("type")
        if typ == "table" and block.get("rows"):
            return True
        if typ == "image":
            return True
        if typ in {"heading", "para"} and str(block.get("text") or "").strip():
            return True
    return False


def _docx_blocks_from_body(body: str) -> list[dict[str, Any]]:
    chunks = _split_blocks(body)
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        table = try_parse_markdown_table(chunk)
        if table:
            out.append(table)
        else:
            out.append({"type": "para", "text": chunk})
    return out


def _pptx_blocks_from_body(body: str, *, title: str, marker: str) -> list[dict[str, Any]]:
    parts = _split_blocks(body)
    if not parts:
        return [{"type": "slide", "title": title, "bullets": [f"标记：{marker}"]}]
    slides: list[dict[str, Any]] = []
    for index, chunk in enumerate(parts):
        lines = [ln.strip() for ln in chunk.split("\n") if ln.strip()]
        first = (lines[0] if lines else "")[:40] or (title if index == 0 else f"第{index + 1}页")
        rest = lines[1:] if len(lines) > 1 else []
        if index == 0:
            bullets = [f"标记：{marker}", *rest] if rest else [f"标记：{marker}", chunk]
            # Avoid duplicating the title line into bullets when it was split off.
            if rest:
                bullets = [f"标记：{marker}", *rest]
            elif chunk != first:
                bullets = [f"标记：{marker}", chunk]
            else:
                bullets = [f"标记：{marker}"]
        else:
            bullets = rest if rest else ([chunk] if chunk != first else [])
        slides.append({"type": "slide", "title": first, "bullets": bullets})
    return slides[:20]


def _split_blocks(raw: str) -> list[str]:
    text = (raw or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    if "\n---\n" in f"\n{text}\n":
        parts = [p.strip() for p in text.split("\n---\n") if p.strip()]
        if parts:
            return parts
    chunks = [part.strip() for part in text.split("\n\n") if part.strip()]
    if chunks:
        return chunks
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def try_parse_markdown_table(chunk: str) -> dict[str, Any] | None:
    """Turn a markdown pipe table into a spec table block. None if not a table."""
    lines = [ln.rstrip() for ln in (chunk or "").split("\n") if ln.strip()]
    if len(lines) < 2:
        return None
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if "|" not in stripped:
            return None
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            continue
        if not any(cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return None
    return {"type": "table", "headers": rows[0], "rows": rows[1:]}


def body_has_markdown_table(body: str | None) -> bool:
    for chunk in _split_blocks(body or ""):
        if try_parse_markdown_table(chunk):
            return True
    return False
