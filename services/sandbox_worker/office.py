"""LibreOffice Writer/Calc/Impress on a private Xvfb display.

This is the sandbox word-processor window. Not PDF, not HTML conversion,
not host WPS. Screenshots are the X11 root (the program window).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import tempfile
from pathlib import Path

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.legacy import convert_target_from_name

from sandbox_worker.browser import PNG_MAGIC

logger = logging.getLogger(__name__)

OFFICE_ENGINE = "libreoffice-writer"
DESKTOP_W = 1280
DESKTOP_H = 800
_DOC_ROOT = Path(os.environ.get("PICO_SANDBOX_DOC_ROOT") or "/tmp/pico-sandbox-docs")

KIND_FLAGS = {
    "writer": "--writer",
    "calc": "--calc",
    "impress": "--impress",
}

KIND_LABEL = {
    "writer": "LibreOffice Writer",
    "calc": "LibreOffice Calc",
    "impress": "LibreOffice Impress",
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
        "沙箱未安装 LibreOffice Writer，无法打开 Word 本身。",
    )


def _next_display() -> str:
    # 91–189 keeps us off the host :0 / CI :99 when those exist.
    base = int(os.environ.get("PICO_SANDBOX_DISPLAY_BASE") or "91")
    slot = int.from_bytes(os.urandom(2), "big") % 90
    return f":{base + slot}"


class OfficeDesktop:
    """One Xvfb + one soffice process. Screenshot is the desktop root."""

    def __init__(
        self,
        *,
        kind: str,
        filename: str,
        doc_path: Path,
        display: str,
        xvfb: asyncio.subprocess.Process,
        office: asyncio.subprocess.Process,
    ) -> None:
        self.kind = kind
        self.filename = filename
        self.doc_path = doc_path
        self.display = display
        self._xvfb = xvfb
        self._office = office

    @property
    def url(self) -> str:
        return f"sandbox://{self.kind}/{self.filename}"

    async def title(self) -> str:
        return f"{KIND_LABEL.get(self.kind, self.kind)} · {self.filename}"

    async def h1(self) -> str:
        return self.filename

    async def describe_inputs(self) -> dict[str, bool]:
        # Xvfb desktop — not a DOM login form.
        return {"has_text_input": False, "has_password_input": False}

    async def screenshot_png(self) -> bytes:
        scrot = shutil.which("scrot")
        if not scrot:
            raise ToolError("sandbox.raster_failed", "沙箱缺少 scrot，无法截取字处理窗口")
        fd, raw_path = tempfile.mkstemp(prefix="sbox_off_", suffix=".png")
        os.close(fd)
        dest = Path(raw_path)
        try:
            proc = await asyncio.create_subprocess_exec(
                scrot,
                "-z",
                "-o",
                str(dest),
                env={**os.environ, "DISPLAY": self.display, "HOME": os.environ.get("HOME") or "/tmp"},
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=8)
            png = dest.read_bytes()
            if not png.startswith(PNG_MAGIC):
                raise ToolError("sandbox.raster_failed", "字处理窗口截图失败")
            return png
        except TimeoutError as exc:
            raise ToolError("sandbox.raster_failed", "字处理窗口截图超时") from exc
        finally:
            dest.unlink(missing_ok=True)

    async def click(self, x: int, y: int) -> None:
        xdotool = shutil.which("xdotool")
        if not xdotool:
            return
        proc = await asyncio.create_subprocess_exec(
            xdotool,
            "mousemove",
            "--sync",
            str(int(x)),
            str(int(y)),
            "click",
            "1",
            env={**os.environ, "DISPLAY": self.display},
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=4)

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = password
        xdotool = shutil.which("xdotool")
        if not xdotool or not text:
            return
        proc = await asyncio.create_subprocess_exec(
            xdotool,
            "type",
            "--delay",
            "12",
            "--",
            text,
            env={**os.environ, "DISPLAY": self.display},
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=20)

    async def close(self) -> None:
        for proc in (self._office, self._xvfb):
            if proc.returncode is not None:
                continue
            try:
                proc.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except TimeoutError:
                    proc.kill()
            except ProcessLookupError:
                pass
        shutil.rmtree(self.doc_path.parent, ignore_errors=True)


async def _spawn(cmd: list[str], *, env: dict[str, str]) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )


async def _wait_visible(display: str, timeout_s: float = 28.0) -> None:
    xdotool = shutil.which("xdotool")
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if xdotool:
            proc = await asyncio.create_subprocess_exec(
                xdotool,
                "search",
                "--onlyvisible",
                "--class",
                "soffice",
                env={**os.environ, "DISPLAY": display},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await proc.communicate()
            if proc.returncode == 0 and (out or b"").strip():
                await asyncio.sleep(0.8)
                return
        await asyncio.sleep(0.4)
    # Still proceed: first-start Writer may be slow; screenshot may already show chrome.


_CONVERT_FILTER = {
    ".docx": "docx:Office Open XML Text",
    ".pptx": "pptx:Impress Office Open XML",
    ".xlsx": "xlsx:Calc Office Open XML",
}
_CONVERT_TIMEOUT_S = 45.0


def convert_target(filename: str) -> str | None:
    return convert_target_from_name(filename)


async def convert_legacy_office(*, filename: str, document: bytes) -> bytes:
    """Headless soffice OLE → OOXML. Not a Pico office kernel."""
    if not document:
        raise ToolError("tool.invalid_arguments", "文档内容为空")
    if len(document) > 12 * 1024 * 1024:
        raise ToolError("tool.invalid_arguments", "文档超过 12MB，沙箱拒收")
    target = convert_target(filename)
    if target is None:
        raise ToolError("tool.invalid_arguments", "不是旧版 .doc/.ppt/.xls")
    soffice = soffice_bin()
    safe_name = Path(filename or f"document{target}").name or f"document{target}"
    _DOC_ROOT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sbox_conv_", dir=str(_DOC_ROOT)))
    src = work / safe_name
    out_dir = work / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = work / "lo-profile"
    profile.mkdir(parents=True, exist_ok=True)
    src.write_bytes(document)
    env = {
        **os.environ,
        "HOME": str(work),
        "LANG": os.environ.get("LANG") or "C.UTF-8",
        "SAL_USE_VCLPLUGIN": "gen",
    }
    filter_name = _CONVERT_FILTER[target]
    try:
        proc = await asyncio.create_subprocess_exec(
            soffice,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--nologo",
            "--norestore",
            "--nolockcheck",
            "--nofirststartwizard",
            "--convert-to",
            filter_name,
            "--outdir",
            str(out_dir),
            str(src),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=_CONVERT_TIMEOUT_S)
        except TimeoutError as exc:
            if proc.returncode is None:
                proc.kill()
            raise ToolError("sandbox.office_unavailable", "旧版文档转换超时") from exc
        produced = next(out_dir.glob(f"*{target}"), None)
        if proc.returncode != 0 or produced is None or not produced.is_file():
            raise ToolError("sandbox.office_unavailable", "旧版文档转不开")
        converted = produced.read_bytes()
        if not converted or converted[:2] != b"PK":
            raise ToolError("sandbox.office_unavailable", "旧版文档转不开")
        return converted
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def open_office(*, kind: str, filename: str, document: bytes) -> OfficeDesktop:
    if not document:
        raise ToolError("tool.invalid_arguments", "文档内容为空")
    if len(document) > 12 * 1024 * 1024:
        raise ToolError("tool.invalid_arguments", "文档超过 12MB，沙箱拒收")
    soffice = soffice_bin()
    xvfb = shutil.which("Xvfb")
    if not xvfb:
        raise ToolError("sandbox.office_unavailable", "沙箱未安装 Xvfb，无法显示字处理窗口")
    resolved = resolve_kind(filename, kind)
    flag = KIND_FLAGS[resolved]
    safe_name = Path(filename or "document.docx").name or "document.docx"
    display = _next_display()
    _DOC_ROOT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sbox_doc_", dir=str(_DOC_ROOT)))
    doc_path = work / safe_name
    doc_path.write_bytes(document)

    profile = work / "lo-profile"
    profile.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "DISPLAY": display,
        "HOME": str(work),
        "LANG": os.environ.get("LANG") or "C.UTF-8",
        "SAL_USE_VCLPLUGIN": "gen",
    }
    xvfb_proc = await _spawn(
        [xvfb, display, "-screen", "0", f"{DESKTOP_W}x{DESKTOP_H}x24", "-ac", "-nolisten", "tcp"],
        env=env,
    )
    await asyncio.sleep(0.25)
    if xvfb_proc.returncode is not None:
        shutil.rmtree(work, ignore_errors=True)
        raise ToolError("sandbox.office_unavailable", "沙箱桌面未能启动")
    office_proc = await _spawn(
        [
            soffice,
            f"-env:UserInstallation=file://{profile}",
            "--nologo",
            "--norestore",
            "--nolockcheck",
            "--nofirststartwizard",
            flag,
            str(doc_path),
        ],
        env=env,
    )
    try:
        await _wait_visible(display)
        if office_proc.returncode is not None:
            raise ToolError("sandbox.office_unavailable", "LibreOffice 未能打开该文档")
    except Exception:
        for proc in (office_proc, xvfb_proc):
            if proc.returncode is None:
                proc.kill()
        shutil.rmtree(work, ignore_errors=True)
        raise
    return OfficeDesktop(
        kind=resolved,
        filename=safe_name,
        doc_path=doc_path,
        display=display,
        xvfb=xvfb_proc,
        office=office_proc,
    )
