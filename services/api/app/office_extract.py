"""Stdlib extract for edu-read office files. Not a visual office product."""

from __future__ import annotations

import csv
import io
import zipfile
from xml.etree import ElementTree as ET

NS_SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MAX_TEXT = 8000
MAX_ROWS = 200
MAX_SHEETS = 3


def _tag(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def extension_of(name: str) -> str:
    base = (name or "").rsplit("/", 1)[-1]
    if "." not in base:
        return ""
    return base.rsplit(".", 1)[-1].lower()


def col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in (cell_ref or "") if ch.isalpha())
    if not letters:
        return 0
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return max(n - 1, 0)


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_office(filename: str, data: bytes) -> dict:
    """Return a stable extract dict. Never raises on bad bytes."""
    name = (filename or "file").strip() or "file"
    ext = extension_of(name)
    if not data:
        return _fail(name, ext, "empty", "空文件，抽不出内容")
    if ext in {"csv", "tsv", "txt", "md", "json"}:
        return _extract_text_table(name, ext, data, delimiter="\t" if ext == "tsv" else ",")
    if ext == "xlsx":
        return _extract_xlsx(name, data)
    if ext == "docx":
        return _extract_docx(name, data)
    if ext in {"xls", "doc", "pdf"}:
        return _fail(name, ext, "unsupported", "这种格式抽不出正文，请另存 xlsx 或 docx")
    return _fail(name, ext or "bin", "unsupported", "不支持这种文件")


def _ok(
    name: str,
    ext: str,
    *,
    headline: str,
    text: str,
    rows: int | None = None,
    cols: int | None = None,
    sheets: list[str] | None = None,
) -> dict:
    body = (text or "")[:MAX_TEXT]
    return {
        "filename": name[:180],
        "kind": ext,
        "status": "ok",
        "headline": headline[:80],
        "rows": rows,
        "cols": cols,
        "sheets": sheets or [],
        "text": body,
        "error": None,
    }


def _fail(name: str, ext: str, status: str, error: str) -> dict:
    return {
        "filename": name[:180],
        "kind": ext or "bin",
        "status": status,
        "headline": error[:80],
        "rows": None,
        "cols": None,
        "sheets": [],
        "text": "",
        "error": error[:120],
    }


def _extract_text_table(name: str, ext: str, data: bytes, *, delimiter: str) -> dict:
    text = _decode_text(data)
    if ext in {"txt", "md", "json"}:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        headline = f"读到 {len(lines)} 行"
        return _ok(name, ext, headline=headline, text=text, rows=len(lines), cols=1)
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error:
        return _fail(name, ext, "bad_file", "坏文件，抽不出表")
    width = max((len(r) for r in rows), default=0)
    preview = "\n".join(",".join(c.strip() for c in r) for r in rows[:MAX_ROWS])
    headline = f"读到 {len(rows)} 行 / {width} 列"
    return _ok(name, ext, headline=headline, text=preview, rows=len(rows), cols=width)


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    out: list[str] = []
    for si in root.findall(_tag(NS_SS, "si")):
        parts = [t.text or "" for t in si.iter(_tag(NS_SS, "t"))]
        out.append("".join(parts))
    return out


def _sheet_names(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    try:
        raw = zf.read("xl/workbook.xml")
    except KeyError:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    names: list[str] = []
    for sheet in root.iter(_tag(NS_SS, "sheet")):
        names.append(sheet.attrib.get("name") or f"表{len(names) + 1}")
    paths = [
        info.filename
        for info in zf.infolist()
        if info.filename.startswith("xl/worksheets/sheet") and info.filename.endswith(".xml")
    ]
    paths.sort()
    paired: list[tuple[str, str]] = []
    for i, path in enumerate(paths[:MAX_SHEETS]):
        label = names[i] if i < len(names) else f"表{i + 1}"
        paired.append((label, path))
    return paired


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "s":
        node = cell.find(_tag(NS_SS, "v"))
        if node is None or node.text is None:
            return ""
        try:
            idx = int(node.text)
        except ValueError:
            return ""
        if 0 <= idx < len(shared):
            return shared[idx]
        return ""
    if kind == "inlineStr":
        parts = [t.text or "" for t in cell.iter(_tag(NS_SS, "t"))]
        return "".join(parts)
    node = cell.find(_tag(NS_SS, "v"))
    return (node.text or "") if node is not None else ""


def _extract_sheet(raw: bytes, shared: list[str]) -> tuple[int, int, list[str]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return 0, 0, []
    grid: dict[tuple[int, int], str] = {}
    max_r = -1
    max_c = -1
    for cell in root.iter(_tag(NS_SS, "c")):
        ref = cell.attrib.get("r") or ""
        row_digits = "".join(ch for ch in ref if ch.isdigit())
        if not row_digits:
            continue
        r = int(row_digits) - 1
        c = col_index(ref)
        val = _cell_value(cell, shared).strip()
        if not val:
            continue
        grid[(r, c)] = val
        max_r = max(max_r, r)
        max_c = max(max_c, c)
    if max_r < 0:
        return 0, 0, []
    lines: list[str] = []
    for r in range(min(max_r + 1, MAX_ROWS)):
        row = [grid.get((r, c), "") for c in range(max_c + 1)]
        if any(row):
            lines.append(",".join(row))
    return max_r + 1, max_c + 1, lines


def _extract_xlsx(name: str, data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return _fail(name, "xlsx", "bad_file", "坏文件，抽不出表")
    with zf:
        if "xl/workbook.xml" not in zf.namelist():
            return _fail(name, "xlsx", "bad_file", "坏文件，抽不出表")
        shared = _shared_strings(zf)
        sheets = _sheet_names(zf)
        if not sheets:
            return _fail(name, "xlsx", "bad_file", "坏文件，抽不出表")
        best_rows = 0
        best_cols = 0
        chunks: list[str] = []
        labels: list[str] = []
        for label, path in sheets:
            try:
                raw = zf.read(path)
            except KeyError:
                continue
            rows, cols, lines = _extract_sheet(raw, shared)
            labels.append(label)
            best_rows = max(best_rows, rows)
            best_cols = max(best_cols, cols)
            if lines:
                chunks.append(f"[{label}]\n" + "\n".join(lines) if len(sheets) > 1 else "\n".join(lines))
        if best_rows <= 0:
            return _fail(name, "xlsx", "bad_file", "表是空的，抽不出格子")
        headline = f"读到 {best_rows} 行 / {best_cols} 列"
        if len(labels) > 1:
            headline = f"读到 {best_rows} 行 / {best_cols} 列（{len(labels)} 张表）"
        return _ok(
            name,
            "xlsx",
            headline=headline,
            text="\n\n".join(chunks),
            rows=best_rows,
            cols=best_cols,
            sheets=labels,
        )


def _extract_docx(name: str, data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return _fail(name, "docx", "bad_file", "坏文件，抽不出正文")
    with zf:
        try:
            raw = zf.read("word/document.xml")
        except KeyError:
            return _fail(name, "docx", "bad_file", "坏文件，抽不出正文")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return _fail(name, "docx", "bad_file", "坏文件，抽不出正文")
    paras: list[str] = []
    for p in root.iter(_tag(NS_W, "p")):
        line = "".join(t.text or "" for t in p.iter(_tag(NS_W, "t"))).strip()
        if line:
            paras.append(line)
    if not paras:
        return _fail(name, "docx", "bad_file", "文档是空的")
    headline = f"读到 {len(paras)} 段"
    return _ok(name, "docx", headline=headline, text="\n".join(paras), rows=len(paras), cols=1)
