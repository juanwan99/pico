"""T-PPT-IMAGE-IN-DECK: generate_image → generate_pptx_document has a real picture.

Complex path (must pass): fixture generate_image bytes → pptx with
image_artifact_id → zip ``ppt/media/`` → inspect.images ≥ 1 → picture
is not the old 3.2in postage stamp. Text-only PPT still lands clean.
No spec fields added.
"""

from __future__ import annotations

import base64
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.document_generators import build_pptx_document
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import parse_spec
from pico_orchestrator.sandbox_s2 import encode_rgb_png
from pico_orchestrator.tools_builtin import build_default_gateway

# Wider than 1×1 so the fixture is a real picture, not a token.
FIXTURE_PNG = encode_rgb_png(
    320,
    180,
    bytes((30, 120, 200)) * (320 * 180),
    text_chunks={"deck": "fixture"},
)
STAMP_EMU = int(Inches(3.2))
MIN_CONTENT_EMU = int(Inches(4.5))


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self, *, run_id: str | None = None) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._run_id = run_id
        self._task_id = "task-deck"

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
                "run_id": self._run_id,
                "task_id": self._task_id,
                "size": len(content),
                "byte_size": len(content),
                "content_encoding": "base64",
            }
        else:
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": content,
                "kind": kind,
                "run_id": self._run_id,
                "task_id": self._task_id,
                "size": len(content.encode("utf-8")),
                "byte_size": len(content.encode("utf-8")),
                "content_encoding": "utf8",
            }
        self._rows(principal).append(row)
        return {k: v for k, v in row.items() if k not in {"content", "content_base64"}}

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and title and row["title"] == title:
                return row
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k not in {"content", "content_base64"}}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]


def _media_names(raw: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return [n for n in zf.namelist() if n.startswith("ppt/media/")]


@pytest.mark.asyncio
async def test_teacher_image_then_pptx_has_real_picture(monkeypatch) -> None:
    """Complex: generate_image fixture → generate_pptx_document → zip + size."""

    async def fake_image(prompt: str) -> tuple[bytes, str]:
        assert "图" in prompt or prompt
        return FIXTURE_PNG, "png"

    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.generate_image_bytes", fake_image
    )
    store = MemoryArtifactStore(run_id="run-deck")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    pictured = await gw.invoke(
        owner,
        "generate_image",
        {"prompt": "画一张课堂示意图", "title": "示意图.png"},
    )
    image_id = pictured["artifact_id"]
    assert image_id
    deck = await gw.invoke(
        owner,
        "generate_pptx_document",
        {
            "title": "带图汇报.pptx",
            "marker": "mk-deck",
            "spec": {
                "kind": "pptx",
                "title": "带图汇报",
                "blocks": [
                    {"type": "slide", "title": "封面", "bullets": ["今日安排"]},
                    {
                        "type": "slide",
                        "title": "配图",
                        "bullets": ["见图"],
                        "image_artifact_id": image_id,
                    },
                    {"type": "slide", "title": "结尾", "bullets": ["谢谢"]},
                ],
            },
        },
    )
    row = await store.read(owner, artifact_id=deck["artifact_id"])
    assert row is not None
    raw = base64.b64decode(row["content_base64"])
    assert is_valid_ooxml_package(raw, ".pptx")
    media = _media_names(raw)
    assert media, "ppt/media/ missing — picture never landed in the zip"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        pic = zf.read(media[0])
        assert pic[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(pic) == len(FIXTURE_PNG)
    outline = inspect_office_bytes(raw, ".pptx")
    assert outline["slides"] == 3
    assert outline["images"] >= 1
    pictured_slide = next(u for u in outline["units"] if u["index"] == 2)
    assert pictured_slide["images"] >= 1
    width = int(pictured_slide.get("image_width_emu") or 0)
    assert width >= MIN_CONTENT_EMU, f"picture still postage-stamp: {width} emu"
    assert width > STAMP_EMU


def test_text_only_pptx_has_no_media_and_still_valid() -> None:
    raw = build_pptx_document(
        title="只要文字.pptx",
        marker="mk-text",
        body="页一\n要点\n\n---\n页二\n要点\n\n---\n页三\n要点",
    )
    assert is_valid_ooxml_package(raw, ".pptx")
    assert _media_names(raw) == []
    outline = inspect_office_bytes(raw, ".pptx")
    assert outline["slides"] >= 3
    assert outline["images"] == 0


def test_hero_image_slide_is_wider_than_bullet_column() -> None:
    spec = parse_spec(
        {
            "kind": "pptx",
            "title": "大图",
            "blocks": [
                {"type": "slide", "title": "只见图", "image_artifact_id": "img-1"},
            ],
        }
    )
    raw = render_spec(spec, images={"img-1": FIXTURE_PNG})
    outline = inspect_office_bytes(raw, ".pptx")
    width = int(outline["units"][0].get("image_width_emu") or 0)
    assert width >= int(Inches(7.0))
