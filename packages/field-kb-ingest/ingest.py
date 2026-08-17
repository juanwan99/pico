"""field-kb-ingest · Docling engine. Pointers stay in edu."""

from __future__ import annotations

import tempfile
from pathlib import Path

ENGINE = "docling"
MAX_EXCERPT = 800
MAX_SLICES = 8


def slices_from_markdown(md: str, title: str) -> list[dict]:
    text = (md or "").replace("\r\n", "\n").strip()
    heading = (title or "").strip() or "未命名"
    if not text:
        return [{"title": heading, "excerpt": heading, "tags": ["empty"]}]
    blocks: list[str] = []
    buf: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#"):
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
            blocks.append(line.lstrip("# ").strip())
        elif line.strip() == "":
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line.strip())
    if buf:
        blocks.append("\n".join(buf).strip())
    out = []
    for block in blocks:
        chunk = block.strip()
        if len(chunk) < 1:
            continue
        out.append(
            {
                "title": heading[:200],
                "excerpt": chunk[:MAX_EXCERPT],
                "tags": ["docling"],
            }
        )
        if len(out) >= MAX_SLICES:
            break
    if not out:
        out.append({"title": heading[:200], "excerpt": text[:MAX_EXCERPT], "tags": ["docling"]})
    return out


def _convert_path(path: Path) -> str:
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(str(path))
    document = getattr(result, "document", None)
    if document is None:
        return ""
    export = getattr(document, "export_to_markdown", None)
    if callable(export):
        return str(export() or "")
    return str(document)


def ingest_bytes(*, filename: str, data: bytes, title: str) -> dict:
    suffix = Path(filename or "file.bin").suffix or ".bin"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / f"src{suffix}"
            dest.write_bytes(data or b"")
            md = _convert_path(dest)
    except Exception as exc:
        return {
            "ok": False,
            "engine": ENGINE,
            "unread": True,
            "error": str(exc),
            "slices": [],
        }
    slices = slices_from_markdown(md, title or filename or "文件")
    body = " ".join(s.get("excerpt") or "" for s in slices).strip()
    heading = (title or filename or "").strip()
    if not md.strip() or not body or body == heading:
        return {
            "ok": False,
            "engine": ENGINE,
            "unread": True,
            "error": "empty",
            "slices": [],
        }
    return {"ok": True, "engine": ENGINE, "slices": slices}


def ingest_text(*, text: str, title: str) -> dict:
    md = text or ""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "src.md"
            dest.write_text(md, encoding="utf-8")
            md = _convert_path(dest) or md
    except Exception:
        pass
    return {
        "ok": True,
        "engine": ENGINE,
        "slices": slices_from_markdown(md or text, title or "文"),
    }
