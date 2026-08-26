"""Office kind + LibreOffice binary. Content pages live in office_preview."""

from __future__ import annotations

import shutil
from pathlib import Path

from pico_orchestrator.gateway import ToolError

OFFICE_ENGINE = "libreoffice-writer"
DESKTOP_W = 1280
DESKTOP_H = 800

KIND_FLAGS = {
    "writer": "--writer",
    "calc": "--calc",
    "impress": "--impress",
}

KIND_LABEL = {
    "writer": "文档",
    "calc": "表格",
    "impress": "演示文稿",
}


def resolve_kind(filename: str, kind: str = "") -> str:
    raw = (kind or "").strip().lower()
    if raw in KIND_FLAGS:
        return raw
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls", ".ods", ".csv")):
        return "calc"
    if name.endswith((".pptx", ".ppt", ".odp")):
        return "impress"
    return "writer"


def soffice_bin() -> str:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    raise ToolError(
        "sandbox.office_unavailable",
        "沙箱未安装 LibreOffice，无法转出文档内容页。",
    )


async def open_office(*, kind: str, filename: str, document: bytes):
    from sandbox_worker.office_preview import open_office_pages

    _ = Path(filename or "document.docx").name
    return await open_office_pages(kind=kind, filename=filename, document=document)
