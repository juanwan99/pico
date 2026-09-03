"""#850 binary stays on the ledger. Model speaks ids."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import Principal, ToolError
from pico_orchestrator.html_ledger_images import image_data_url, rewrite_pico_artifact_srcs
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.user_errors import user_message_for_error

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _rows(self, principal: Principal) -> list[dict[str, Any]]:
        return self.rows.setdefault((principal.school_id, principal.membership_id), [])

    async def write(
        self,
        principal: Principal,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        import base64
        import hashlib

        if isinstance(content, bytes):
            size = len(content)
            encoding = "base64"
            digest = hashlib.sha256(content).hexdigest()
            text_content = None
            content_b64 = base64.b64encode(content).decode("ascii")
        else:
            size = len(content.encode("utf-8"))
            encoding = "utf8"
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            text_content = content
            content_b64 = None
        row = {
            "artifact_id": f"art-{len(self._rows(principal)) + 1}",
            "title": title,
            "content": text_content,
            "content_base64": content_b64,
            "kind": kind,
            "size": size,
            "byte_size": size,
            "content_encoding": encoding,
            "content_sha256": digest,
        }
        self._rows(principal).append(row)
        return {key: value for key, value in row.items() if key not in {"content", "content_base64"}}

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and row["title"] == title:
                return row
        return None

    async def list(self, principal: Principal, *, limit: int) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in row.items() if key != "content"}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]


@pytest.mark.asyncio
async def test_html_keeps_pico_artifact_id_on_ledger() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    pic = await store.write(owner, title="cover.png", content=TINY_PNG, kind="png")
    aid = pic["artifact_id"]
    page = await gw.invoke(
        owner,
        "generate_html_document",
        {
            "title": "deck.html",
            "marker": "M1",
            "body": (
                "<!DOCTYPE html><html><body>"
                f'<img src="pico-artifact:{aid}" alt="cover" />'
                "<button type='button'>ok</button>"
                "</body></html>"
            ),
        },
    )
    assert page["kind"] == "html"
    assert page["images"]["landed"] == [aid]
    assert page["images"]["skipped"] == []
    stored = await store.read(owner, artifact_id=page["artifact_id"], title=None)
    html = stored["content"]
    assert f"pico-artifact:{aid}" in html
    assert "data:image/png;base64," not in html
    assert "https://" not in html.split("<img")[1].split(">")[0]
    inlined, meta = rewrite_pico_artifact_srcs(
        html, resolved={aid: image_data_url(TINY_PNG) or ""}, index_ids=[]
    )
    assert "data:image/png;base64," in inlined
    assert meta["landed"] == [aid]


@pytest.mark.asyncio
async def test_html_index_alias_and_missing_id_skips() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    pic = await store.write(owner, title="one.png", content=TINY_PNG, kind="png")
    page = await gw.invoke(
        owner,
        "generate_html_document",
        {
            "title": "two.html",
            "marker": "M2",
            "image_artifact_ids": [pic["artifact_id"]],
            "body": (
                "<!DOCTYPE html><html><body>"
                '<img src="pico-artifact:0" alt="ok" />'
                '<img src="pico-artifact:missing-id" alt="gone" />'
                "</body></html>"
            ),
        },
    )
    assert pic["artifact_id"] in page["images"]["landed"]
    assert "missing-id" in page["images"]["skipped"]
    stored = await store.read(owner, artifact_id=page["artifact_id"], title=None)
    html = stored["content"]
    assert f'pico-artifact:{pic["artifact_id"]}' in html
    assert "data:image/png;base64," not in html
    assert 'src="pico-artifact:missing-id"' in html


@pytest.mark.asyncio
async def test_read_file_strips_png_keeps_text() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    pic = await store.write(owner, title="shot.png", content=TINY_PNG, kind="png")
    note = await gw.invoke(
        owner,
        "workspace_write_file",
        {"title": "note.md", "content": "hello", "kind": "file"},
    )
    binary = await gw.invoke(
        owner, "workspace_read_file", {"artifact_id": pic["artifact_id"]}
    )
    art = binary["artifact"]
    assert "content" not in art or art.get("content") in (None, "")
    assert "content_base64" not in art
    assert art["binary"] is True
    assert "像素不进" in art["user_message"]
    assert "不能当正文读" not in art["user_message"]
    assert art["kind"] == "png"
    text = await gw.invoke(
        owner, "workspace_read_file", {"artifact_id": note["artifact_id"]}
    )
    assert text["artifact"]["content"] == "hello"
    assert text["artifact"].get("binary") is not True


@pytest.mark.asyncio
async def test_read_file_strips_data_urls_from_html() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    b64 = "A" * 120
    page = await gw.invoke(
        owner,
        "generate_html_document",
        {
            "title": "pix.html",
            "marker": "PX",
            "body": (
                "<!DOCTYPE html><html><body>"
                f'<img src="data:image/png;base64,{b64}" alt="x" />'
                "<button type='button'>ok</button>"
                "</body></html>"
            ),
        },
    )
    got = await gw.invoke(
        owner, "workspace_read_file", {"artifact_id": page["artifact_id"]}
    )
    body = got["artifact"]["content"]
    assert "data:image/omitted" in body
    assert b64 not in body


@pytest.mark.asyncio
async def test_read_file_extracts_office_text_not_base64() -> None:
    from pico_orchestrator.document_generators import build_docx_document

    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    raw = build_docx_document(title="通知.docx", marker="READ-OFFICE", body="三年级二班春游")
    saved = await store.write(owner, title="通知.docx", content=raw, kind="docx")
    got = await gw.invoke(
        owner, "workspace_read_file", {"artifact_id": saved["artifact_id"]}
    )
    art = got["artifact"]
    assert "content_base64" not in art
    assert art.get("binary") is not True
    assert "三年级二班春游" in (art.get("content") or "")
    assert art.get("extracted") is True


@pytest.mark.asyncio
async def test_read_file_legacy_doc_is_honest_unread() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    saved = await store.write(
        owner, title="旧稿.doc", content=b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1junk", kind="bin"
    )
    got = await gw.invoke(
        owner, "workspace_read_file", {"artifact_id": saved["artifact_id"]}
    )
    art = got["artifact"]
    assert "content_base64" not in art
    assert art.get("unread") is True
    assert "OLE" in art["user_message"]


@pytest.mark.asyncio
async def test_read_file_excerpt_sidecar_is_unread_not_extracted() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    saved = await store.write(
        owner,
        title="地理答案.pdf",
        content='{"status":"unread","text":"","error":"没抽出正文"}',
        kind="edu_excerpt",
    )
    got = await gw.invoke(
        owner, "workspace_read_file", {"artifact_id": saved["artifact_id"]}
    )
    art = got["artifact"]
    assert art.get("extracted") is not True
    assert art.get("unread") is True
    assert "没抽出正文" not in str(art.get("content") or "")
    assert "content_base64" not in art


def test_canonicalize_index_alias() -> None:
    from pico_orchestrator.html_ledger_images import canonicalize_pico_artifact_refs

    out = canonicalize_pico_artifact_refs(
        '<img src="pico-artifact:0"><img src="pico-artifact:missing">',
        ["abc"],
    )
    assert 'src="pico-artifact:abc"' in out
    assert 'src="pico-artifact:missing"' in out


def test_rewrite_helper_index() -> None:
    url = image_data_url(TINY_PNG)
    assert url and url.startswith("data:image/png;base64,")
    html, meta = rewrite_pico_artifact_srcs(
        '<img src="pico-artifact:0">',
        resolved={"abc": url},
        index_ids=["abc"],
    )
    assert url in html
    assert meta["landed"] == ["abc"]


def test_task_list_omits_large_utf8_inline() -> None:
    sys.path.insert(0, str(ROOT / "services" / "api"))
    from app.artifact_store import artifact_inline_for_list

    assert artifact_inline_for_list(encoding="utf8", inline="ok", byte_size=2) == "ok"
    assert (
        artifact_inline_for_list(encoding="utf8", inline="y" * 9000, byte_size=9000)
        is None
    )
    assert artifact_inline_for_list(encoding="base64", inline="aaa", byte_size=3) is None


def test_stream_read_error_is_human() -> None:
    msg = user_message_for_error("stream_read_error", code="true_pi.assistant_error")
    assert "stream_read_error" not in msg
    assert "文件还在" in msg
    msg2 = user_message_for_error(
        "Error Code bad_response: stream ended abnormally: reason=eof soft_errors=1",
        code="true_pi.assistant_error",
    )
    assert "soft_errors" not in msg2
    assert "eof" not in msg2.lower()
    assert "文件还在" in msg2
    assert "未能完成" not in msg2


@pytest.mark.asyncio
async def test_html_https_image_still_fail_closed() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            owner,
            "generate_html_document",
            {
                "title": "cdn.html",
                "marker": "M3",
                "body": (
                    "<!DOCTYPE html><html><body>"
                    '<img src="https://cdn.example/a.png" />'
                    "</body></html>"
                ),
            },
        )
    assert ei.value.code == "tool.invalid_arguments"
    assert "外网" in ei.value.message


@pytest.mark.asyncio
async def test_html_ledger_stays_small_when_picture_is_fat() -> None:
    """Pixels stay on the png row. HTML row must not balloon past author body max."""
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P("s1", "m1", ["ai:run"])
    fat = TINY_PNG + (b"X" * 160_000)
    pic = await store.write(owner, title="fat.png", content=fat, kind="png")
    page = await gw.invoke(
        owner,
        "generate_html_document",
        {
            "title": "fat.html",
            "marker": "M4",
            "body": (
                "<!DOCTYPE html><html><body>"
                f'<img src="pico-artifact:{pic["artifact_id"]}" alt="fat" />'
                "</body></html>"
            ),
        },
    )
    stored = await store.read(owner, artifact_id=page["artifact_id"], title=None)
    assert len(stored["content"]) < 200_000
    assert f'pico-artifact:{pic["artifact_id"]}' in stored["content"]
    assert "data:image/png;base64," not in stored["content"]
    url = image_data_url(fat)
    inlined, _meta = rewrite_pico_artifact_srcs(
        stored["content"], resolved={pic["artifact_id"]: url or ""}, index_ids=[]
    )
    assert len(inlined) > 200_000
    assert "data:image/png;base64," in inlined
