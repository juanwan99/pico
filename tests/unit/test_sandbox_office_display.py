import asyncio
import os
import re
import shutil
import signal
import sys
from contextlib import suppress
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pico_orchestrator.document_generators import (
    build_docx_document,
    build_pptx_document,
    build_xlsx_document,
)
from pico_orchestrator.gateway import ToolError
from PIL import Image
from sandbox_worker import office


@pytest.mark.asyncio
async def test_close_stops_libreoffice_launcher_child(tmp_path):
    work = tmp_path / "document"
    work.mkdir()
    xvfb = await office._spawn(["sleep", "60"], env=dict(os.environ))
    launcher = await office._spawn(
        [
            sys.executable,
            "-c",
            (
                "import os, signal\n"
                "if os.fork() == 0:\n"
                "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "    print('ready', flush=True)\n"
                "    signal.pause()\n"
            ),
        ],
        env=dict(os.environ),
        stdout=asyncio.subprocess.PIPE,
    )
    desktop = office.OfficeDesktop(
        kind="writer",
        filename="sample.docx",
        doc_path=work / "sample.docx",
        display=":0",
        xvfb=xvfb,
        office=launcher,
    )
    try:
        assert await asyncio.wait_for(launcher.stdout.readline(), timeout=3) == b"ready\n"
        # The group leader can be gone while the child still holds stdout open.
        async with asyncio.timeout(3):
            while launcher.returncode is None:
                await asyncio.sleep(0.01)
        await desktop.close()
        assert await asyncio.wait_for(launcher.stdout.read(), timeout=3) == b""
        assert xvfb.returncode == -signal.SIGTERM
        assert not work.exists()
    finally:
        for proc in (launcher, xvfb):
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()


@pytest.mark.asyncio
async def test_xvfb_eof_does_not_start_libreoffice(monkeypatch, tmp_path):
    report = asyncio.StreamReader()
    report.feed_data(b"42")
    report.feed_eof()
    xvfb = SimpleNamespace(pid=123, stdout=report, returncode=1, wait=AsyncMock())
    spawn = AsyncMock(return_value=xvfb)
    killpg = Mock()
    monkeypatch.setattr(office, "_DOC_ROOT", tmp_path)
    monkeypatch.setattr(office.shutil, "which", lambda name: name)
    monkeypatch.setattr(office, "_spawn", spawn)
    monkeypatch.setattr(office.os, "killpg", killpg)

    with pytest.raises(ToolError, match="沙箱桌面未能启动") as error:
        await office.open_office(kind="writer", filename="sample.docx", document=b"PK")

    assert error.value.code == "sandbox.office_unavailable"
    spawn.assert_awaited_once()
    assert spawn.await_args.args[0][1:3] == ["-displayfd", "1"]
    killpg.assert_called_once_with(xvfb.pid, signal.SIGKILL)
    xvfb.wait.assert_awaited_once()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_concurrent_office_windows_get_distinct_displays(monkeypatch, tmp_path):
    for program in ("Xvfb", "xdotool", "scrot"):
        if not shutil.which(program):
            pytest.skip(f"{program} is required to test real desktop windows")
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        pytest.skip("LibreOffice is required to test real desktop windows")
    monkeypatch.setattr(office, "_DOC_ROOT", tmp_path)
    monkeypatch.setenv("DISPLAY", ":65535")

    documents = {
        "docx": build_docx_document(title="Word", marker="word", body="Writer display test"),
        "xlsx": build_xlsx_document(title="Excel", marker="excel", body="Calc display test"),
        "pptx": build_pptx_document(title="PPT", marker="ppt", body="Impress display test"),
    }
    desktops: list[office.OfficeDesktop] = []

    async def open_window(filename, document):
        desktop = await office.open_office(kind="", filename=filename, document=document)
        desktops.append(desktop)
        proc = await asyncio.create_subprocess_exec(
            "xdotool", "search", "--onlyvisible", "--name", rf"^{re.escape(filename)} ",
            env={**os.environ, "DISPLAY": desktop.display},
            stdout=asyncio.subprocess.DEVNULL,
        )
        assert await proc.wait() == 0, (filename, desktop.display)
        return desktop

    try:
        async with asyncio.TaskGroup() as tasks:
            for ext, document in documents.items():
                for index in range(10):
                    tasks.create_task(open_window(f"parallel-{index}.{ext}", document))
        assert len({desktop.display for desktop in desktops}) == 30

        closed = desktops[-1]
        await closed.close()
        desktops.pop()
        active_displays = {desktop.display for desktop in desktops}
        reopened = await open_window(closed.filename, documents[closed.doc_path.suffix[1:]])
        assert reopened.display not in active_displays

        for kind in office.KIND_FLAGS:
            desktop = next(desktop for desktop in desktops if desktop.kind == kind)
            with Image.open(BytesIO(await desktop.screenshot_png())) as image:
                assert image.size == (office.DESKTOP_W, office.DESKTOP_H)
                assert any(low < high for low, high in image.convert("RGB").getextrema())
    finally:
        await asyncio.gather(*(desktop.close() for desktop in desktops))
