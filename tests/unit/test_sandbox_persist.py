from __future__ import annotations

from pathlib import Path

import pytest
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_persist import (
    clear_owner_disk,
    list_owner_disk_names,
    owner_disk_dir,
    read_owner_disk_file,
    write_owner_disk_file,
)
from sandbox_worker.files import listing_png
from sandbox_worker.runtime import SandboxRuntime


class FakeSurface:
    def __init__(self, url: str, title: str, h1: str = ""):
        self.url = url
        self._title = title
        self._h1 = h1 or title
        self.filename = Path(url).name
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


@pytest.fixture()
def disk(tmp_path, monkeypatch):
    root = tmp_path / "disks"
    monkeypatch.setenv("PICO_SANDBOX_DISK", str(root))
    return root


def test_owner_disks_do_not_overlap(disk) -> None:
    a = owner_disk_dir("school-a", "member-a")
    b = owner_disk_dir("school-a", "member-b")
    c = owner_disk_dir("school-b", "member-a")
    assert a != b != c
    assert a.parts[-2:] == ("school-a", "member-a")
    assert len(a.relative_to(disk).parts) == 2
    write_owner_disk_file("school-a", "member-a", "notes.docx", b"AAA")
    write_owner_disk_file("school-a", "member-b", "notes.docx", b"BBB")
    assert read_owner_disk_file("school-a", "member-a", "notes.docx") == b"AAA"
    assert read_owner_disk_file("school-a", "member-b", "notes.docx") == b"BBB"
    assert "notes.docx" not in list_owner_disk_names("school-b", "member-a")


def test_quota_is_human_and_per_teacher(disk, monkeypatch) -> None:
    monkeypatch.setenv("PICO_SANDBOX_DISK_QUOTA_BYTES", "40")
    write_owner_disk_file("sch", "mem", "a.docx", b"x" * 20)
    with pytest.raises(ToolError) as denied:
        write_owner_disk_file("sch", "mem", "b.docx", b"y" * 30)
    assert denied.value.code == "sandbox.quota"
    assert "2GB" in denied.value.message or "已满" in denied.value.message
    write_owner_disk_file("sch", "other", "b.docx", b"y" * 30)


def test_clear_is_explicit(disk) -> None:
    write_owner_disk_file("sch", "mem", "keep.docx", b"PK")
    assert list_owner_disk_names("sch", "mem") == ["keep.docx"]
    out = clear_owner_disk("sch", "mem")
    assert out["cleared"] is True
    assert list_owner_disk_names("sch", "mem") == []


@pytest.mark.asyncio
async def test_destroy_keeps_disk_and_new_run_sees_file(disk, monkeypatch) -> None:
    unique = "persist-t1-unique.docx"
    marker = b"PERSIST-BODY-UNIQUE"

    async def open_office(*, kind: str, filename: str, document: bytes):
        surface = FakeSurface(f"sandbox://{kind}/{filename}", f"LibreOffice Writer · {filename}")
        surface.filename = filename
        surface.payload = document
        return surface

    async def open_files(names):
        surface = FakeSurface("sandbox://files", "文件")
        surface.names = names
        return surface

    import sandbox_worker.runtime as runtime_mod

    runtime_mod.open_office = open_office  # type: ignore[attr-defined]
    runtime_mod.open_files_surface = open_files  # type: ignore[attr-defined]
    runtime = SandboxRuntime()

    first = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="run-old",
        kind="writer",
        filename=unique,
        document=marker,
    )
    sid = first["session_id"]
    assert any(f["name"] == unique for f in first["files"])
    await runtime.destroy(sid)
    assert runtime.get(sid) is None
    assert unique in list_owner_disk_names("sch", "mem")
    assert read_owner_disk_file("sch", "mem", unique) == marker

    files = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="run-new",
        kind="files",
    )
    assert files["session_id"] != sid
    assert any(f["name"] == unique for f in files["files"])
    assert files.get("persist") is True

    second = await runtime.open_session(
        school_id="sch",
        membership_id="mem",
        run_id="run-new",
        kind="writer",
        filename=unique,
        document=b"",
    )
    assert any(f["name"] == unique for f in second["files"])
    assert unique in second["title"]
    png = listing_png([unique])
    assert unique.encode("ascii") in png

    other = await runtime.open_session(
        school_id="sch",
        membership_id="other",
        run_id="run-new",
        kind="files",
    )
    assert unique not in [f["name"] for f in other["files"]]
    with pytest.raises(ToolError) as denied:
        runtime.require_owner(second["session_id"], school_id="sch", membership_id="other")
    assert denied.value.code == "sandbox.forbidden"
