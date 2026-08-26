"""Content-only office pages. No Writer/Impress chrome."""

from __future__ import annotations

from pathlib import Path

from sandbox_worker.browser import PNG_MAGIC
from sandbox_worker.office import resolve_kind
from sandbox_worker.office_preview import OfficePages, _read_pngs


def _tiny_png(path: Path) -> None:
    path.write_bytes(
        PNG_MAGIC
        + b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        + b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
        + b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_resolve_kind_still_maps_office_names() -> None:
    assert resolve_kind("a.pptx", "") == "impress"
    assert resolve_kind("a.docx", "") == "writer"


def test_read_pngs_skips_non_png(tmp_path: Path) -> None:
    good = tmp_path / "page-1.png"
    bad = tmp_path / "page-2.png"
    _tiny_png(good)
    bad.write_bytes(b"not-a-png")
    pages = _read_pngs([good, bad])
    assert len(pages) == 1
    assert pages[0].startswith(PNG_MAGIC)


def test_office_pages_click_changes_page() -> None:
    one = PNG_MAGIC + b"one"
    two = PNG_MAGIC + b"two"
    surface = OfficePages(kind="impress", filename="课.pptx", pages=[one, two])

    async def _run() -> None:
        assert await surface.screenshot_png() == one
        await surface.click(1000, 10)
        assert await surface.screenshot_png() == two
        await surface.click(100, 10)
        assert await surface.screenshot_png() == one

    import asyncio

    asyncio.run(_run())
    assert surface.url == "sandbox://impress/课.pptx"
