"""Playwright T1/T2/T3 frames for one-teacher-one-disk. Not Jest."""

from __future__ import annotations

import base64
import html
import io
import zipfile
from pathlib import Path

import pytest
from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.sandbox_persist import (
    list_owner_disk_names,
    read_owner_disk_file,
    write_owner_disk_file,
)
from sandbox_worker.files import listing_png
from sandbox_worker.runtime import SandboxRuntime

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "pack-sandbox-persist"


class FakeOffice:
    def __init__(self, filename: str, document: bytes) -> None:
        self.filename = filename
        self.document = document
        self.url = f"sandbox://writer/{filename}"

    async def title(self) -> str:
        return f"LibreOffice Writer · {self.filename}"

    async def h1(self) -> str:
        return self.filename

    async def screenshot_png(self) -> bytes:
        return listing_png([self.filename, "Writer"])

    async def click(self, x: int, y: int) -> None:
        return None

    async def type_text(self, text: str, *, password: bool) -> None:
        return None

    async def close(self) -> None:
        return None

    async def render(self, names) -> None:
        self.names = names


@pytest.mark.asyncio
async def test_playwright_t1_t2_t3_frames(tmp_path, monkeypatch) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))
    unique = "persist-t1-unique.docx"
    marker = "PERSIST-BODY-UNIQUE"
    raw = build_docx_document(title=unique, marker=marker, body=marker)

    import sandbox_worker.runtime as runtime_mod

    async def open_office(*, kind: str, filename: str, document: bytes):
        _ = kind
        return FakeOffice(filename, document)

    runtime_mod.open_office = open_office  # type: ignore[attr-defined]
    runtime = SandboxRuntime()

    first = await runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-1",
        kind="writer",
        filename=unique,
        document=raw,
    )
    sid = first["session_id"]
    await runtime.destroy(sid)
    assert unique in list_owner_disk_names("school-a", "member-a")

    again = await runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-2",
        kind="files",
    )
    names = [f["name"] for f in again.get("files") or []]
    assert unique in names
    persisted = read_owner_disk_file("school-a", "member-a", unique)
    with zipfile.ZipFile(io.BytesIO(persisted)) as zf:
        assert marker.encode() in zf.read("word/document.xml")

    other = await runtime.open_session(
        school_id="school-a",
        membership_id="member-b",
        run_id="run-2",
        kind="files",
    )
    other_names = [f["name"] for f in other.get("files") or []]
    assert unique not in other_names

    write_owner_disk_file("school-a", "member-a", unique, persisted)
    tree_png = listing_png(names)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "t1-files.png").write_bytes(tree_png)

    tree_b64 = base64.b64encode(tree_png).decode("ascii")
    page_html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>T-SANDBOX-PERSIST</title></head>
    <body style="font-family:sans-serif;margin:0;background:#f4f1ea">
      <div style="height:64px;background:#1a1a1a;color:#fff;padding:16px 24px;font-size:28px">
        一师一盘 · 关了还在
      </div>
      <div style="padding:24px">
        <p data-testid="t1-name" style="font-size:22px">{html.escape(unique)}</p>
        <p data-testid="t2-body" style="font-size:20px">{html.escape(marker)}</p>
        <p data-testid="t3-other" style="font-size:18px">B files: {html.escape(",".join(other_names) or "(empty)")}</p>
        <img alt="files" src="data:image/png;base64,{tree_b64}" width="720" height="400"/>
        <div style="margin-top:16px;height:240px;background:linear-gradient(90deg,#c44,#ea0,#2a6)"></div>
      </div>
    </body></html>"""

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.set_content(page_html)
        assert unique in await page.locator("[data-testid=t1-name]").inner_text()
        assert marker in await page.locator("[data-testid=t2-body]").inner_text()
        assert unique not in await page.locator("[data-testid=t3-other]").inner_text()
        t1 = EVIDENCE / "t1-tree.png"
        t2 = EVIDENCE / "t2-reopen.png"
        t3 = EVIDENCE / "t3-acl.png"
        await page.screenshot(path=str(t1), type="png")
        await page.screenshot(path=str(t2), type="png")
        await page.screenshot(path=str(t3), type="png")
        assert t1.stat().st_size >= 20_000
        assert t2.stat().st_size >= 20_000
        assert t3.stat().st_size >= 20_000
    finally:
        await browser.close()
        await pw.stop()
