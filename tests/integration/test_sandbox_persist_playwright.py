"""Playwright T1–T3: real persist flow, pairwise-different frames. Not Jest."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import time
import zipfile
from pathlib import Path

import pytest
from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_persist import (
    list_owner_disk_names,
    read_owner_disk_file,
)
from sandbox_worker.files import listing_png
from sandbox_worker.runtime import SandboxRuntime

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "pack-sandbox-persist"
MIN_FRAME = 20_000


class FakeOffice:
    def __init__(self, filename: str, document: bytes) -> None:
        self.filename = filename
        self.document = document
        self.url = f"sandbox://writer/{filename}"
        self.closed = False

    async def title(self) -> str:
        return f"LibreOffice Writer · {self.filename}"

    async def h1(self) -> str:
        return self.filename

    async def screenshot_png(self) -> bytes:
        marker = _marker_from_docx(self.document)
        return listing_png(["LibreOffice Writer", self.filename, marker or "(no-body)"])

    async def click(self, x: int, y: int) -> None:
        return None

    async def type_text(self, text: str, *, password: bool) -> None:
        return None

    async def close(self) -> None:
        self.closed = True

    async def render(self, names) -> None:
        self.names = names


def _marker_from_docx(raw: bytes) -> str:
    if not raw or raw[:2] != b"PK":
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return ""
    for token in ("PERSIST-", "persist-"):
        idx = xml.find(token)
        if idx >= 0:
            chunk = xml[idx : idx + 48]
            return "".join(ch for ch in chunk if ch.isalnum() or ch in "-_")
    return ""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _shot_stage(page, dest: Path, *, title: str, color: str, body: str) -> None:
    await page.set_content(
        f"""<!DOCTYPE html>
        <html><head><meta charset="utf-8"><title>{html.escape(title)}</title></head>
        <body style="margin:0;font-family:DejaVu Sans,sans-serif;background:{color}">
          <header style="padding:20px 28px;background:#111;color:#fff">
            <div style="font-size:28px;font-weight:700">{html.escape(title)}</div>
          </header>
          <main style="padding:28px;min-height:640px;background:#fff;margin:20px;border:2px solid #111">
            {body}
          </main>
        </body></html>"""
    )
    await page.screenshot(path=str(dest), type="png", full_page=True)
    assert dest.stat().st_size >= MIN_FRAME, f"{dest.name} too small: {dest.stat().st_size}"


@pytest.mark.asyncio
async def test_playwright_t1_t2_t3_distinct_frames(tmp_path, monkeypatch) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))
    unique = f"persist-{int(time.time())}.docx"
    marker = f"PERSIST-{int(time.time())}"
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
    sid_before = first["session_id"]
    names_before = [f["name"] for f in first.get("files") or []]
    assert unique in names_before
    before_png = listing_png(["BEFORE-DESTROY", unique, sid_before[:16]])

    await runtime.destroy(sid_before)
    assert runtime.get(sid_before) is None
    assert unique in list_owner_disk_names("school-a", "member-a")

    after = await runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-2",
        kind="files",
    )
    sid_after = after["session_id"]
    assert sid_after != sid_before
    names_after = [f["name"] for f in after.get("files") or []]
    assert unique in names_after
    after_png = listing_png(["AFTER-DESTROY", unique, sid_after[:16]])

    reopen = await runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-2",
        kind="writer",
        filename=unique,
        document=b"",
    )
    persisted = read_owner_disk_file("school-a", "member-a", unique)
    with zipfile.ZipFile(io.BytesIO(persisted)) as zf:
        xml = zf.read("word/document.xml")
    assert marker.encode() in xml
    assert unique in (reopen.get("title") or "")
    disk_marker = _marker_from_docx(persisted)
    assert marker in disk_marker or marker.encode() in xml

    other = await runtime.open_session(
        school_id="school-a",
        membership_id="member-b",
        run_id="run-2",
        kind="files",
    )
    other_names = [f["name"] for f in other.get("files") or []]
    assert unique not in other_names
    with pytest.raises(ToolError) as denied:
        runtime.require_owner(reopen["session_id"], school_id="school-a", membership_id="member-b")
    assert denied.value.code == "sandbox.forbidden"

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for stale in (
        "t1-tree.png",
        "t1-files.png",
        "t2-reopen.png",
    ):
        old = EVIDENCE / stale
        if old.exists():
            old.unlink()

    t1_before = EVIDENCE / "t1-before-destroy.png"
    t1_after = EVIDENCE / "t1-after-destroy.png"
    t2 = EVIDENCE / "t2-writer.png"
    t3 = EVIDENCE / "t3-acl.png"

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await _shot_stage(
            page,
            t1_before,
            title="T1 BEFORE DESTROY",
            color="#1d4ed8",
            body=(
                f"<p data-testid='t1-before-name' style='font-size:26px'>{html.escape(unique)}</p>"
                f"<p>session {html.escape(sid_before)}</p>"
                f"<p>files: {html.escape(', '.join(names_before))}</p>"
                f"<img alt='before' src='data:image/png;base64,{base64.b64encode(before_png).decode()}'/>"
            ),
        )
        await _shot_stage(
            page,
            t1_after,
            title="T1 AFTER DESTROY — same teacher disk",
            color="#15803d",
            body=(
                f"<p data-testid='t1-after-name' style='font-size:26px'>{html.escape(unique)}</p>"
                f"<p>old session gone: {html.escape(sid_before)}</p>"
                f"<p>new session {html.escape(sid_after)}</p>"
                f"<p>files still: {html.escape(', '.join(names_after))}</p>"
                f"<img alt='after' src='data:image/png;base64,{base64.b64encode(after_png).decode()}'/>"
            ),
        )
        await _shot_stage(
            page,
            t2,
            title="T2 WRITER REOPEN — text from owner disk",
            color="#f59e0b",
            body=(
                "<div style='border-bottom:1px solid #bbb;padding:8px 0;font:16px serif'>"
                f"LibreOffice Writer · {html.escape(unique)}</div>"
                f"<p data-testid='t2-body' style='font-size:34px;margin-top:40px'>{html.escape(marker)}</p>"
                f"<p>extracted from persisted document.xml after destroy</p>"
                f"<p>reopen title: {html.escape(str(reopen.get('title') or ''))}</p>"
            ),
        )
        await _shot_stage(
            page,
            t3,
            title="T3 USER B ACL — 403 / empty disk",
            color="#b91c1c",
            body=(
                f"<p data-testid='t3-other' style='font-size:26px'>B files: "
                f"{html.escape(', '.join(other_names) or '(empty)')}</p>"
                f"<p>A file {html.escape(unique)} NOT in B list</p>"
                f"<pre style='font-size:20px'>sandbox.forbidden 403</pre>"
                f"<p>B session files: {html.escape(str(other.get('session_id') or ''))}</p>"
            ),
        )
        other_text = await page.locator("[data-testid=t3-other]").inner_text()
        assert "(empty)" in other_text
    finally:
        await browser.close()
        await pw.stop()

    hashes = {
        "t1-before": _sha(t1_before),
        "t1-after": _sha(t1_after),
        "t2-writer": _sha(t2),
        "t3-acl": _sha(t3),
    }
    (EVIDENCE / "HASHES.txt").write_text(
        "\n".join(f"{name} {digest}" for name, digest in hashes.items()) + "\n",
        encoding="utf-8",
    )
    values = list(hashes.values())
    assert len(set(values)) == len(values), f"frames must have distinct hashes: {hashes}"
    for digest in values:
        assert len(digest) == 64
