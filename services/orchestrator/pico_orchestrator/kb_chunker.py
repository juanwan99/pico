"""Parent/child chunking of extracted material text for the Meili chunk index (#1006).

Input is the markdown-ish text Docling / pypdfium2 / RapidOCR already produce
(``#`` headings, blank-line paragraphs, ``|`` table rows, ``\\x0c`` page breaks).
Output is a flat list of child chunks, each carrying its parent section text so
retrieval can show a passage with its surrounding context and cite a page.

This is a splitter, not a parser: no layout model, no tokenizer, no vendor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CHILD_MAX = 450
CHILD_MIN = 120
PARENT_MAX = 2000
HEADING_MAX = 120
MAX_CHUNKS = 400

_SENTENCE_END = re.compile(r"(?<=[。！？；!?;\n])")
_HEADING = re.compile(r"^#{1,6}\s*(.+?)\s*#*\s*$")
_PAGE_BREAK = "\x0c"


@dataclass
class Chunk:
    seq: int
    heading: str
    text: str
    page: int | None
    parent_seq: int
    parent_text: str
    tags: list[str] = field(default_factory=list)


@dataclass
class _Block:
    kind: str  # "heading" | "para" | "table"
    text: str
    page: int | None


def _blocks(text: str) -> list[_Block]:
    """Split raw text into headings, paragraphs and table runs, tracking pages."""
    out: list[_Block] = []
    buf: list[str] = []
    buf_kind = "para"
    page: int | None = 1 if _PAGE_BREAK in text else None

    def flush() -> None:
        nonlocal buf, buf_kind
        if buf:
            joined = "\n".join(buf).strip()
            if joined:
                out.append(_Block(buf_kind, joined, page))
        buf = []
        buf_kind = "para"

    for raw_line in (text or "").replace("\r\n", "\n").split("\n"):
        if _PAGE_BREAK in raw_line:
            flush()
            page = (page or 1) + raw_line.count(_PAGE_BREAK)
            rest = raw_line.replace(_PAGE_BREAK, "").strip()
            if rest:
                buf.append(rest)
            continue
        line = raw_line.rstrip()
        if not line.strip():
            flush()
            continue
        m = _HEADING.match(line.strip())
        if m:
            flush()
            out.append(_Block("heading", m.group(1)[:HEADING_MAX], page))
            continue
        is_table = line.lstrip().startswith("|")
        if buf and (buf_kind == "table") != is_table:
            flush()
        buf_kind = "table" if is_table else "para"
        buf.append(line.strip())
    flush()
    return out


def _split_long(text: str, limit: int) -> list[str]:
    """Split one oversized paragraph on sentence ends, then hard-wrap what is left."""
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    cur = ""
    for sent in _SENTENCE_END.split(text):
        if not sent:
            continue
        if len(cur) + len(sent) > limit and cur:
            pieces.append(cur.strip())
            cur = ""
        while len(sent) > limit:
            pieces.append(sent[:limit].strip())
            sent = sent[limit:]
        cur += sent
    if cur.strip():
        pieces.append(cur.strip())
    return [p for p in pieces if p]


def _children_of(blocks: list[_Block], *, child_max: int, child_min: int) -> list[tuple[str, int | None]]:
    """Pack consecutive blocks into children of roughly child_max characters."""
    children: list[tuple[str, int | None]] = []
    cur: list[str] = []
    cur_len = 0
    cur_page: int | None = None

    def flush() -> None:
        nonlocal cur, cur_len, cur_page
        if cur:
            children.append(("\n".join(cur).strip(), cur_page))
        cur, cur_len, cur_page = [], 0, None

    for block in blocks:
        for piece in _split_long(block.text, child_max):
            if cur and cur_len + len(piece) + 1 > child_max:
                flush()
            if not cur:
                cur_page = block.page
            cur.append(piece)
            cur_len += len(piece) + 1
    flush()
    # Merge a trailing tiny child into its predecessor so citations are not one-liners.
    if len(children) >= 2 and len(children[-1][0]) < child_min:
        last_text, _last_page = children.pop()
        prev_text, prev_page = children[-1]
        children[-1] = (prev_text + "\n" + last_text, prev_page)
    return children


def chunk_text(
    text: str,
    *,
    title: str = "",
    child_max: int = CHILD_MAX,
    child_min: int = CHILD_MIN,
    parent_max: int = PARENT_MAX,
    max_chunks: int = MAX_CHUNKS,
) -> list[Chunk]:
    """Section-aware parent/child chunks. Empty text → []."""
    blocks = _blocks(text)
    if not blocks:
        return []
    # Group blocks into sections at headings.
    sections: list[tuple[str, list[_Block]]] = []
    heading = (title or "").strip()[:HEADING_MAX]
    body: list[_Block] = []
    for block in blocks:
        if block.kind == "heading":
            if body:
                sections.append((heading, body))
            heading = block.text
            body = []
        else:
            body.append(block)
    if body:
        sections.append((heading, body))
    elif heading and not sections:
        sections.append((heading, []))

    chunks: list[Chunk] = []
    seq = 0
    for parent_seq, (sec_heading, sec_blocks) in enumerate(sections):
        parent_text = "\n".join(b.text for b in sec_blocks).strip()
        if sec_heading and sec_heading != (title or "").strip()[:HEADING_MAX]:
            parent_text = f"{sec_heading}\n{parent_text}".strip()
        parent_text = parent_text[:parent_max]
        for child_text, page in _children_of(sec_blocks, child_max=child_max, child_min=child_min):
            if not child_text:
                continue
            chunks.append(
                Chunk(
                    seq=seq,
                    heading=sec_heading,
                    text=child_text,
                    page=page,
                    parent_seq=parent_seq,
                    parent_text=parent_text,
                )
            )
            seq += 1
            if seq >= max_chunks:
                return chunks
    return chunks
