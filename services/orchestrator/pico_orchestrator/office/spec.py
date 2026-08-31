"""pico.office.spec/v1 — structured intermediate. File bytes are a projection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

_FAKE_IMAGE = re.compile(r"\[image:[^\]]*\]", re.IGNORECASE)
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_CODE = re.compile(r"`+")
_HEADING = re.compile(r"^#{1,6}\s+")
_LIST = re.compile(r"^(\s*[-*+]|\s*\d+\.)\s+")
_HR = re.compile(r"^[-*_]{3,}$")


def sanitize_slide_text(raw: str | None) -> str:
    """Drop chat/markdown leftovers. Not a layout engine."""
    text = _FAKE_IMAGE.sub("", str(raw or ""))
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_CODE.sub("", text)
    parts: list[str] = []
    for line in text.splitlines():
        item = line.strip()
        if not item or _HR.match(item):
            continue
        item = _HEADING.sub("", item)
        item = _LIST.sub("", item).strip()
        if item:
            parts.append(item)
    return "\n".join(parts)

SCHEMA = "pico.office.spec/v1"
Kind = Literal["docx", "pptx", "xlsx"]


@dataclass(frozen=True)
class Theme:
    heading_font: str | None = None
    body_font: str | None = None
    accent: str | None = None
    background: str | None = None

    @classmethod
    def from_raw(cls, raw: Any) -> Theme | None:
        if not isinstance(raw, dict) or not raw:
            return None
        # GPT / Codex send CSS-like camelCase. Same three colors + fonts —
        # not a new spec field. Snake_case keys stay first.
        heading = _first_str(raw, "heading_font", "headingFont", "fontFace", "font")
        body = _first_str(raw, "body_font", "bodyFont", "fontFace", "font")
        accent = _first_str(
            raw, "accent", "accentColor", "accent_color", "primaryColor", "primary"
        )
        background = _first_str(
            raw, "background", "backgroundColor", "background_color"
        )
        if not any((heading, body, accent, background)):
            return None
        return cls(
            heading_font=heading,
            body_font=body,
            accent=accent,
            background=background,
        )


@dataclass(frozen=True)
class CommentSpec:
    paragraph: int
    text: str


@dataclass(frozen=True)
class Block:
    type: str
    text: str = ""
    level: int = 1
    rows: tuple[tuple[str, ...], ...] = ()
    artifact_id: str | None = None
    title: str = ""
    bullets: tuple[str, ...] = ()
    notes: str = ""
    image_artifact_id: str | None = None
    headers: tuple[str, ...] = ()
    cover: bool = False

    def image_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        if self.artifact_id:
            ids.append(self.artifact_id)
        if self.image_artifact_id:
            ids.append(self.image_artifact_id)
        return tuple(ids)


@dataclass(frozen=True)
class OfficeSpec:
    schema: str
    kind: Kind
    title: str
    marker: str
    theme: Theme | None = None
    blocks: tuple[Block, ...] = field(default_factory=tuple)
    comments: tuple[CommentSpec, ...] = field(default_factory=tuple)
    values: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def image_ids(self) -> tuple[str, ...]:
        seen: list[str] = []
        for block in self.blocks:
            for item in block.image_ids():
                if item not in seen:
                    seen.append(item)
        return tuple(seen)

    def values_map(self) -> dict[str, str]:
        return {key: val for key, val in self.values if key}


def parse_spec(raw: Any, *, default_kind: Kind | None = None) -> OfficeSpec:
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("spec 不是合法 JSON。") from exc
    if not isinstance(raw, dict):
        raise TypeError("spec 必须是对象。")
    kind = str(raw.get("kind") or default_kind or "").strip().lower()
    if kind not in {"docx", "pptx", "xlsx"}:
        raise ValueError("spec.kind 只支持 docx、pptx 或 xlsx。")
    title = str(raw.get("title") or "").strip() or _default_title(kind)
    marker = str(raw.get("marker") or "").strip()
    blocks_raw = raw.get("blocks")
    if kind == "xlsx" and not blocks_raw:
        blocks_raw = raw.get("sheets")
    # Live F4: Pi sent spec={images:[]} / {kpi_table_title} with sibling blocks
    # already merged by the tool. If blocks are still missing, a title/theme
    # still becomes one slide — do not fail the whole deck.
    if kind == "pptx" and (blocks_raw is None or blocks_raw == []):
        heading = str(raw.get("title") or "").strip()
        if heading or Theme.from_raw(raw.get("theme")) is not None:
            blocks_raw = [{"type": "slide", "title": heading or title}]
    if not isinstance(blocks_raw, list) or not blocks_raw:
        raise ValueError("spec.blocks 不能为空。" if kind != "xlsx" else "Excel spec 需要 sheets 或 blocks。")
    blocks = tuple(_parse_block(item, kind=kind) for item in blocks_raw)  # type: ignore[misc]
    return OfficeSpec(
        schema=str(raw.get("schema") or SCHEMA),
        kind=kind,  # type: ignore[arg-type]
        title=title,
        marker=marker,
        theme=Theme.from_raw(raw.get("theme")),
        blocks=blocks,
        comments=_parse_comments(raw.get("comments")),
        values=_parse_values(raw.get("values") or raw.get("fill")),
    )


def spec_from_plain(
    *,
    kind: Kind,
    title: str,
    marker: str,
    body: str | None,
) -> OfficeSpec:
    """Compat: old generate_* text body → v1 spec. No invented filler."""
    from pico_orchestrator.document_generators import _docx_body_paragraphs, _pptx_slides

    if kind == "xlsx":
        from pico_orchestrator.document_generators import xlsx_plain_sheets

        heading = title.strip() or "Pico XLSX"
        sheets = xlsx_plain_sheets(body, title=heading, marker=marker)
        return OfficeSpec(
            schema=SCHEMA,
            kind="xlsx",
            title=heading,
            marker=marker,
            blocks=tuple(
                Block(type="sheet", title=name[:31], headers=headers, rows=rows)
                for name, headers, rows in sheets
            ),
        )
    if kind == "docx":
        blocks = [Block(type="heading", text=title, level=0)]
        if marker:
            blocks.append(Block(type="para", text=f"标记：{marker}"))
        for para in _docx_body_paragraphs(body):
            blocks.append(Block(type="para", text=para))
        return OfficeSpec(schema=SCHEMA, kind="docx", title=title, marker=marker, blocks=tuple(blocks))
    slides = _pptx_slides(body, title=title, marker=marker)
    blocks = tuple(
        Block(
            type="slide",
            title=sanitize_slide_text(slide_title) or "幻灯",
            bullets=_bullets_from_body(slide_body),
        )
        for slide_title, slide_body in slides
    )
    return OfficeSpec(schema=SCHEMA, kind="pptx", title=title, marker=marker, blocks=blocks)


def _default_title(kind: str) -> str:
    if kind == "xlsx":
        return "Pico XLSX"
    if kind == "pptx":
        return "Pico PPTX"
    return "Pico DOCX"


def _bullets_from_body(body: str) -> tuple[str, ...]:
    lines: list[str] = []
    for raw in (body or "").splitlines():
        item = sanitize_slide_text(raw)
        if item:
            lines.append(item)
    return tuple(lines) if lines else ("",)


def _parse_block(item: Any, *, kind: Kind) -> Block:
    if not isinstance(item, dict):
        raise TypeError("block 必须是对象。")
    btype = str(item.get("type") or "").strip().lower()
    if kind == "xlsx":
        if btype and btype != "sheet":
            raise ValueError("Excel spec 的 block.type 必须是 sheet。")
        name = str(item.get("name") or item.get("title") or "Sheet1").strip() or "Sheet1"
        headers_raw = item.get("headers")
        headers = (
            tuple(str(x) for x in headers_raw)
            if isinstance(headers_raw, list) and headers_raw
            else ()
        )
        rows_raw = item.get("rows")
        rows = _table_rows(rows_raw) if rows_raw is not None else ()
        if not headers and not rows:
            raise ValueError("Excel sheet 需要 headers 或 rows。")
        return Block(type="sheet", title=name[:31], headers=headers, rows=rows)
    if kind == "pptx":
        # Pi / document-skill send cover|content|title|page. Those are slides,
        # not a new spec field. Missing type with title/bullets already worked.
        title = sanitize_slide_text(str(item.get("title") or "").strip())
        bullets_raw = item.get("bullets")
        if isinstance(item.get("text"), str) and not bullets_raw:
            bullets = _bullets_from_body(item["text"])
        elif isinstance(bullets_raw, list):
            bullets = tuple(
                item_text
                for item_text in (sanitize_slide_text(str(x)) for x in bullets_raw)
                if item_text
            )
        else:
            bullets = ()
        if not title and not bullets:
            raise ValueError("PPT 页需要 title 或 bullets。")
        return Block(
            type="slide",
            title=title or (bullets[0][:40] if bullets else "幻灯"),
            bullets=bullets,
            notes=str(item.get("notes") or "").strip(),
            image_artifact_id=_opt_str(item.get("image_artifact_id") or item.get("image")),
            cover=btype in {"cover", "title"},
        )
    if btype == "heading":
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError("heading 不能为空。")
        level = item.get("level", 1)
        try:
            lvl = int(level)
        except (TypeError, ValueError) as exc:
            raise ValueError("heading.level 必须是数字。") from exc
        return Block(type="heading", text=text, level=max(0, min(lvl, 4)))
    if btype == "para":
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError("para 不能为空。")
        return Block(type="para", text=text)
    if btype == "table":
        rows = _table_rows(item.get("rows"))
        return Block(type="table", rows=rows)
    if btype == "image":
        aid = _opt_str(item.get("artifact_id") or item.get("image_artifact_id"))
        if not aid:
            raise ValueError("image 需要 artifact_id（先 generate_image）。")
        return Block(type="image", artifact_id=aid, text=str(item.get("text") or "").strip())
    if btype == "page_break":
        return Block(type="page_break")
    raise ValueError(f"不支持的 block.type：{btype or '空'}。")


def _parse_comments(raw: Any) -> tuple[CommentSpec, ...]:
    if raw in (None, ""):
        return ()
    if not isinstance(raw, list):
        raise TypeError("comments 必须是数组。")
    out: list[CommentSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("comment 必须是对象。")
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError("comment.text 不能为空。")
        para = item.get("paragraph", item.get("paragraph_index", item.get("index")))
        try:
            idx = int(para)
        except (TypeError, ValueError) as exc:
            raise ValueError("comment.paragraph 必须是数字，从 1 起。") from exc
        if idx < 1:
            raise ValueError("comment.paragraph 从 1 起。")
        out.append(CommentSpec(paragraph=idx, text=text))
    return tuple(out)


def _parse_values(raw: Any) -> tuple[tuple[str, str], ...]:
    if raw in (None, ""):
        return ()
    if not isinstance(raw, dict):
        raise TypeError("values 必须是对象，例如 {\"姓名\": \"张三\"}。")
    return tuple((str(key).strip(), str(val)) for key, val in raw.items() if str(key).strip())


def _table_rows(raw: Any) -> tuple[tuple[str, ...], ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("table.rows 不能为空。")
    rows: list[tuple[str, ...]] = []
    width = 0
    for row in raw:
        if not isinstance(row, list) or not row:
            raise ValueError("table 每一行必须是非空数组。")
        cells = tuple(str(c) if c is not None else "" for c in row)
        width = max(width, len(cells))
        rows.append(cells)
    padded = tuple(cells + ("",) * (width - len(cells)) for cells in rows)
    return padded


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_str(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        got = _opt_str(raw.get(key))
        if got:
            return got
    return None
