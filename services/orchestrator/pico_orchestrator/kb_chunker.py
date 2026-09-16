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
_CODE_START = re.compile(r"^(?:async\s+)?def\s|^class\s")
_PAGE_BREAK = "\x0c"


def _pipe_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_pipe_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _is_pipe_separator(line: str) -> bool:
    compact = line.strip().replace(" ", "")
    return bool(compact) and set(compact) <= set("|:-")


def expand_pipe_tables(text: str) -> str:
    """Each markdown table data row also carries header=value. Format-wide, no titles."""
    lines = (text or "").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if (
            i + 1 < len(lines)
            and _is_pipe_table_line(lines[i])
            and _is_pipe_separator(lines[i + 1])
        ):
            header = _pipe_cells(lines[i])
            out.append(lines[i])
            out.append(lines[i + 1])
            i += 2
            while i < len(lines) and _is_pipe_table_line(lines[i]) and not _is_pipe_separator(lines[i]):
                cells = _pipe_cells(lines[i])
                raw = "| " + " | ".join(cells) + " |"
                pairs = []
                for j, name in enumerate(header):
                    val = cells[j] if j < len(cells) else ""
                    lab = name or f"列{j + 1}"
                    if val:
                        pairs.append(f"{lab}={val}")
                if pairs:
                    out.append(raw + " " + " ".join(f"| {p}" for p in pairs))
                else:
                    out.append(lines[i])
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


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


def _looks_like_code(text: str) -> bool:
    return any(_CODE_START.match(ln) for ln in (text or "").splitlines())


def _split_code(text: str, limit: int) -> list[str]:
    """Keep def/class units together; wrap leftover on newlines, not CJK periods."""
    units: list[list[str]] = []
    cur: list[str] = []
    for ln in (text or "").splitlines():
        if _CODE_START.match(ln) and cur:
            units.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        units.append(cur)
    pieces: list[str] = []
    for unit in units:
        blob = "\n".join(unit).strip()
        if not blob:
            continue
        if len(blob) <= limit:
            pieces.append(blob)
            continue
        acc = ""
        for line in unit:
            if acc and len(acc) + len(line) + 1 > limit:
                pieces.append(acc.strip())
                acc = line
            else:
                acc = f"{acc}\n{line}" if acc else line
        if acc.strip():
            pieces.append(acc.strip())
    return pieces


def _table_header_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip() and not _is_pipe_separator(line):
            return line.strip()
    return ""


def _split_table(text: str, limit: int) -> list[str]:
    """Keep the header on every table child so a split row still names its columns."""
    header = _table_header_line(text)
    data = [
        ln
        for ln in (text or "").splitlines()
        if ln.strip() and not _is_pipe_separator(ln) and ln.strip() != header
    ]
    if not data:
        return [text] if (text or "").strip() else []
    pieces: list[str] = []
    cur = [header] if header else []
    cur_len = len(header)
    for line in data:
        extra = len(line) + 1
        if cur and cur_len + extra > limit:
            pieces.append("\n".join(cur).strip())
            cur = [header] if header else []
            cur_len = len(header)
        cur.append(line)
        cur_len += extra
    if cur and (not header or len(cur) > 1):
        pieces.append("\n".join(cur).strip())
    elif cur:
        pieces.append("\n".join(cur).strip())
    return [p for p in pieces if p]


def _split_long(text: str, limit: int) -> list[str]:
    """Split one oversized paragraph on sentence ends, then hard-wrap what is left."""
    if _looks_like_code(text):
        return _split_code(text, limit)
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
        splitter = _split_table if block.kind == "table" else _split_long
        for piece in splitter(block.text, child_max):
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
    blocks = _blocks(expand_pipe_tables(text))
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
