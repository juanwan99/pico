"""Protected artifact types: fail-closed against renamed text posing as Office/HTML."""

from __future__ import annotations

import io
import zipfile

# Extensions that MUST only come from dedicated generators (or valid bytes).
PROTECTED_EXTENSIONS = frozenset({".html", ".htm", ".docx", ".pptx", ".xlsx"})


def title_protected_extension(title: str) -> str | None:
    """Return protected extension if title claims one, else None."""
    name = (title or "").strip().split("/")[-1].lower()
    for ext in PROTECTED_EXTENSIONS:
        if name.endswith(ext):
            return ext
    return None


def is_valid_ooxml_package(raw: bytes, ext: str) -> bool:
    """True only if ZIP contains the minimal OOXML parts for docx/pptx/xlsx."""
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
    if ext == ".xlsx":
        return "xl/workbook.xml" in names and any(
            n.startswith("xl/worksheets/sheet") and n.endswith(".xml") for n in names
        )
    return False


def zip_with_utf8_flag(raw: bytes) -> bytes:
    """Repack a ZIP whose UTF-8 names lack the UTF-8 bit (Info-ZIP ``zip``).

    Windows reads such names in the OEM code page, so 春游.csv shows as
    garbage. Returns ``raw`` unchanged unless every unflagged non-ASCII name
    is valid UTF-8 (a GBK zip from a teacher is left alone).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            infos = zf.infolist()
            names: list[str] = []
            for info in infos:
                if info.flag_bits & 0x1:
                    return raw
                name = info.filename
                if not info.flag_bits & 0x800 and not name.isascii():
                    name = name.encode("cp437").decode("utf-8")
                names.append(name)
            if names == [i.filename for i in infos]:
                return raw
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as dst:
                for info, name in zip(infos, names, strict=True):
                    fixed = zipfile.ZipInfo(name, info.date_time)
                    fixed.compress_type = info.compress_type
                    fixed.external_attr = info.external_attr
                    fixed.create_system = info.create_system
                    dst.writestr(fixed, zf.read(info))
    except (zipfile.BadZipFile, UnicodeError, NotImplementedError, OSError, EOFError):
        return raw
    return out.getvalue()


def reject_fake_protected_write_message(ext: str) -> str:
    return (
        f"禁止用 workspace_write_file 写入 {ext}（改后缀文本不算真文件）。"
        "请使用 generate_html_document 写网页，或 sandbox_office_lib 写 Word/Excel/PPT。"
    )
