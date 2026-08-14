"""Sandbox file-manager window. Lists isolation-dir files on the sandbox screen."""

from __future__ import annotations

import html
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from sandbox_worker.browser import PNG_MAGIC, open_html_page

FILES_ENGINE = "sandbox-files"


class FilesSurface:
    def __init__(self, page, names: list[str]) -> None:
        self._page = page
        self.names = names

    @property
    def url(self) -> str:
        return "sandbox://files"

    async def title(self) -> str:
        return "文件"

    async def h1(self) -> str:
        return "工作区文件"

    async def render(self, names: list[str]) -> None:
        self.names = names
        await self._page.set_content(_listing_html(names), wait_until="domcontentloaded")

    async def screenshot_png(self) -> bytes:
        raw = await self._page.screenshot(type="png", full_page=False)
        png = bytes(raw)
        if not png.startswith(PNG_MAGIC):
            from pico_orchestrator.gateway import ToolError

            raise ToolError("sandbox.raster_failed", "文件窗口截图失败")
        return png

    async def click(self, x: int, y: int) -> None:
        await self._page.mouse.click(float(x), float(y))

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = (text, password)

    async def close(self) -> None:
        try:
            await self._page.context.close()
        except Exception:
            logger.debug("files window close failed", exc_info=True)


def _listing_html(names: list[str]) -> str:
    if names:
        items = "".join(
            f"<li data-file=\"{html.escape(name)}\" style=\"padding:10px 12px;border-bottom:1px solid #eee;font:14px/1.4 sans-serif\">{html.escape(name)}</li>"
            for name in names
        )
    else:
        items = "<li style=\"padding:16px;color:#888;font:14px sans-serif\">工作区还没有文件</li>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>文件</title></head>
<body style="margin:0;background:#fafafa;color:#111">
<header style="padding:10px 12px;background:#1a1a1a;color:#fff;font:15px sans-serif">工作区文件</header>
<ul style="list-style:none;margin:0;padding:0">{items}</ul>
</body></html>"""


async def open_files_surface(names: list[str]) -> FilesSurface:
    page = await open_html_page(_listing_html(names))
    return FilesSurface(page, names)


def list_workspace_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    names: list[str] = []
    for path in sorted(root.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            names.append(path.name)
    return names
