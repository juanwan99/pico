"""S2-B2 sandbox sidecar: stronger isolate, human-in-loop, egress deny."""

from __future__ import annotations

import inspect
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s2 import PNG_MAGIC
from pico_orchestrator.sandbox_view import LOGIN_COPY, render_session_view_html
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.web_guard import parse_public_http_url
from sandbox_worker.ports import SANDBOX_DEFAULT_PORT, assert_listen_port
from sandbox_worker.runtime import HUMAN_LOGIN_COPY, RUNTIME, automation_hostile_reason

@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self, *, run_id: str | None = None) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._run_id = run_id
        self._task_id = "task-s1"

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
        import base64

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
            body = content
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": body,
                "kind": kind,
                "run_id": self._run_id,
                "task_id": self._task_id,
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


PAGE = """<!DOCTYPE html>
<html><head><title>教案首页</title></head>
<body><h1>第一课</h1><p>hello</p></body></html>
"""


@pytest.mark.asyncio


PUBLIC_HTML = (
    "<!DOCTYPE html><html><head><title>Example Domain</title></head>"
    "<body><h1>Example Domain</h1><p>public demo</p></body></html>"
)


@pytest.fixture
def embedded_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")

    async def fake_fetch(url: str) -> tuple[str, str]:
        parse_public_http_url(url)
        return url, PUBLIC_HTML

    monkeypatch.setattr(RUNTIME, "_fetch_html", fake_fetch)
    RUNTIME._sessions.clear()
    yield RUNTIME
    RUNTIME._sessions.clear()


@pytest.mark.asyncio
async def test_browser_open_public_page_and_view_copy(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    opened = await gw.invoke(
        owner, "sandbox_browser_open", {"url": "https://example.com/"}
    )
    assert opened["ok"] is True
    assert opened["session_id"].startswith("sbox_")
    assert opened["title"] == "Example Domain"
    assert HUMAN_LOGIN_COPY in opened["human_copy"]
    assert "不要在聊天里发送密码" in opened["message"]
    assert opened["view_path"].startswith("/v1/sandbox/sessions/")
    shot = await gw.invoke(
        owner, "sandbox_browser_screenshot", {"session_id": opened["session_id"]}
    )
    assert shot["mime"] == "image/png"
    sess = embedded_runtime.get(opened["session_id"])
    assert sess is not None
    assert sess.screenshot_png.startswith(PNG_MAGIC)
    html = render_session_view_html(
        session_id=opened["session_id"],
        screenshot_path="/shot",
        page_url=opened["url"],
        workspace_id=opened["workspace_id"],
        input_path="/input",
    )
    assert LOGIN_COPY in html
    assert "不要在聊天里发送密码" in html


@pytest.mark.asyncio
async def test_browser_open_denies_loopback_18765(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "sandbox_browser_open",
            {"url": "http://127.0.0.1:18765/health"},
        )
    assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_browser_open_denies_intranet_and_metadata(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    for url in (
        "http://10.1.2.3/",
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1/",
    ):
        with pytest.raises(ToolError) as denied:
            await gw.invoke(owner, "sandbox_browser_open", {"url": url})
        assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_browser_cross_account_denied(embedded_runtime) -> None:
    store = MemoryArtifactStore(run_id="run-b2")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    outsider = P("school-a", "member-b", ["ai:run"])
    opened = await gw.invoke(
        owner, "sandbox_browser_open", {"url": "https://example.com/"}
    )
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            outsider,
            "sandbox_browser_screenshot",
            {"session_id": opened["session_id"]},
        )
    assert denied.value.code == "sandbox.session_not_found"


@pytest.mark.asyncio
async def test_wechat_jiaowu_fail_honestly_not_required(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as wechat:
        await gw.invoke(
            owner,
            "sandbox_browser_open",
            {"url": "https://open.weixin.qq.com/connect/qrconnect"},
        )
    assert wechat.value.code == "sandbox.site_blocks_automation"
    assert "微信" in wechat.value.message
    assert "不要在聊天里发送密码" in wechat.value.message
    with pytest.raises(ToolError) as jiaowu:
        await gw.invoke(
            owner,
            "sandbox_browser_open",
            {"url": "https://jwxt.example.edu.cn/login"},
        )
    assert jiaowu.value.code == "sandbox.site_blocks_automation"
    assert "教务" in jiaowu.value.message
    assert automation_hostile_reason("https://example.com/") is None


@pytest.mark.asyncio
async def test_password_input_not_echoed(embedded_runtime) -> None:
    owner_sess = await embedded_runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-b2",
        url="https://example.com/",
    )
    sess = embedded_runtime.require_owner(
        owner_sess["session_id"], school_id="school-a", membership_id="member-a"
    )
    out = embedded_runtime.apply_input(
        sess, text="super-secret-pass", password=True, field="password"
    )
    blob = str(out)
    assert "super-secret-pass" not in blob
    assert out.get("password") is None
    assert "••••" not in str(out.get("message") or "") or "super-secret-pass" not in blob


@pytest.mark.asyncio
async def test_browser_usage_emit_kind_sandbox_no_money(embedded_runtime) -> None:
    captured: list[dict] = []

    async def fake_record(**kwargs):
        captured.append(kwargs)

    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    with patch("app.usage_ledger.record_usage_event", fake_record):
        await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    rows = [row for row in captured if row.get("kind") == "sandbox"]
    assert rows
    for row in rows:
        assert row.get("source") == "sandbox"
        extra = row.get("extra") or {}
        assert "duration_ms" in extra
        assert extra.get("workspace_id") or extra.get("session_id")
        joined = " ".join(extra.keys()).lower()
        for banned in ("price", "currency", "cost", "charge", "billing", "amount"):
            assert banned not in joined


def test_worker_refuses_product_ports() -> None:
    with pytest.raises(RuntimeError):
        assert_listen_port(8080)
    with pytest.raises(RuntimeError):
        assert_listen_port(18088)
    with pytest.raises(RuntimeError):
        assert_listen_port(18765)
    assert assert_listen_port(SANDBOX_DEFAULT_PORT) == 18767


def test_worker_source_does_not_bind_product_ports() -> None:
    import sandbox_worker.__main__ as mainmod
    import sandbox_worker.app as appmod
    import sandbox_worker.ports as portsmod

    src = inspect.getsource(mainmod) + inspect.getsource(appmod)
    assert "8080" not in src
    assert "18088" not in src
    # ports module names them only to refuse them
    assert "8080" in inspect.getsource(portsmod)
    assert "assert_listen_port" in inspect.getsource(portsmod)


def test_compose_sidecar_is_unprivileged_and_not_on_product_ports() -> None:
    for rel in (
        "docker-compose.host.yml",
        "docker-compose.yml",
        "docker-compose.product.yml",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "pico-sandbox:" in text
        block = _service_block(text, "pico-sandbox")
        assert "privileged: true" not in block
        assert "cap_drop:" in block
        assert "ALL" in block
        assert "no-new-privileges:true" in block
        assert 'user: "65532:65532"' in block
        assert not re.search(r'["\']8080:', block)
        assert not re.search(r'["\']18088:', block)
        assert "18767" in block
        assert "network_mode: host" not in block
    host = (ROOT / "docker-compose.host.yml").read_text(encoding="utf-8")
    assert "PICO_SANDBOX_URL: http://127.0.0.1:18767" in host
    libre = _service_block(host, "librechat")
    sandbox = _service_block(host, "pico-sandbox")
    assert sandbox != libre
    assert "18088" in libre  # product UI stays on LibreChat
    assert "18088" not in sandbox


def _service_block(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"  {name}:"):
            start = i
            break
    if start is None:
        raise AssertionError(f"missing service {name}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if (
            lines[j].startswith("  ")
            and not lines[j].startswith("    ")
            and lines[j].rstrip().endswith(":")
        ):
            end = j
            break
    return "\n".join(lines[start:end])
