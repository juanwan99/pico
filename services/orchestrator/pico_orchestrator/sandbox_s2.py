"""S2 same-run HTML raster: real PNG bytes, isolated process, no product-port Chrome.

Extends S1 inspect. See docs/SANDBOX-S2.md.
Never fetches public/intranet URLs. Raster failure must not break title/h1.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import struct
import sys
import zlib
from typing import Any

from pico_orchestrator.sandbox_s1 import (
    EXEC_TIMEOUT_S,
    MAX_CONTENT_BYTES,
    extract_title_h1,
)

logger = logging.getLogger(__name__)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
RASTER_WIDTH = 720
RASTER_HEIGHT = 400
_VISIBLE_TAG_RE = __import__("re").compile(
    r"(?is)<(script|style|noscript)[^>]*>.*?</\1>|<[^>]+>"
)
_WS_RE = __import__("re").compile(r"\s+")


def visible_text(html: str, *, limit: int = 800) -> str:
    stripped = _VISIBLE_TAG_RE.sub(" ", html or "")
    text = _WS_RE.sub(" ", stripped).strip()
    return text[:limit]


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def encode_rgb_png(
    width: int,
    height: int,
    rgb: bytes,
    *,
    text_chunks: dict[str, str] | None = None,
) -> bytes:
    if len(rgb) != width * height * 3:
        raise ValueError("rgb buffer size mismatch")
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    compressed = zlib.compress(bytes(raw), 9)
    out = bytearray(PNG_MAGIC)
    out.extend(
        _png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
    )
    for key, value in (text_chunks or {}).items():
        payload = key.encode("latin-1", errors="replace") + b"\x00" + value.encode(
            "utf-8", errors="replace"
        )[:800]
        out.extend(_png_chunk(b"tEXt", payload))
    out.extend(_png_chunk(b"IDAT", compressed))
    out.extend(_png_chunk(b"IEND", b""))
    return bytes(out)


def _fill_rect(
    buf: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    r, g, b = color
    x0 = max(0, min(width, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, y0)
    y1 = max(0, y1)
    for y in range(y0, y1):
        row = y * width * 3
        for x in range(x0, x1):
            i = row + x * 3
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b


def _blend_pixel(buf: bytearray, width: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= width:
        return
    i = (y * width + x) * 3
    if i + 2 >= len(buf):
        return
    buf[i], buf[i + 1], buf[i + 2] = color


# Compact 5x7 glyphs for ASCII 32-126 (columns, LSB = top).
_GLYPH_5X7: dict[str, tuple[int, int, int, int, int]] = {
    " ": (0, 0, 0, 0, 0),
    "!": (0, 0, 0x5F, 0, 0),
    '"': (0, 7, 0, 7, 0),
    "#": (0x14, 0x7F, 0x14, 0x7F, 0x14),
    "$": (0x24, 0x2A, 0x7F, 0x2A, 0x12),
    "%": (0x23, 0x13, 0x08, 0x64, 0x62),
    "&": (0x36, 0x49, 0x55, 0x22, 0x50),
    "'": (0, 5, 3, 0, 0),
    "(": (0, 0x1C, 0x22, 0x41, 0),
    ")": (0, 0x41, 0x22, 0x1C, 0),
    "*": (0x14, 0x08, 0x3E, 0x08, 0x14),
    "+": (0x08, 0x08, 0x3E, 0x08, 0x08),
    ",": (0, 0x50, 0x30, 0, 0),
    "-": (0x08, 0x08, 0x08, 0x08, 0x08),
    ".": (0, 0x60, 0x60, 0, 0),
    "/": (0x20, 0x10, 0x08, 0x04, 0x02),
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E),
    "1": (0, 0x42, 0x7F, 0x40, 0),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46),
    "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10),
    "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30),
    "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36),
    "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    ":": (0, 0x36, 0x36, 0, 0),
    ";": (0, 0x56, 0x36, 0, 0),
    "<": (0x08, 0x14, 0x22, 0x41, 0),
    "=": (0x14, 0x14, 0x14, 0x14, 0x14),
    ">": (0, 0x41, 0x22, 0x14, 0x08),
    "?": (0x02, 0x01, 0x51, 0x09, 0x06),
    "@": (0x3E, 0x41, 0x5D, 0x59, 0x4E),
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E),
    "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22),
    "D": (0x7F, 0x41, 0x41, 0x22, 0x1C),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41),
    "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "G": (0x3E, 0x41, 0x49, 0x49, 0x7A),
    "H": (0x7F, 0x08, 0x08, 0x08, 0x7F),
    "I": (0, 0x41, 0x7F, 0x41, 0),
    "J": (0x20, 0x40, 0x41, 0x3F, 0x01),
    "K": (0x7F, 0x08, 0x14, 0x22, 0x41),
    "L": (0x7F, 0x40, 0x40, 0x40, 0x40),
    "M": (0x7F, 0x02, 0x0C, 0x02, 0x7F),
    "N": (0x7F, 0x04, 0x08, 0x10, 0x7F),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E),
    "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "Q": (0x3E, 0x41, 0x51, 0x21, 0x5E),
    "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x46, 0x49, 0x49, 0x49, 0x31),
    "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
    "U": (0x3F, 0x40, 0x40, 0x40, 0x3F),
    "V": (0x1F, 0x20, 0x40, 0x20, 0x1F),
    "W": (0x3F, 0x40, 0x38, 0x40, 0x3F),
    "X": (0x63, 0x14, 0x08, 0x14, 0x63),
    "Y": (0x07, 0x08, 0x70, 0x08, 0x07),
    "Z": (0x61, 0x51, 0x49, 0x45, 0x43),
    "[": (0, 0x7F, 0x41, 0x41, 0),
    "\\": (0x02, 0x04, 0x08, 0x10, 0x20),
    "]": (0, 0x41, 0x41, 0x7F, 0),
    "^": (0x04, 0x02, 0x01, 0x02, 0x04),
    "_": (0x40, 0x40, 0x40, 0x40, 0x40),
    "`": (0, 1, 2, 4, 0),
    "a": (0x20, 0x54, 0x54, 0x54, 0x78),
    "b": (0x7F, 0x48, 0x44, 0x44, 0x38),
    "c": (0x38, 0x44, 0x44, 0x44, 0x20),
    "d": (0x38, 0x44, 0x44, 0x48, 0x7F),
    "e": (0x38, 0x54, 0x54, 0x54, 0x18),
    "f": (0x08, 0x7E, 0x09, 0x01, 0x02),
    "g": (0x0C, 0x52, 0x52, 0x52, 0x3E),
    "h": (0x7F, 0x08, 0x04, 0x04, 0x78),
    "i": (0, 0x44, 0x7D, 0x40, 0),
    "j": (0x20, 0x40, 0x44, 0x3D, 0),
    "k": (0x7F, 0x10, 0x28, 0x44, 0),
    "l": (0, 0x41, 0x7F, 0x40, 0),
    "m": (0x7C, 0x04, 0x18, 0x04, 0x78),
    "n": (0x7C, 0x08, 0x04, 0x04, 0x78),
    "o": (0x38, 0x44, 0x44, 0x44, 0x38),
    "p": (0x7C, 0x14, 0x14, 0x14, 0x08),
    "q": (0x08, 0x14, 0x14, 0x18, 0x7C),
    "r": (0x7C, 0x08, 0x04, 0x04, 0x08),
    "s": (0x48, 0x54, 0x54, 0x54, 0x20),
    "t": (0x04, 0x3F, 0x44, 0x40, 0x20),
    "u": (0x3C, 0x40, 0x40, 0x20, 0x7C),
    "v": (0x1C, 0x20, 0x40, 0x20, 0x1C),
    "w": (0x3C, 0x40, 0x30, 0x40, 0x3C),
    "x": (0x44, 0x28, 0x10, 0x28, 0x44),
    "y": (0x0C, 0x50, 0x50, 0x50, 0x3C),
    "z": (0x44, 0x64, 0x54, 0x4C, 0x44),
}


def _draw_char(
    buf: bytearray,
    width: int,
    x: int,
    y: int,
    ch: str,
    color: tuple[int, int, int],
    scale: int = 2,
) -> int:
    glyph = _GLYPH_5X7.get(ch)
    if glyph is None:
        code = ord(ch)
        box_w = 8 * scale
        for gy in range(8 * scale):
            for gx in range(box_w):
                bit = ((code >> ((gx // scale) % 8)) ^ (gy // scale)) & 1
                if bit:
                    _blend_pixel(buf, width, x + gx, y + gy, color)
        return box_w + scale
    col_w = scale
    for cx, col in enumerate(glyph):
        for row in range(7):
            if col & (1 << row):
                for sy in range(scale):
                    for sx in range(scale):
                        _blend_pixel(
                            buf, width, x + cx * col_w + sx, y + row * scale + sy, color
                        )
    return 5 * scale + scale


def _draw_text(
    buf: bytearray,
    width: int,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    *,
    scale: int = 2,
    max_width: int | None = None,
) -> None:
    cursor = x
    limit = width if max_width is None else min(width, x + max_width)
    for ch in text:
        if cursor >= limit - 6:
            break
        cursor += _draw_char(buf, width, cursor, y, ch, color, scale=scale)


def _raster_stdlib(html: str) -> bytes:
    title, h1 = extract_title_h1(html)
    body = visible_text(html)
    width, height = RASTER_WIDTH, RASTER_HEIGHT
    buf = bytearray([255, 255, 255] * width * height)
    digest = hashlib.sha256((html or "").encode("utf-8", errors="replace")).digest()
    # Subtle uniqueness stripe so two pages cannot share identical pixels.
    for i, byte in enumerate(digest[: width // 8]):
        _fill_rect(buf, width, i * 8, height - 6, i * 8 + 8, height, (byte, 80, 160))
    _fill_rect(buf, width, 0, 0, width, 44, (36, 36, 40))
    _fill_rect(buf, width, 12, 14, 28, 30, (80, 200, 120))
    _draw_text(
        buf,
        width,
        36,
        14,
        "file://workspace/this-run.html",
        (220, 220, 224),
        scale=2,
        max_width=width - 48,
    )
    _fill_rect(buf, width, 0, 44, width, 92, (245, 246, 248))
    _draw_text(
        buf,
        width,
        16,
        58,
        f"title: {title or '(none)'}",
        (20, 20, 24),
        scale=2,
        max_width=width - 32,
    )
    _draw_text(
        buf,
        width,
        16,
        110,
        f"h1: {h1 or '(none)'}",
        (16, 16, 20),
        scale=3,
        max_width=width - 32,
    )
    y = 170
    for chunk_start in range(0, min(len(body), 240), 80):
        _draw_text(
            buf,
            width,
            16,
            y,
            body[chunk_start : chunk_start + 80],
            (40, 40, 48),
            scale=2,
            max_width=width - 32,
        )
        y += 28
    _draw_text(
        buf,
        width,
        16,
        height - 36,
        "Pico sandbox inspect raster",
        (110, 110, 120),
        scale=2,
        max_width=width - 32,
    )
    return encode_rgb_png(
        width,
        height,
        bytes(buf),
        text_chunks={
            "Title": (title or "")[:180],
            "H1": (h1 or "")[:180],
            "Software": "pico-sandbox-s2",
        },
    )


def _raster_pillow(html: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    title, h1 = extract_title_h1(html)
    body = visible_text(html, limit=500)
    img = Image.new("RGB", (RASTER_WIDTH, RASTER_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for candidate in (
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.isfile(candidate):
            try:
                font = ImageFont.truetype(candidate, 18)
                break
            except OSError:
                continue
    draw.rectangle((0, 0, RASTER_WIDTH, 44), fill=(36, 36, 40))
    draw.text((16, 12), "file://workspace/this-run.html", fill=(220, 220, 224), font=font)
    draw.rectangle((0, 44, RASTER_WIDTH, 92), fill=(245, 246, 248))
    draw.text((16, 56), f"title: {title or '(none)'}", fill=(20, 20, 24), font=font)
    draw.text((16, 110), h1 or "(no h1)", fill=(16, 16, 20), font=font)
    draw.multiline_text((16, 160), body or "(empty)", fill=(40, 40, 48), font=font, spacing=6)
    draw.text(
        (16, RASTER_HEIGHT - 28),
        "Pico sandbox inspect raster",
        fill=(110, 110, 120),
        font=font,
    )
    digest = hashlib.sha256((html or "").encode("utf-8", errors="replace")).digest()
    for i, byte in enumerate(digest[: RASTER_WIDTH // 8]):
        draw.rectangle(
            (i * 8, RASTER_HEIGHT - 6, i * 8 + 8, RASTER_HEIGHT),
            fill=(byte, 80, 160),
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png = buf.getvalue()
    if not png.startswith(PNG_MAGIC):
        raise ValueError("pillow did not emit PNG")
    return png


def raster_html_to_png(html: str) -> bytes:
    """Return a real PNG of this HTML. Never fetches a URL."""
    text = (html or "")[:MAX_CONTENT_BYTES]
    try:
        png = _raster_pillow(text)
        if png.startswith(PNG_MAGIC) and len(png) > 64:
            return png
    except Exception:
        logger.debug("pillow raster unavailable; using stdlib encoder", exc_info=True)
    png = _raster_stdlib(text)
    if not png.startswith(PNG_MAGIC):
        raise ValueError("raster encoder produced non-PNG")
    return png


def raster_meta_from_write(row: dict[str, Any], *, byte_size: int) -> dict[str, Any]:
    artifact_id = str(row.get("artifact_id") or row.get("id") or "").strip()
    path = str(row.get("download_path") or "").strip()
    if not path and artifact_id:
        path = f"/v1/artifacts/{artifact_id}/content"
    block = {
        "artifact_id": artifact_id,
        "download_path": path,
        "mime": "image/png",
        "byte_size": int(row.get("byte_size") or row.get("size") or byte_size),
        "kind": "png",
    }
    return {"screenshot": block, "raster": dict(block)}


async def raster_html_isolated(html: str) -> bytes | None:
    """Isolated subprocess raster; falls back in-process. Never raises."""
    text = (html or "")[:MAX_CONTENT_BYTES]
    env = os.environ.copy()
    try:
        import pico_orchestrator as _pkg

        root = os.path.dirname(os.path.dirname(os.path.abspath(_pkg.__file__)))
        env["PYTHONPATH"] = os.pathsep.join(
            [root, env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
    except Exception:  # noqa: BLE001 — subprocess optional
        root = ""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pico_orchestrator.sandbox_s2",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        out, _err = await asyncio.wait_for(
            proc.communicate(text.encode("utf-8")),
            timeout=EXEC_TIMEOUT_S,
        )
        if proc.returncode == 0 and out.startswith(PNG_MAGIC) and len(out) > 64:
            return out
    except Exception:
        logger.debug("isolated raster subprocess skipped", exc_info=True)
    try:
        png = await asyncio.to_thread(raster_html_to_png, text)
        if png.startswith(PNG_MAGIC) and len(png) > 64:
            return png
    except Exception:
        logger.debug("in-process raster skipped", exc_info=True)
    return None


def main() -> None:
    raw = sys.stdin.buffer.read()
    html = raw.decode("utf-8", errors="replace")[:MAX_CONTENT_BYTES]
    sys.stdout.buffer.write(raster_html_to_png(html))


if __name__ == "__main__":
    main()
