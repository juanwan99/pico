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

    runtime_mod.open_office = open_office  # type: ignore[attr-defined]

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
