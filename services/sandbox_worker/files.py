"""Sandbox file-manager window. Lists isolation-dir names on the sandbox screen.

Raster is in-process (no second Chromium). Unique ASCII filenames stay readable
on the screenshot. React also overlays the same names when this window is focused.
"""

from __future__ import annotations

from pathlib import Path

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s2 import (
    PNG_MAGIC,
    _draw_text,
    _fill_rect,
    encode_rgb_png,
)

from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_WIDTH

FILES_ENGINE = "sandbox-files"


def listing_png(names: list[str]) -> bytes:
    width, height = VIEWPORT_WIDTH, VIEWPORT_HEIGHT
    buf = bytearray([250, 250, 250] * width * height)
    _fill_rect(buf, width, 0, 0, width, 44, (26, 26, 26))
    _draw_text(buf, width, 16, 14, "Workspace files", (255, 255, 255), scale=2)
    y = 60
    if not names:
        _draw_text(buf, width, 16, y, "(empty)", (136, 136, 136), scale=2)
    else:
        for name in names[:18]:
            _draw_text(
                buf,
                width,
                16,
                y,
                name,
                (17, 17, 17),
                scale=2,
                max_width=width - 32,
            )
            y += 18
            if y > height - 20:
                break
    png = encode_rgb_png(
        width,
        height,
        bytes(buf),
        text_chunks={"files": ",".join(names)[:200]},
    )
    if not png.startswith(PNG_MAGIC):
        raise ToolError("sandbox.raster_failed", "文件窗口截图失败")
    return png


class FilesSurface:
    def __init__(self, names: list[str]) -> None:
        self.names = list(names)
        self._png = listing_png(self.names)

    @property
    def url(self) -> str:
        return "sandbox://files"

    async def title(self) -> str:
        return "文件"

    async def h1(self) -> str:
        return "工作区文件"

    async def describe_inputs(self) -> dict[str, bool]:
        return {"has_text_input": False, "has_password_input": False}

    async def render(self, names: list[str]) -> None:
        self.names = list(names)
        self._png = listing_png(self.names)

    async def screenshot_png(self) -> bytes:
        return self._png

    async def click(self, x: int, y: int) -> None:
        _ = (x, y)

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = (text, password)

    async def close(self) -> None:
        return None


async def open_files_surface(names: list[str]) -> FilesSurface:
    return FilesSurface(names)


def list_workspace_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    names: list[str] = []
    for path in sorted(root.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            names.append(path.name)
    return names
