"""T-PPT-CONTRACT: Pi sees embed field; markdown/[image:] do not embed; spec does."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import parse_spec, sanitize_slide_text, spec_from_plain
from pico_orchestrator.tool_observation import observe_write
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.runtime import pico_system_text

ROOT = Path(__file__).resolve().parents[2]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_sanitize_drops_markdown_and_fake_image_token() -> None:
    cleaned = sanitize_slide_text("# 流程\n- **P 代** × 矮茎\n[image:art-1]\n---\nF2 **3:1**")
    assert "**" not in cleaned
    assert "[image:" not in cleaned
    assert "#" not in cleaned
    assert "---" not in cleaned
    assert "P 代" in cleaned
    assert "3:1" in cleaned


def test_plain_body_markdown_does_not_embed_or_keep_tokens() -> None:
    spec = spec_from_plain(
        kind="pptx",
        title="豌豆.pptx",
        marker="mk-a",
        body="# 一对相对性状\n- **P 代**\n[image:art-fake]\n\n---\n## 流程\n- F2 **3:1**",
    )
    raw = render_spec(spec, images={"art-fake": PNG})
    outline = inspect_office_bytes(raw, ".pptx")
    assert outline["images"] == 0
    blob = "\n".join(
        (u.get("title") or "") + "\n" + "\n".join(u.get("bullets") or [])
        for u in (outline.get("units") or [])
    )
    assert "[image:" not in blob
    assert "**" not in blob


def test_image_token_in_bullets_does_not_embed_even_if_bytes_present() -> None:
    spec = parse_spec(
        {
            "kind": "pptx",
            "title": "假语法.pptx",
            "blocks": [
                {
                    "type": "slide",
                    "title": "流程",
                    "bullets": ["P→F1", "[image:art-real]", "**3:1**"],
                }
            ],
        }
    )
    raw = render_spec(spec, images={"art-real": PNG})
    outline = inspect_office_bytes(raw, ".pptx")
    assert outline["images"] == 0
    blob = "\n".join(
        "\n".join(u.get("bullets") or []) for u in (outline.get("units") or [])
    )
    assert "[image:" not in blob
    assert "**" not in blob
    assert "3:1" in blob


def test_image_artifact_id_embeds() -> None:
    spec = parse_spec(
        {
            "kind": "pptx",
            "title": "正确嵌图.pptx",
            "blocks": [
                {
                    "type": "slide",
                    "title": "一对相对性状",
                    "bullets": ["P→F1→F2"],
                    "image_artifact_id": "art-diagram-1",
                }
            ],
        }
    )
    raw = render_spec(spec, images={"art-diagram-1": PNG})
    outline = inspect_office_bytes(raw, ".pptx")
    assert outline["images"] >= 1


def test_observe_pptx_hints_when_no_images() -> None:
    spec = spec_from_plain(kind="pptx", title="t.pptx", marker="m", body="封面\n要点")
    raw = render_spec(spec)
    seen = observe_write(kind="pptx", title="t.pptx", raw=raw)
    assert seen["outline"]["images"] == 0
    assert "image_artifact_id" in seen["outline"]["hint"]


def test_observe_pptx_no_hint_when_embedded() -> None:
    spec = parse_spec(
        {
            "kind": "pptx",
            "title": "t.pptx",
            "blocks": [{"type": "slide", "title": "图", "image_artifact_id": "img-1"}],
        }
    )
    raw = render_spec(spec, images={"img-1": PNG})
    seen = observe_write(kind="pptx", title="t.pptx", raw=raw)
    assert seen["outline"]["images"] >= 1
    assert "hint" not in seen["outline"]


def test_pi_surface_names_image_artifact_id() -> None:
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    start = ts.find('Create a real .pptx Artifact')
    pptx = ts[start : start + 1600]
    assert "image_artifact_id" in pptx
    assert "spec" in pptx
    assert "[image:" in pptx
    assert "Pictures: generate_image first when needed" not in ts
    img = ts[ts.find("Create one png/jpg") : ts.find("Create one png/jpg") + 400]
    assert "SiliconFlow" not in img
    system = pico_system_text()
    assert "image_artifact_id" in system
    assert "[image:" in system


@dataclass
class _P:
    school_id: str
    membership_id: str
    scopes: list[str]


class _ProdShapedStore:
    """Same keyword-only read() as production LedgerArtifactStore. No defaults."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(
        self,
        principal: _P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        del principal
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        row = {
            "artifact_id": f"art-{len(self.rows) + 1}",
            "title": title,
            "kind": kind,
            "byte_size": len(raw),
            "content_base64": base64.b64encode(raw).decode("ascii")
            if isinstance(content, bytes)
            else None,
            "content": None if isinstance(content, bytes) else content,
        }
        self.rows.append(row)
        return {k: v for k, v in row.items() if k not in {"content", "content_base64"}}

    async def read(
        self,
        principal: _P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        del principal
        for row in reversed(self.rows):
            if artifact_id and row["artifact_id"] == artifact_id:
                return dict(row)
            if not artifact_id and title and row["title"] == title:
                return dict(row)
        return None

    async def list(self, principal: _P, *, limit: int) -> list[dict[str, Any]]:
        del principal
        return list(reversed(self.rows))[:limit]


@pytest.mark.asyncio
async def test_generate_pptx_loads_image_when_store_requires_title() -> None:
    """Live bug: _load_spec_images omitted title= and LedgerArtifactStore TypeError'd."""
    store = _ProdShapedStore()
    gw = build_default_gateway(store)
    owner = _P("s", "m", ["ai:run"])
    store.rows.append(
        {
            "artifact_id": "img-live",
            "title": "cover.jpg",
            "kind": "jpg",
            "byte_size": len(PNG),
            "content_base64": base64.b64encode(PNG).decode("ascii"),
            "content": None,
        }
    )
    deck = await gw.invoke(
        owner,
        "generate_pptx_document",
        {
            "title": "嵌图.pptx",
            "spec": {
                "kind": "pptx",
                "blocks": [
                    {
                        "type": "slide",
                        "title": "封面",
                        "bullets": ["见图"],
                        "image_artifact_id": "img-live",
                    }
                ],
            },
        },
    )
    row = await store.read(owner, artifact_id=deck["artifact_id"], title=None)
    assert row is not None
    raw = base64.b64decode(row["content_base64"])
    outline = inspect_office_bytes(raw, ".pptx")
    assert outline["images"] >= 1
