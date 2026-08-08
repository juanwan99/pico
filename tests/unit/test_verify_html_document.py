"""Static HTML self-check tool — honest statuses, no browser claims."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from pico_orchestrator.gateway import Principal
from pico_orchestrator.tools_builtin import build_default_gateway


class _P:
    school_id = "s1"
    membership_id = "m1"
    scopes: ClassVar[list[str]] = ["ai:run"]


class _MemStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    async def write(
        self, principal: Principal, *, title: str, content: str | bytes, kind: str
    ) -> dict[str, Any]:
        aid = f"a-{len(self.items)+1}"
        body = content if isinstance(content, str) else content.decode("utf-8", "replace")
        self.items[aid] = {
            "artifact_id": aid,
            "title": title,
            "kind": kind,
            "content": body,
            "byte_size": len(body.encode("utf-8")),
        }
        return self.items[aid]

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        if artifact_id and artifact_id in self.items:
            return self.items[artifact_id]
        if title:
            for item in self.items.values():
                if item["title"] == title:
                    return item
        return None

    async def list(self, principal: Principal, *, limit: int) -> list[dict[str, Any]]:
        return list(self.items.values())[:limit]


def test_verify_html_pass_structure() -> None:
    store = _MemStore()
    gw = build_default_gateway(store)
    html = """<!DOCTYPE html><html><body>
    <input id="name" required />
    <button type="submit">Go</button>
    <script>localStorage.setItem('x','1')</script>
    </body></html>"""

    async def _run() -> dict[str, Any]:
        return await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"content": html},
        )

    out = asyncio.run(_run())
    assert out["overall"] in {"pass", "partial"}
    assert out["ok"] is True
    assert "honest_note" in out
    assert "浏览器" in out["honest_note"] or "未执行" in out["honest_note"]
    names = {c["name"] for c in out["checks"]}
    assert "document_shell" in names


def test_verify_html_fail_missing_shell() -> None:
    gw = build_default_gateway(_MemStore())

    async def _run() -> dict[str, Any]:
        return await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"content": "just plain text no tags"},
        )

    out = asyncio.run(_run())
    assert out["overall"] == "fail"
    assert out["ok"] is False


def test_verify_html_from_artifact() -> None:
    store = _MemStore()
    gw = build_default_gateway(store)

    async def _run() -> dict[str, Any]:
        created = await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "generate_html_document",
            {
                "title": "meet.html",
                "marker": "mk-1",
                "body": "<input name='t'><button>ok</button>",
            },
        )
        return await gw.invoke(
            _P(),  # type: ignore[arg-type]
            "verify_html_document",
            {"artifact_id": created["artifact_id"]},
        )

    out = asyncio.run(_run())
    assert "checks" in out
    assert out["source"] == "artifact"


def test_tool_listed_in_schemas() -> None:
    schemas = {
        s["function"]["name"]: s["function"]
        for s in __import__(
            "pico_orchestrator.tools_builtin", fromlist=["openai_tool_schemas"]
        ).openai_tool_schemas()
    }
    assert "verify_html_document" in schemas
