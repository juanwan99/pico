import pytest
from sandbox_worker.runtime import SandboxRuntime


class FakeSurface:
    def __init__(self, url: str, title: str, h1: str = ""):
        self.url = url
        self._title = title
        self._h1 = h1 or title
        self.png = b"\x89PNG\r\n\x1a\n" + b"x" * 40
        self.closed = False

    async def title(self) -> str:
        return self._title

    async def h1(self) -> str:
        return self._h1

    async def screenshot_png(self) -> bytes:
        return self.png

    async def click(self, x: int, y: int) -> None:
        return None

    async def type_text(self, text: str, *, password: bool) -> None:
        return None

    async def close(self) -> None:
        self.closed = True

    async def render(self, names) -> None:
        self.names = names


@pytest.mark.asyncio
async def test_same_desk_keeps_browser_when_opening_writer():
    browser = FakeSurface("https://example.com/", "Example Domain", "Example Domain")
    writer = FakeSurface("sandbox://writer/notes.docx", "LibreOffice Writer · notes.docx")

    async def open_browser(url: str):
        _ = url
        return browser

    async def open_office(*, kind: str, filename: str, document: bytes):
        _ = (kind, filename, document)
        return writer

    runtime = SandboxRuntime(open_browser=open_browser)
    import sandbox_worker.runtime as runtime_mod

    async def open_files(names):
        surface = FakeSurface("sandbox://files", "文件")
        surface.names = names
        return surface

    runtime_mod.open_office = open_office  # type: ignore[attr-defined]
    runtime_mod.open_files_surface = open_files  # type: ignore[attr-defined]

    first = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="r1",
        url="https://example.com/",
    )
    sid = first["session_id"]
    second = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="r1",
        kind="writer",
        filename="notes.docx",
        document=b"PK",
    )
    assert second["session_id"] == sid
    kinds = [w["kind"] for w in second["windows"]]
    assert "browser" in kinds
    assert "writer" in kinds
    assert second["kind"] == "writer"

    sess = runtime.require_owner(sid, school_id="sch", membership_id="mem")
    back = await runtime.focus(sess, kind="browser")
    assert back["kind"] == "browser"
    assert back["title"] == "Example Domain"
    assert browser.closed is False
    assert "files" in [w["kind"] for w in second["windows"]]
    assert any(f["name"] == "notes.docx" for f in second.get("files") or [])


@pytest.mark.asyncio
async def test_opening_new_docx_replaces_writer_and_keeps_tree():
    first_doc = FakeSurface("sandbox://writer/old.docx", "LibreOffice Writer · old.docx")
    first_doc.filename = "old.docx"
    second_doc = FakeSurface("sandbox://writer/new.docx", "LibreOffice Writer · new.docx")
    second_doc.filename = "new.docx"
    docs = [first_doc, second_doc]

    async def open_browser(url: str):
        raise AssertionError(url)

    async def open_office(*, kind: str, filename: str, document: bytes):
        _ = (kind, document)
        surface = docs.pop(0)
        surface.filename = filename
        return surface

    runtime = SandboxRuntime(open_browser=open_browser)
    import sandbox_worker.runtime as runtime_mod

    async def open_files(names):
        surface = FakeSurface("sandbox://files", "文件")
        surface.names = names
        return surface

    runtime_mod.open_office = open_office  # type: ignore[attr-defined]
    runtime_mod.open_files_surface = open_files  # type: ignore[attr-defined]

    first = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="r2",
        kind="writer",
        filename="old.docx",
        document=b"PK-old",
    )
    second = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="r2",
        kind="writer",
        filename="new.docx",
        document=b"PK-new",
    )
    assert second["session_id"] == first["session_id"]
    assert second["title"] == "LibreOffice Writer · new.docx"
    names = [f["name"] for f in second.get("files") or []]
    assert "old.docx" in names
    assert "new.docx" in names
    assert first_doc.closed is True


@pytest.mark.asyncio
async def test_files_surface_raster_shows_unique_name():
    from sandbox_worker.files import listing_png, open_files_surface

    unique = "night-p3-unique.docx"
    png = listing_png([unique])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert unique.encode("ascii") in png
    surface = await open_files_surface([unique])
    shot = await surface.screenshot_png()
    assert unique.encode("ascii") in shot
    assert await surface.h1() == "工作区文件"
