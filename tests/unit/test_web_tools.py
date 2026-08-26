"""#507 web_search / web_fetch: SSRF deny, allowlist, DS adapter, usage emit."""

from __future__ import annotations

import ipaddress
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.web_guard import (
    assert_public_http_url,
    assert_resolved_public,
    parse_public_http_url,
)
from pico_orchestrator.web_tools import (
    _FETCH_TIMEOUT,
    _SEARCH_TIMEOUT,
    _parse_ds_response,
    _source_item,
    attach_teacher_sources,
    web_fetch_handler,
    web_search_handler,
)


@dataclass
class P:
    school_id: str = "school-a"
    membership_id: str = "m1"
    scopes: list[str] | None = None


def _fake_async_client(handler):
    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            del a, k

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a: object) -> bool:
            del a
            return False

        async def get(self, url: str, **kwargs: object):
            return await handler("GET", url, kwargs)

        async def post(self, url: str, **kwargs: object):
            return await handler("POST", url, kwargs)

    return FakeClient


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "https://localhost/admin",
        "http://10.1.2.3/x",
        "http://192.168.0.9/",
        "http://172.16.5.4/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://0.0.0.0/",
        "http://2130706433/",
        "file:///etc/passwd",
        "ftp://example.com/a",
        "https://pico.aivia.asia/login",
        "https://mcu.asia/",
        "http://metadata.google.internal/",
        "http://example.com:18765/",
        "http://pico-api/health",
    ],
)
def test_parse_denies_intranet_and_admin(url: str) -> None:
    with pytest.raises(ToolError) as ei:
        parse_public_http_url(url)
    assert ei.value.code in {"web.denied", "tool.invalid_arguments"}
    assert "http" in ei.value.message.lower() or "拒绝" in ei.value.message or "仅支持" in ei.value.message


def test_parse_allows_public_https_syntax() -> None:
    t = parse_public_http_url("https://example.com/path?q=1")
    assert t.scheme == "https"
    assert t.host == "example.com"
    assert t.hostname_is_ip is False


@pytest.mark.asyncio
async def test_dns_to_private_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pico_orchestrator.web_guard._resolve_ips",
        lambda host: [ipaddress.ip_address("10.9.8.7")],
    )
    with pytest.raises(ToolError) as ei:
        await assert_public_http_url("https://internal-looking.example")
    assert ei.value.code == "web.denied"
    assert "内网" in ei.value.message


@pytest.mark.asyncio
async def test_web_fetch_loopback_denied_before_http() -> None:
    with pytest.raises(ToolError) as ei:
        await web_fetch_handler(P(), {"url": "http://127.0.0.1:18765/health"})
    assert ei.value.code == "web.denied"


@pytest.mark.asyncio
async def test_web_fetch_public_page_truncated_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pico_orchestrator.web_guard._resolve_ips",
        lambda host: [ipaddress.ip_address("93.184.216.34")],
    )

    async def handler(method: str, url: str, kwargs: object) -> object:
        del method, kwargs
        assert url.startswith("https://example.com")
        return type(
            "Resp",
            (),
            {
                "status_code": 200,
                "headers": {"content-type": "text/html; charset=utf-8"},
                "content": b"<html><head><title>Lesson</title></head><body><h1>Lesson</h1><p>Visible fact 42</p></body></html>",
            },
        )()

    monkeypatch.setattr(
        "pico_orchestrator.web_tools.httpx.AsyncClient", _fake_async_client(handler)
    )
    captured: list[dict[str, Any]] = []

    async def fake_record(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr("app.usage_ledger.record_usage_event", fake_record)
    out = await web_fetch_handler(P(), {"url": "https://example.com/page"})
    assert out["retrieved"] is True
    assert "Visible fact 42" in out["text"]
    assert out["sources"][0]["url"].startswith("https://example.com")
    assert out["title"] == "Lesson"
    assert captured and captured[0]["kind"] == "search"
    assert captured[0]["source"] == "web_fetch"
    assert captured[0]["extra"]["host"] == "example.com"
    assert "price" not in (captured[0]["extra"] or {})


@pytest.mark.asyncio
async def test_web_fetch_redirect_to_loopback_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pico_orchestrator.web_guard._resolve_ips",
        lambda host: [ipaddress.ip_address("93.184.216.34")],
    )

    async def handler(method: str, url: str, kwargs: object) -> object:
        del method, url, kwargs
        return type(
            "Resp",
            (),
            {
                "status_code": 302,
                "headers": {"location": "http://127.0.0.1/secret"},
                "content": b"",
            },
        )()

    monkeypatch.setattr(
        "pico_orchestrator.web_tools.httpx.AsyncClient", _fake_async_client(handler)
    )
    with pytest.raises(ToolError) as ei:
        await web_fetch_handler(P(), {"url": "https://example.com/go"})
    assert ei.value.code == "web.denied"


def test_parse_ds_response_extracts_citations() -> None:
    body = {
        "output_text": "See [MOE](https://www.gov.cn/zhengce/2024-01/01/content.htm)",
        "output": [
            {
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "课标"},
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "课标已发布",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://www.gov.cn/zhengce/2024-01/01/content.htm",
                                "title": "MOE",
                            }
                        ],
                    }
                ],
            },
        ],
    }
    parsed = _parse_ds_response(body, query="课标")
    assert parsed["honest_miss"] is False
    assert parsed["retrieved"] is True
    assert any("gov.cn" in s["url"] for s in parsed["sources"])
    assert "来源" in parsed["teacher_sources_md"]


def test_parse_ds_empty_is_honest_miss() -> None:
    parsed = _parse_ds_response({"output": []}, query="nothing")
    assert parsed["honest_miss"] is True
    assert parsed["sources"] == []
    assert "未检索" in parsed["message"]


def test_parse_ds_web_search_call_open_page_becomes_source() -> None:
    """Live #507 shape: DS web_search_call.action.open_page has the URL;
    the message is prose without annotations. Must not lie with 未检索.
    """
    page = "https://www.jiemian.com/article/1234567.html"
    body = {
        "id": "resp_live_shape",
        "object": "response",
        "status": "completed",
        "output_text": (
            "UTC 日期 2026-08-13。界面新闻报道 DeepSeek-V4-Pro-0813 发布，"
            "模型未在正文里放 markdown 链接。"
        ),
        "output": [
            {
                "id": "ws_search",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "DeepSeek-V4-Pro-0813 界面新闻"},
            },
            {
                "id": "ws_open",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "open_page", "url": page},
            },
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": (
                            "UTC 日期 2026-08-13。界面新闻报道 DeepSeek-V4-Pro-0813 发布，"
                            "模型未在正文里放 markdown 链接。"
                        ),
                    }
                ],
            },
        ],
    }
    parsed = _parse_ds_response(body, query="今日 DeepSeek 新闻")
    assert parsed["honest_miss"] is False
    assert parsed["retrieved"] is True
    assert any(s["url"].startswith("https://www.jiemian.com/") for s in parsed["sources"])
    assert page in parsed["teacher_sources_md"]
    assert "来源" in parsed["teacher_sources_md"]
    assert "未检索" not in parsed["message"]
    assert "界面新闻" in parsed["excerpt"]


def test_parse_ds_excerpt_markdown_link_becomes_source() -> None:
    body = {
        "output_text": "据 [界面新闻](https://www.jiemian.com/article/abc.html) 报道。",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "据 [界面新闻](https://www.jiemian.com/article/abc.html) 报道。",
                    }
                ],
            }
        ],
    }
    parsed = _parse_ds_response(body, query="新闻")
    assert parsed["honest_miss"] is False
    assert parsed["retrieved"] is True
    assert any("jiemian.com" in s["url"] for s in parsed["sources"])
    assert "https://www.jiemian.com/article/abc.html" in parsed["teacher_sources_md"]


def test_parse_ds_excerpt_without_urls_is_honest_miss() -> None:
    long_text = (
        "今日 UTC 日期为 2026-08-13。"
        "界面新闻报道 DeepSeek-V4-Pro-0813 发布，但正文没有给出网址。"
    ) * 8
    assert len(long_text) > 200
    body = {
        "output_text": long_text,
        "output": [
            {
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "今日新闻"},
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": long_text}],
            },
        ],
    }
    parsed = _parse_ds_response(body, query="今日新闻")
    assert parsed["honest_miss"] is True
    assert parsed["retrieved"] is False
    assert parsed["sources"] == []
    assert "未检索" in parsed["message"]
    assert parsed["teacher_sources_md"] == "未检索到可用来源"
    assert len(parsed["excerpt"]) > 100


def test_parse_ds_web_search_call_loopback_not_sourced() -> None:
    body = {
        "output_text": "检索跑过了，但唯一打开的地址是内网。",
        "output": [
            {
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "open_page", "url": "http://127.0.0.1/"},
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "检索跑过了，但唯一打开的地址是内网。"}],
            },
        ],
    }
    parsed = _parse_ds_response(body, query="x")
    assert parsed["sources"] == []
    assert parsed["honest_miss"] is True
    assert parsed["retrieved"] is False
    assert all("127.0.0.1" not in (s.get("url") or "") for s in parsed["sources"])
    assert "未检索" in parsed["teacher_sources_md"]
    assert parsed["excerpt"]  # facts may still be used; do not claim sources


def test_search_timeout_allows_ds_multi_hop() -> None:
    assert _SEARCH_TIMEOUT >= 90
    assert _FETCH_TIMEOUT == 12.0


def test_source_item_strips_ds_ws_call_id_fragment() -> None:
    dirty = (
        "http://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620485.html"
        "#ws_call_id=call_01_RirHwWpDhHZJHxExk87Q6361"
    )
    item = _source_item(title=dirty, url=dirty)
    assert item is not None
    assert item["url"] == (
        "http://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620485.html"
    )
    assert "#ws_call_id" not in item["url"]
    assert "#ws_call_id" not in item["title"]
    parsed = _parse_ds_response(
        {
            "output_text": "课标已发布",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {"type": "open_page", "url": dirty},
                }
            ],
        },
        query="课标",
    )
    assert parsed["honest_miss"] is False
    assert all("#ws_call_id" not in (s.get("url") or "") for s in parsed["sources"])
    assert any("moe.gov.cn" in s["url"] for s in parsed["sources"])


@pytest.mark.asyncio
async def test_mixed_public_and_poison_aaaa_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pico_orchestrator.web_guard._resolve_ips",
        lambda host: [
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("127.0.0.1"),
        ],
    )
    target = await assert_public_http_url("https://zh.wikipedia.org/wiki/x")
    assert target.host == "zh.wikipedia.org"


def test_all_private_resolved_ips_still_denied() -> None:
    with pytest.raises(ToolError) as ei:
        assert_resolved_public(
            "internal.example",
            [ipaddress.ip_address("10.1.2.3"), ipaddress.ip_address("127.0.0.1")],
        )
    assert ei.value.code == "web.denied"


def test_extracted_url_strips_trailing_backtick() -> None:
    item = _source_item(title="Example", url="https://www.example.com`")
    assert item is not None
    assert "`" not in item["url"]
    assert item["url"].startswith("https://www.example.com")
    wrapped = _source_item(title="https://www.example.com`", url="`https://www.example.com`")
    assert wrapped is not None
    assert wrapped["url"].startswith("https://www.example.com")
    assert "`" not in wrapped["url"]
    parsed = _parse_ds_response(
        {
            "output_text": "See https://www.example.com` for the page.",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {"type": "open_page", "url": "https://www.example.com`"},
                }
            ],
        },
        query="example.com",
    )
    assert parsed["honest_miss"] is False
    assert parsed["retrieved"] is True
    assert all("`" not in (s.get("url") or "") for s in parsed["sources"])
    assert any(s["url"].startswith("https://www.example.com") for s in parsed["sources"])


@pytest.mark.asyncio
async def test_web_search_uses_deepseek_not_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("PICO_SEARCH_PROVIDER", "deepseek")

    posts: list[str] = []

    async def handler(method: str, url: str, kwargs: object) -> object:
        del method
        posts.append(url)
        payload = (kwargs or {}).get("json") if isinstance(kwargs, dict) else None
        tools = (payload or {}).get("tools")
        assert tools == [{"type": "web_search"}]
        assert (payload or {}).get("input") == "今日公开新闻"
        instructions = str((payload or {}).get("instructions") or "")
        assert "[title](https://...)" in instructions or "markdown" in instructions.lower()

        class FakeResp:
            status_code = 200

            def json(self) -> dict[str, Any]:
                return {
                    "output_text": "news",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "hit",
                                    "annotations": [
                                        {
                                            "type": "url_citation",
                                            "title": "News",
                                            "url": "https://www.example.com/n",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }

        return FakeResp()

    monkeypatch.setattr(
        "pico_orchestrator.web_tools.httpx.AsyncClient", _fake_async_client(handler)
    )
    captured: list[dict[str, Any]] = []

    async def fake_record(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr("app.usage_ledger.record_usage_event", fake_record)
    out = await web_search_handler(P(), {"query": "今日公开新闻"})
    assert out["retrieved"] is True
    assert out["provider"] == "deepseek"
    assert posts and "responses" in posts[0]
    assert captured[0]["kind"] == "search"
    assert captured[0]["source"] == "web_search"
    assert captured[0]["extra"]["query_count"] == 1
    assert captured[0]["extra"]["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_web_search_no_key_honest_miss_without_tavily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    captured: list[dict[str, Any]] = []

    async def fake_record(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr("app.usage_ledger.record_usage_event", fake_record)
    out = await web_search_handler(P(), {"query": "今日公开新闻"})
    assert out["honest_miss"] is True
    assert out["sources"] == []
    assert "未检索" in out["message"]
    assert captured and captured[0]["kind"] == "search"


def test_gateway_allowlist_includes_web_pair() -> None:
    gw = build_default_gateway()
    names = {t["name"] for t in gw.list_tools()}
    assert "web_search" in names
    assert "web_fetch" in names
    schemas = {s["function"]["name"] for s in openai_tool_schemas(gw)}
    assert "web_search" in schemas
    assert "web_fetch" in schemas
    assert "web_search" in ALLOWED_GATEWAY_TOOLS
    assert "web_fetch" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_preview_inspect" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_browser_open" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_browser_screenshot" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_document_open" in ALLOWED_GATEWAY_TOOLS
    assert "edit_docx_document" in ALLOWED_GATEWAY_TOOLS
    assert "edit_pptx_document" in ALLOWED_GATEWAY_TOOLS
    assert "generate_xlsx_document" in ALLOWED_GATEWAY_TOOLS
    assert "edit_xlsx_document" in ALLOWED_GATEWAY_TOOLS
    assert "render_document" in ALLOWED_GATEWAY_TOOLS
    assert "inspect_document" in ALLOWED_GATEWAY_TOOLS
    assert "verify_document" in ALLOWED_GATEWAY_TOOLS
    assert "generate_image" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_pptx_lib" in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert "kb_search" in ALLOWED_GATEWAY_TOOLS
    assert len(ALLOWED_GATEWAY_TOOLS) == 26


def test_attach_teacher_sources_footer() -> None:
    text = attach_teacher_sources(
        "答案正文",
        [
            (
                "web_search",
                {
                    "retrieved": True,
                    "sources": [
                        {
                            "title": "Gov",
                            "url": "https://www.gov.cn/a",
                            "snippet": "x",
                        }
                    ],
                },
            )
        ],
    )
    assert "https://www.gov.cn/a" in text
    assert "来源" in text
    miss = attach_teacher_sources(
        "闲聊",
        [("web_search", {"retrieved": False, "honest_miss": True, "sources": []})],
    )
    assert "未检索" in miss
    plain = attach_teacher_sources("普通问答", [("workspace_write_file", {"title": "a.md"})])
    assert plain == "普通问答"


def test_contract_no_longer_bans_all_web() -> None:
    text = (ROOT / "docs" / "contracts" / "tools.md").read_text(encoding="utf-8")
    assert "web_search" in text
    assert "web_fetch" in text
    assert "- Web search / fetch" not in text
    assert "Unrestricted" in text or "unrestricted" in text.lower() or "任意" in text
