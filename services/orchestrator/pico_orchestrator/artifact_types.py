"""Protected artifact types: fail-closed against renamed text posing as Office/HTML."""

from __future__ import annotations

import io
import zipfile

# Extensions that MUST only come from dedicated generators (or valid bytes).
PROTECTED_EXTENSIONS = frozenset({".html", ".htm", ".docx", ".pptx"})


def title_protected_extension(title: str) -> str | None:
    """Return protected extension if title claims one, else None."""
    name = (title or "").strip().split("/")[-1].lower()
    for ext in PROTECTED_EXTENSIONS:
        if name.endswith(ext):
            return ext
    return None


def is_valid_ooxml_package(raw: bytes, ext: str) -> bool:
    """True only if ZIP contains the minimal OOXML parts for docx/pptx."""
    if not raw or raw[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False
    if "[Content_Types].xml" not in names:
        return False
    if ext == ".docx":
        return "word/document.xml" in names
    if ext == ".pptx":
        return "ppt/presentation.xml" in names and any(
            n.startswith("ppt/slides/slide") and n.endswith(".xml") for n in names
        )
    return False


def reject_fake_protected_write_message(ext: str) -> str:
    return (
        f"禁止用 workspace_write_file 写入 {ext}（改后缀文本不算真文件）。"
        "请使用 generate_html_document / generate_docx_document / generate_pptx_document。"
    )
