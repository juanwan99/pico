"""LibreOffice headless content raster. Pages only — no Writer/Impress chrome.

Thin adapter: soffice --convert-to pdf, then pdftoppm (or soffice png).
Not a Pico slide editor.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import tempfile
from pathlib import Path

from pico_orchestrator.gateway import ToolError

from sandbox_worker.browser import PNG_MAGIC
from sandbox_worker.office import resolve_kind, soffice_bin

logger = logging.getLogger(__name__)

MAX_PAGES = 20
MAX_DOC_BYTES = 12 * 1024 * 1024
CONVERT_TIMEOUT_S = 55.0
PDF_DPI = 120
DESKTOP_W = 1280


class OfficePages:
    """One document as content-page PNGs. Screenshot is the current page."""

    def __init__(self, *, kind: str, filename: str, pages: list[bytes]) -> None:
        if not pages:
            raise ToolError("sandbox.raster_failed", "文档没有可显示的内容页")
        self.kind = kind
        self.filename = filename
        self.pages = pages
        self.index = 0

    @property
    def url(self) -> str:
        return f"sandbox://{self.kind}/{self.filename}"

    async def title(self) -> str:
        return self.filename

    async def h1(self) -> str:
        return self.filename

    async def describe_inputs(self) -> dict[str, bool]:
        return {"has_text_input": False, "has_password_input": False}

    async def screenshot_png(self) -> bytes:
        return self.pages[self.index]

    async def click(self, x: int, y: int) -> None:
        _ = y
        if x < DESKTOP_W // 3 and self.index > 0:
            self.index -= 1
        elif x > (DESKTOP_W * 2) // 3 and self.index < len(self.pages) - 1:
            self.index += 1

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = text, password

    async def close(self) -> None:
        self.pages = []


def _read_pngs(paths: list[Path]) -> list[bytes]:
    out: list[bytes] = []
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if raw.startswith(PNG_MAGIC):
            out.append(raw)
        if len(out) >= MAX_PAGES:
            break
    return out


async def _run(cmd: list[str], *, env: dict[str, str], timeout: float) -> int:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except TimeoutError as exc:
        if proc.returncode is None:
            proc.kill()
        raise ToolError("sandbox.raster_failed", "文档内容页转换超时") from exc
    return int(proc.returncode or 0)


async def _pdf_to_pngs(pdf: Path, dest: Path, env: dict[str, str]) -> list[bytes]:
    dest.mkdir(parents=True, exist_ok=True)
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = dest / "page"
        await _run(
            [
                pdftoppm,
                "-png",
                "-r",
                str(PDF_DPI),
                "-l",
                str(MAX_PAGES),
                str(pdf),
                str(prefix),
            ],
            env=env,
            timeout=CONVERT_TIMEOUT_S,
        )
        pages = _read_pngs(sorted(dest.glob("page*.png")))
        if pages:
            return pages
    soffice = soffice_bin()
    profile = dest / "lo-png"
    profile.mkdir(parents=True, exist_ok=True)
    await _run(
        [
            soffice,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--nologo",
            "--norestore",
            "--nolockcheck",
            "--nofirststartwizard",
            "--invisible",
            "--convert-to",
            "png",
            "--outdir",
            str(dest),
            str(pdf),
        ],
        env=env,
        timeout=CONVERT_TIMEOUT_S,
    )
    return _read_pngs(sorted(dest.glob("*.png")))


async def render_office_pages(filename: str, document: bytes) -> list[bytes]:
    """Return PNG pages of the document content. Never invent pixels."""
    if not document:
        raise ToolError("tool.invalid_arguments", "文档内容为空")
    if len(document) > MAX_DOC_BYTES:
        raise ToolError("tool.invalid_arguments", "文档超过 12MB，沙箱拒收")
    soffice = soffice_bin()
    work = Path(tempfile.mkdtemp(prefix="sbox_prev_"))
    try:
        safe_name = Path(filename or "document.docx").name or "document.docx"
        src = work / safe_name
        src.write_bytes(document)
        profile = work / "lo-profile"
        profile.mkdir(parents=True, exist_ok=True)
        outdir = work / "out"
        outdir.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "HOME": str(work),
            "LANG": os.environ.get("LANG") or "C.UTF-8",
            "SAL_USE_VCLPLUGIN": "gen",
        }
        code = await _run(
            [
                soffice,
                f"-env:UserInstallation=file://{profile}",
                "--headless",
                "--nologo",
                "--norestore",
                "--nolockcheck",
                "--nofirststartwizard",
                "--invisible",
                "--convert-to",
                "pdf",
                "--outdir",
                str(outdir),
                str(src),
            ],
            env=env,
            timeout=CONVERT_TIMEOUT_S,
        )
        pdfs = sorted(outdir.glob("*.pdf"))
        if code != 0 or not pdfs:
            raise ToolError("sandbox.raster_failed", "文档内容页转换失败")
        pages = await _pdf_to_pngs(pdfs[0], work / "pages", env)
        if not pages:
            raise ToolError("sandbox.raster_failed", "文档没有可显示的内容页")
        return pages[:MAX_PAGES]
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def preview_office_payload(filename: str, document: bytes) -> dict[str, object]:
    pages = await render_office_pages(filename, document)
    return {
        "ok": True,
        "page_count": len(pages),
        "pages": [base64.b64encode(page).decode("ascii") for page in pages],
    }


async def open_office_pages(*, kind: str, filename: str, document: bytes) -> OfficePages:
    resolved = resolve_kind(filename, kind)
    safe_name = Path(filename or "document.docx").name or "document.docx"
    pages = await render_office_pages(safe_name, document)
    return OfficePages(kind=resolved, filename=safe_name, pages=pages)
