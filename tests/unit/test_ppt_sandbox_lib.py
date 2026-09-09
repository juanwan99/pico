"""T-PPT-SANDBOX-LIB: isolated python-pptx ceiling. Spec path stays default."""

from __future__ import annotations

import base64
import sys
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.pptx_helpers import ImagePathMap
from pico_orchestrator.office.sandbox_lib import (
    PPTX_LIB_MAX_SOURCE,
    assert_pptx_lib_source,
    run_pptx_lib_source,
)
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.workbench_progress import (
    workbench_tool_result_line,
    workbench_tool_step_line,
)

ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xa3\x0a\x0d\xe4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

THREE_SLIDE_WITH_IMAGE = """
prs = Presentation()
for title in ("封面", "配图", "结尾"):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
pic = None
for key in IMAGE_PATHS:
    pic = IMAGE_PATHS[key]
if pic:
    prs.slides[1].shapes.add_picture(pic, Inches(1), Inches(1.6), width=Inches(5))
save_deck(prs)
"""


@dataclass
class P:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.scopes is None:
            self.scopes = ["ai:run"]


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _rows(self, principal: P) -> list[dict[str, Any]]:
        return self.rows.setdefault((principal.school_id, principal.membership_id), [])

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        if isinstance(content, bytes):
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": None,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "kind": kind,
                "size": len(content),
                "byte_size": len(content),
                "content_encoding": "base64",
            }
        else:
            body = content
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": body,
                "kind": kind,
                "size": len(body.encode("utf-8")),
                "byte_size": len(body.encode("utf-8")),
                "content_encoding": "utf8",
            }
        self._rows(principal).append(row)
        return {k: v for k, v in row.items() if k not in {"content", "content_base64"}}

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and title and row["title"] == title:
                return row
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k != "content"}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]


def _pptx_bytes(store: MemoryArtifactStore, owner: P, artifact_id: str) -> bytes:
    rows = store._rows(owner)
    row = next(r for r in rows if r["artifact_id"] == artifact_id)
    return base64.b64decode(row["content_base64"])


def test_allowlist_has_ceiling_not_bash() -> None:
    gw = build_default_gateway()
    names = set(gw.tools)
    assert "sandbox_pptx_lib" not in names
    assert "sandbox_office_lib" in names
    assert "generate_pptx_document" not in names
    assert "sandbox_pptx_lib" not in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_office_lib" in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in names
    schemas = {s["function"]["name"] for s in openai_tool_schemas(gw)}
    assert "sandbox_pptx_lib" not in schemas
    assert "sandbox_office_lib" in schemas
    assert len(ALLOWED_GATEWAY_TOOLS) == 19
    assert "generate_diagram" in ALLOWED_GATEWAY_TOOLS
    assert workbench_tool_step_line("sandbox_office_lib") == "正在沙箱写办公文件"
    assert workbench_tool_result_line("sandbox_office_lib", ok=True) == "已沙箱写出办公文件"
    assert workbench_tool_result_line("sandbox_office_lib", ok=False) == "没沙箱写出办公文件"


def test_source_door_is_syntax_and_size_only() -> None:
    """v2 (#959): no import / dunder jail. Only empty, oversize, or unparsable is refused."""
    assert_pptx_lib_source("import os\nprs = Presentation()\nsave_deck(prs)")
    assert_pptx_lib_source("eval('1')")
    assert_pptx_lib_source("Presentation.__class__")
    assert_pptx_lib_source("from pathlib.abc import Path")
    assert_pptx_lib_source(
        "from pptx import Presentation\n"
        "prs = Presentation()\n"
        "if __name__ == '__main__':\n"
        "    prs.save('/tmp/x.pptx')\n"
    )
    with pytest.raises(ToolError) as ei:
        assert_pptx_lib_source("   ")
    assert ei.value.code == "tool.invalid_arguments"
    with pytest.raises(ToolError) as ei:
        assert_pptx_lib_source("def (:\n")
    assert ei.value.code == "sandbox.exec_invalid"


def test_real_pathlib_and_local_save_land_in_ledger() -> None:
    """Naked GPT writes to its own path in the workdir; the newest deck is collected."""
    source = """
from pathlib import Path
from pptx import Presentation
Path('out/x').mkdir(parents=True, exist_ok=True)
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = '真 pathlib'
prs.save('out/x/deck.pptx')
"""
    raw = run_pptx_lib_source(source)
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 1


def test_blank_layout_go_title_body_writes() -> None:
    """Live F4 r2: blank + go() hit shapes.title None → sandbox.pptx_failed."""
    source = """
from pptx import Presentation, Inches, Pt
prs = Presentation()
blank = prs.slide_layouts[6]
def go(slide, title_txt, bullets):
    t = slide.shapes.title
    t.text = title_txt
    body = slide.placeholders[1].text_frame
    body.clear()
    for b in bullets:
        p = body.add_paragraph()
        p.text = b
slide = prs.slides.add_slide(blank)
box = slide.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(11.7), Inches(1.4))
box.text_frame.text = "办公简报：本周经营风险与下周动作"
slide = prs.slides.add_slide(blank)
go(slide, "本周经营风险总览", ["市场端询盘下降", "交付延迟风险"])
save_deck(prs)
"""
    raw = run_pptx_lib_source(source)
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 2
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        xml = b"".join(zf.read(name) for name in zf.namelist() if name.startswith("ppt/slides/"))
    blob = xml.decode("utf-8", errors="replace")
    assert "本周经营风险总览" in blob or "市场端询盘下降" in blob


def test_from_pptx_import_writes_real_deck() -> None:
    """Live F: document-skill `from pptx import Presentation` was exec_denied."""
    source = """
from pptx import Presentation
from pptx.util import Inches, Pt
prs = Presentation()
add_title_slide(prs, "本周经营风险与下周动作", "责任人：张三")
add_content_slide(prs, "风险总览", ["收入端延期", "毛利承压", "回款变慢"])
save_deck(prs)
"""
    raw = run_pptx_lib_source(source)
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 2


def test_image_path_map_int_index() -> None:
    """Live F2: IMAGE_PATHS[0] was KeyError because the inject is a dict."""
    paths = ImagePathMap({"art-9": "/tmp/a.png", "art-2": "/tmp/b.png"})
    assert paths[0] == "/tmp/a.png"
    assert paths["art-9"] == "/tmp/a.png"
    assert paths[1] == "/tmp/b.png"
    assert 0 in paths
    assert paths.get(0) == "/tmp/a.png"
    empty = ImagePathMap()
    with pytest.raises(IndexError):
        empty[0]


def test_from_pptx_import_inches_pt_on_pptx_package() -> None:
    """Live F2: `from pptx import Presentation, Inches, Pt` was ImportError."""
    source = """
from pptx import Presentation, Inches, Pt
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "封面"
pic = IMAGE_PATHS[0]
slide.shapes.add_picture(pic, Inches(1), Inches(1.6), width=Inches(5))
save_deck(prs)
"""
    raw = run_pptx_lib_source(source, images={"art-cover": ONE_PNG})
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 1
    assert int(outline["images"]) >= 1
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        media = [name for name in zf.namelist() if name.startswith("ppt/media/")]
        assert media


def test_helper_aliases_title_image_and_table_prs() -> None:
    """Live F2: add_title_slide(image=) / add_table(prs=) / add_table(prs, rows)."""
    source = """
from pptx import Presentation, Inches, Pt
prs = Presentation()
add_title_slide(prs, "本周经营风险与下周动作", "责任人：张三", image=IMAGE_PATHS[0])
add_content_slide(prs, "风险总览", ["订单交付延期", "毛利率承压", "回款变慢"])
add_table(prs=prs, rows=[["项", "本周"], ["收入", "88"], ["毛利", "21"]])
add_table(prs, [["项", "上周"], ["回款", "12"]])
save_deck(prs)
"""
    raw = run_pptx_lib_source(source, images={"art-cover": ONE_PNG})
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 4
    assert int(outline["images"]) >= 1
    from pptx import Presentation

    deck = Presentation(BytesIO(raw))
    tables = [s for sl in deck.slides for s in sl.shapes if getattr(s, "has_table", False)]
    assert len(tables) >= 2
    assert tables[0].table.cell(1, 1).text == "88"


def test_add_table_without_rows_still_typeerror() -> None:
    """Alias prs= does not invent a table when the grid is missing."""
    from pico_orchestrator.office.pptx_helpers import add_table
    from pptx import Presentation

    prs = Presentation()
    with pytest.raises(TypeError, match="rows"):
        add_table(prs=prs)


def test_live_placeholder_empty_shell_still_fails() -> None:
    source = (
        "from pptx import Presentation\n"
        "prs = Presentation()\n"
        "# 说明：此处使用沙箱其余逻辑由工具提供，本块只作占位\n"
        "save_deck(prs)"
    )
    with pytest.raises(ToolError) as ei:
        run_pptx_lib_source(source)
    assert ei.value.code == "sandbox.pptx_shell"


def test_empty_shell_fail_closed() -> None:
    with pytest.raises(ToolError) as ei:
        run_pptx_lib_source("prs = Presentation()\nsave_deck(prs)")
    assert ei.value.code == "sandbox.pptx_shell"
    assert "空壳" in ei.value.message or "没有可看" in ei.value.message
    with pytest.raises(ToolError) as ei:
        run_pptx_lib_source("prs = Presentation()")
    assert ei.value.code == "sandbox.no_output"


@pytest.mark.asyncio
async def test_complex_image_then_sandbox_deck_has_media() -> None:
    """Complex task: generate_image → sandbox_office_lib kind=pptx → zip media + inspect."""
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P()

    async def fake_image(_prompt: str) -> tuple[bytes, str, None]:
        return ONE_PNG, "png", None

    with patch(
        "pico_orchestrator.tools_builtin.generate_image_with_usage",
        fake_image,
    ):
        pictured = await gw.invoke(owner, "generate_image", {"prompt": "示意图"})
    aid = pictured["artifact_id"]
    assert aid

    out = await gw.invoke(
        owner,
        "sandbox_office_lib",
        {
            "kind": "pptx",
            "source": THREE_SLIDE_WITH_IMAGE,
            "title": "上限.pptx",
            "image_artifact_ids": [aid],
        },
    )
    assert out["format"] == "pptx"
    assert out["via"] == "sandbox_office_lib"
    raw = _pptx_bytes(store, owner, out["artifact_id"])
    assert is_valid_ooxml_package(raw, ".pptx")
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        media = [name for name in zf.namelist() if name.startswith("ppt/media/")]
        assert media, "sandbox deck must embed a picture, not a text-only shell"
        blob = zf.read(media[0])
        assert blob[:8] == b"\x89PNG\r\n\x1a\n"
        assert blob == ONE_PNG
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 3
    assert int(outline["images"]) >= 1


@pytest.mark.asyncio
async def test_generate_pptx_document_not_on_gateway() -> None:
    gw = build_default_gateway(MemoryArtifactStore())
    assert "generate_pptx_document" not in gw.tools
    assert "sandbox_pptx_lib" not in gw.tools
    owner = P()
    one = await gw.invoke(
        owner,
        "sandbox_office_lib",
        {
            "kind": "pptx",
            "title": "日常.pptx",
            "source": (
                "from pptx import Presentation\n"
                "prs = Presentation()\n"
                "add_title_slide(prs, '只有一页', 'M-default')\n"
                "save_deck(prs)\n"
            ),
        },
    )
    assert one.get("format") == "pptx"
    assert one.get("via") == "sandbox_office_lib"


@pytest.mark.asyncio
async def test_tool_rejects_import_and_empty_shell() -> None:
    gw = build_default_gateway()
    owner = P()
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            owner,
            "sandbox_office_lib",
            {"kind": "pptx", "source": "import os\nprs = Presentation()\nsave_deck(prs)"},
        )
    # `import os` is fine now; the empty deck is what fails.
    assert ei.value.code == "sandbox.pptx_shell"
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            owner,
            "sandbox_office_lib",
            {"kind": "pptx", "source": "prs = Presentation()\nsave_deck(prs)"},
        )
    assert ei.value.code == "sandbox.pptx_shell"


def test_runner_is_python_not_host_bash() -> None:
    """pico-api never runs the script itself; the runner is python in the box."""
    client = (ROOT / "services/orchestrator/pico_orchestrator/office/sandbox_lib.py").read_text(
        encoding="utf-8"
    )
    assert "subprocess" not in client
    assert "sys.executable" not in client
    runner = (ROOT / "services/sandbox_worker/office_runner.py").read_text(encoding="utf-8")
    assert "sys.executable" in runner
    assert "/bin/bash" not in runner
    assert "shell=True" not in runner


def test_pico_office_container_contract_in_compose() -> None:
    """The jail is the container, so pin the container: no network, no secrets, no disk."""
    import re

    compose = (ROOT / "docker-compose.host.yml").read_text(encoding="utf-8")
    block = re.search(
        r"\n  pico-office:\n(.*?)(?=\n  [a-z][a-z0-9-]*:\n|\nvolumes:\n)", compose, re.DOTALL
    )
    assert block, "pico-office service missing"
    svc = block.group(1)
    assert "network_mode: none" in svc
    assert "read_only: true" in svc
    assert "- ALL" in svc and "cap_drop" in svc
    assert "no-new-privileges:true" in svc
    assert 'user: "65532:65532"' in svc
    assert "teacher-disks" not in svc
    assert "DEEPSEEK" not in svc and "JWT" not in svc and "MEILI_MASTER_KEY" not in svc
    assert "pico-office-sock}:/run/pico-office" in svc
    assert "sandbox_worker.office_runner" in svc
    api = re.search(r"\n  pico-api:\n(.*?)\n  meilisearch:\n", compose, re.DOTALL)
    assert api and "PICO_OFFICE_URL: unix:///run/pico-office/office.sock" in api.group(1)
    assert "PICO_OFFICE_URL: embedded" not in api.group(1)


NAKED_STYLE_SOURCE = """
from pathlib import Path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

out = Path("/tmp/pico-sandbox-must-not-write-here")
out.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(15, 25, 44)
CREAM = RGBColor(247, 244, 235)
MINT = RGBColor(115, 214, 177)
WHITE = RGBColor(255, 255, 255)

def add_box(slide, x, y, w, h, fill):
    if not isinstance(slide, object) or not hasattr(slide, "shapes"):
        raise TypeError("slide")
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]

slide = prs.slides.add_slide(blank)
add_box(slide, 0, 0, 13.333, 7.5, NAVY)
box = slide.shapes.add_textbox(Inches(0.8), Inches(2.4), Inches(11.5), Inches(1.4))
tf = box.text_frame
tf.clear()
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.LEFT
run = p.add_run()
run.text = "减数分裂"
run.font.size = Pt(44)
run.font.bold = True
run.font.color.rgb = WHITE

slide = prs.slides.add_slide(blank)
add_box(slide, 0, 0, 13.333, 7.5, CREAM)
add_box(slide, 0.6, 1.6, 3.8, 4.6, MINT)
box = slide.shapes.add_textbox(Inches(0.8), Inches(1.9), Inches(3.4), Inches(0.6))
box.text_frame.paragraphs[0].text = "同源染色体配对"

slide = prs.slides.add_slide(blank)
add_box(slide, 0, 0, 13.333, 7.5, NAVY)
add_box(slide, 0.7, 1.8, 5.8, 4.4, RGBColor(30, 45, 71))
box = slide.shapes.add_textbox(Inches(1.0), Inches(2.1), Inches(5.2), Inches(0.5))
box.text_frame.paragraphs[0].text = "有丝分裂 vs 减数分裂"

prs.save("/tmp/pico-sandbox-must-not-write-here/out.pptx")
"""


def test_naked_prs_save_to_own_path_is_collected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v2: the box is a computer — the script may save wherever it likes inside the
    box; the runner collects the recorded save path. (Embedded mode = the host is the
    box, so we point the fixture's path at tmp_path.)"""
    target = tmp_path / "pico-sandbox-must-not-write-here" / "out.pptx"
    source = NAKED_STYLE_SOURCE.replace(
        '"/tmp/pico-sandbox-must-not-write-here"', repr(str(target.parent))
    ).replace('"/tmp/pico-sandbox-must-not-write-here/out.pptx"', repr(str(target)))
    raw = run_pptx_lib_source(source)
    assert is_valid_ooxml_package(raw, ".pptx")
    assert target.exists(), "the script's own save path is honoured, not redirected"
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 3
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        xml = b"".join(zf.read(name) for name in zf.namelist() if name.startswith("ppt/slides/"))
    blob = xml.decode("utf-8", errors="replace")
    assert "减数分裂" in blob
    assert "同源染色体配对" in blob
    assert "srgbClr" in blob
    assert "0F192C" in blob.upper() or "0f192c" in blob
    assert "title-only" not in blob


def test_naked_gpt_meiosis_fixture_runs_in_sandbox() -> None:
    source = (ROOT / "tests/fixtures/office/naked_gpt_meiosis.py.txt").read_text(encoding="utf-8")
    assert len(source) > 10_000
    raw = run_pptx_lib_source(source)
    assert is_valid_ooxml_package(raw, ".pptx")
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 4
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        xml = b"".join(zf.read(name) for name in zf.namelist() if name.startswith("ppt/slides/"))
    blob = xml.decode("utf-8", errors="replace")
    assert "减数分裂" in blob
    assert "srgbClr" in blob


def test_script_errors_surface_as_stderr_not_jail() -> None:
    """Reading a missing file is a normal Python error the model can fix; no jail code."""
    with pytest.raises(ToolError) as ei:
        run_pptx_lib_source(
            "from pathlib import Path\nPath('/definitely/not/here.txt').read_text()\n"
        )
    assert ei.value.code == "sandbox.pptx_failed"
    assert "FileNotFoundError" in ei.value.message
    assert "exec_denied" not in ei.value.code


def test_dunder_name_main_guard_still_saves() -> None:
    source = """
from pptx import Presentation
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])
shape = slide.shapes.add_shape(
    MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), Inches(4), Inches(3)
)
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(15, 25, 44)
box = slide.shapes.add_textbox(Inches(0.4), Inches(0.4), Inches(3), Inches(1))
run = box.text_frame.paragraphs[0].add_run()
run.text = "减数分裂封面"
run.font.size = Pt(20)
run.font.color.rgb = RGBColor(255, 255, 255)
if __name__ == "__main__":
    prs.save("/tmp/pico-sandbox-main-guard.pptx")
"""
    raw = run_pptx_lib_source(source)
    assert is_valid_ooxml_package(raw, ".pptx")
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 1


def test_source_cap_allows_gpt_length() -> None:
    assert PPTX_LIB_MAX_SOURCE == 200_000
    pad = "# pad\n" * 15_000
    source = (
        "from pptx import Presentation\n"
        "prs = Presentation()\n"
        "slide = prs.slides.add_slide(prs.slide_layouts[0])\n"
        "slide.shapes.title.text = 'cap'\n" + pad + "save_deck(prs)\n"
    )
    assert len(source) > 80_000
    assert_pptx_lib_source(source)
    raw = run_pptx_lib_source(source)
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 1
    with pytest.raises(ToolError) as ei:
        assert_pptx_lib_source("prs = Presentation()\n" + ("# x\n" * 60_000))
    assert ei.value.code == "tool.invalid_arguments"
