"""Allowlisted web_search (DeepSeek official) + web_fetch (public http(s)).

Thin adapters only:
  web_search → DeepSeek Responses API ``tools: [{type: web_search}]``
  web_fetch  → SSRF-guarded GET, truncated text

Optional Tavily is a fallback when ``TAVILY_API_KEY`` is set. Tests and
green CI must not require it. Never invent sources.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from pico_orchestrator.gateway import Principal, ToolError
from pico_orchestrator.provider import resolve_provider
from pico_orchestrator.usage_hook import emit_search_usage
from pico_orchestrator.web_guard import assert_public_http_url, parse_public_http_url

logger = logging.getLogger(__name__)

_MAX_QUERY = 500
_MAX_FETCH_BYTES = 512_000
_MAX_TEXT = 24_000
_FETCH_TIMEOUT = 12.0
_SEARCH_TIMEOUT = 35.0
_MAX_REDIRECTS = 3
_MAX_SOURCES = 8
_USER_AGENT = "PicoBot/1.0 (+https://github.com/juanwan99/pico; allowlisted-fetch)"

_MD_LINK = re.compile(r"\[([^\]]{1,200})\]\((https?://[^)\s]{1,500})\)")
_BARE_URL = re.compile(r"https?://[^\s)\]>'\"<>]{8,500}")

_SCRIPT_RE = re.compile(r"(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>")
_TAG_RE = re.compile(r"(?is)<[^>]+>")
_WS_RE = re.compile(r"[ \t]+\n")
_MULTI_NL = re.compile(r"\n{3,}")


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "iframe"}:
            self._skip += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr", "section"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "iframe"} and self._skip:
            self._skip -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "tr", "section"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        joined = " ".join(self._chunks)
        joined = _WS_RE.sub("\n", joined)
        joined = _MULTI_NL.sub("\n\n", joined)
        return joined.strip()


def _required_query(args: dict[str, Any]) -> str:
    value = args.get("query")
    if not isinstance(value, str) or not value.strip():
        raise ToolError("tool.invalid_arguments", "query 必须是非空字符串")
    text = value.strip()
    if len(text) > _MAX_QUERY:
        raise ToolError("tool.invalid_arguments", f"query 超过 {_MAX_QUERY} 字符")
    return text


def _source_item(*, title: str, url: str, snippet: str = "") -> dict[str, str] | None:
    u = (url or "").strip()
    if not u:
        return None
    try:
        parse_public_http_url(u)
    except ToolError:
        return None
    t = (title or "").strip() or u
    s = (snippet or "").strip().replace("\n", " ")
    return {"title": t[:200], "url": u[:500], "snippet": s[:400]}


def _dedupe_sources(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in items:
        url = item.get("url") or ""
        if url in seen:
            continue
        seen.add(url)
        out.append(item)
        if len(out) >= _MAX_SOURCES:
            break
    return out


def _extract_markdown_sources(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for title, url in _MD_LINK.findall(text or ""):
        item = _source_item(title=title, url=url)
        if item:
            found.append(item)
    if not found:
        for url in _BARE_URL.findall(text or ""):
            item = _source_item(title=url, url=url.rstrip(".,;"))
            if item:
                found.append(item)
    return found


def _parse_ds_response(body: dict[str, Any], *, query: str) -> dict[str, Any]:
    sources: list[dict[str, str]] = []
    texts: list[str] = []

    def walk(obj: Any, depth: int = 0) -> None:
        if depth > 12:
            return
        if isinstance(obj, dict):
            otype = str(obj.get("type") or "")
            if otype in {"url_citation", "citation", "source", "web_search_result"} or (
                obj.get("url") and otype in {"", "url_citation"}
            ):
                item = _source_item(
                    title=str(obj.get("title") or obj.get("url") or ""),
                    url=str(obj.get("url") or obj.get("href") or ""),
                    snippet=str(
                        obj.get("snippet") or obj.get("text") or obj.get("content") or ""
                    ),
                )
                if item:
                    sources.append(item)
            if isinstance(obj.get("text"), str) and otype in {"", "output_text", "text"}:
                texts.append(str(obj.get("text")))
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    walk(val, depth + 1)
        elif isinstance(obj, list):
            for el in obj:
                walk(el, depth + 1)

    walk(body.get("output") or body)
    output_text = str(body.get("output_text") or "").strip()
    if output_text:
        texts.append(output_text)
    excerpt = "\n".join(t.strip() for t in texts if t and t.strip()).strip()
    sources.extend(_extract_markdown_sources(excerpt))
    sources = _dedupe_sources(sources)
    honest_miss = not sources
    retrieved = not honest_miss
    message = (
        "未检索到可用来源"
        if honest_miss
        else f"已检索 {len(sources)} 条来源"
    )
    return {
        "query": query,
        "retrieved": retrieved and not honest_miss,
        "honest_miss": honest_miss,
        "message": message,
        "sources": sources,
        "excerpt": excerpt[:_MAX_TEXT],
        "provider": "deepseek",
        "teacher_sources_md": _teacher_sources_md(sources, honest_miss=honest_miss),
    }


def _teacher_sources_md(sources: list[dict[str, str]], *, honest_miss: bool) -> str:
    if honest_miss or not sources:
        return "未检索到可用来源"
    lines = ["来源："]
    for item in sources:
        title = item.get("title") or item.get("url") or "来源"
        url = item.get("url") or ""
        lines.append(f"- [{title}]({url})")
    return "\n".join(lines)


def _responses_url(base_url: str) -> str:
    root = (base_url or "https://api.deepseek.com").rstrip("/")
    if root.endswith("/v1"):
        return f"{root}/responses"
    return f"{root}/responses"


async def _deepseek_web_search(query: str) -> dict[str, Any]:
    provider = resolve_provider()
    if provider is None or not (provider.api_key or "").strip():
        return {
            "query": query,
            "retrieved": False,
            "honest_miss": True,
            "message": "未检索：未配置模型密钥，无法调用 DeepSeek 官方 web_search。",
            "sources": [],
            "excerpt": "",
            "provider": "deepseek",
            "teacher_sources_md": "未检索到可用来源",
        }
    if provider.name != "deepseek":
        # Product brain is DeepSeek; do not send DS web_search to Kimi.
        tavily = await _tavily_web_search(query)
        if tavily is not None:
            return tavily
        return {
            "query": query,
            "retrieved": False,
            "honest_miss": True,
            "message": "未检索：当前提供方不是 DeepSeek，官方 web_search 不可用。",
            "sources": [],
            "excerpt": "",
            "provider": provider.name,
            "teacher_sources_md": "未检索到可用来源",
        }
    url = _responses_url(provider.base_url)
    payload = {
        "model": provider.model or "deepseek-v4-flash",
        "input": query,
        "tools": [{"type": "web_search"}],
        "tool_choice": {"type": "web_search"},
    }
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 404 and url.endswith("/v1/responses"):
                alt = url[: -len("/v1/responses")] + "/responses"
                resp = await client.post(alt, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise ToolError("tool.upstream_error", "联网检索超时，请稍后重试。") from exc
    except httpx.HTTPError as exc:
        raise ToolError("tool.upstream_error", "联网检索失败，请稍后重试。") from exc
    if resp.status_code >= 400:
        logger.info("deepseek web_search http %s", resp.status_code)
        raise ToolError(
            "tool.upstream_error",
            f"DeepSeek 官方检索返回 HTTP {resp.status_code}，未检索到可用来源。",
        )
    try:
        body = resp.json()
    except json.JSONDecodeError as exc:
        raise ToolError("tool.upstream_error", "检索响应无法解析。") from exc
    if not isinstance(body, dict):
        raise ToolError("tool.upstream_error", "检索响应格式异常。")
    parsed = _parse_ds_response(body, query=query)
    parsed["http_status"] = resp.status_code
    return parsed


async def _tavily_web_search(query: str) -> dict[str, Any] | None:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": 5},
            )
    except httpx.HTTPError:
        logger.info("tavily search transport failed")
        return None
    if resp.status_code >= 400:
        return None
    try:
        body = resp.json()
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    sources: list[dict[str, str]] = []
    for row in body.get("results") or []:
        if not isinstance(row, dict):
            continue
        item = _source_item(
            title=str(row.get("title") or ""),
            url=str(row.get("url") or ""),
            snippet=str(row.get("content") or row.get("snippet") or ""),
        )
        if item:
            sources.append(item)
    sources = _dedupe_sources(sources)
    honest_miss = not sources
    return {
        "query": query,
        "retrieved": not honest_miss,
        "honest_miss": honest_miss,
        "message": "未检索到可用来源" if honest_miss else f"已检索 {len(sources)} 条来源",
        "sources": sources,
        "excerpt": str(body.get("answer") or "")[:_MAX_TEXT],
        "provider": "tavily",
        "teacher_sources_md": _teacher_sources_md(sources, honest_miss=honest_miss),
    }


def _search_provider_pref() -> str:
    return (os.environ.get("PICO_SEARCH_PROVIDER") or "deepseek").strip().lower()


async def web_search_handler(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    query = _required_query(args)
    pref = _search_provider_pref()
    result: dict[str, Any] | None = None
    err: ToolError | None = None
    try:
        if pref == "tavily":
            result = await _tavily_web_search(query)
            if result is None:
                result = await _deepseek_web_search(query)
        else:
            result = await _deepseek_web_search(query)
            if result.get("honest_miss") and pref in {"auto", "deepseek"}:
                fallback = await _tavily_web_search(query)
                if fallback is not None and not fallback.get("honest_miss"):
                    result = fallback
    except ToolError as exc:
        err = exc
        result = {
            "query": query,
            "retrieved": False,
            "honest_miss": True,
            "message": exc.message,
            "sources": [],
            "excerpt": "",
            "provider": "deepseek",
            "teacher_sources_md": "未检索到可用来源",
        }
    assert result is not None
    extra = {
        "provider": result.get("provider") or "deepseek",
        "tool": "web_search",
        "query_count": 1,
        "source_count": len(result.get("sources") or []),
        "honest_miss": bool(result.get("honest_miss")),
    }
    await emit_search_usage(
        principal,
        tool="web_search",
        extra=extra,
        ok=err is None and not result.get("honest_miss"),
    )
    if err is not None and not result.get("sources"):
        # Still return structured miss so the model can say 未检索 honestly.
        return result
    return result


def _html_to_text(raw: str) -> str:
    parser = _HTMLText()
    try:
        parser.feed(_SCRIPT_RE.sub(" ", raw))
        parser.close()
        text = parser.text()
    except Exception:  # noqa: BLE001
        text = _TAG_RE.sub(" ", html_lib.unescape(raw))
        text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def _content_type_ok(value: str | None) -> bool:
    ct = (value or "").split(";")[0].strip().lower()
    if not ct:
        return True
    return ct.startswith(
        (
            "text/",
            "application/json",
            "application/xml",
            "application/xhtml",
            "application/javascript",
            "application/ld+json",
        )
    )


async def _fetch_once(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html, text/plain, application/json"},
        follow_redirects=False,
    )


async def web_fetch_handler(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    raw_url = args.get("url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ToolError("tool.invalid_arguments", "url 必须是非空字符串")
    current = raw_url.strip()
    last_error: ToolError | None = None
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, trust_env=False) as client:
            for _hop in range(_MAX_REDIRECTS + 1):
                target = await assert_public_http_url(current)
                try:
                    resp = await _fetch_once(client, target.url)
                except httpx.TimeoutException as exc:
                    raise ToolError("web.fetch_failed", "页面读取超时") from exc
                except httpx.HTTPError as exc:
                    raise ToolError("web.fetch_failed", "无法读取该页面") from exc
                if resp.status_code in {301, 302, 303, 307, 308}:
                    loc = resp.headers.get("location") or ""
                    if not loc:
                        raise ToolError("web.fetch_failed", "重定向缺少目标地址")
                    if loc.startswith("/"):
                        parsed = urlparse(target.url)
                        loc = f"{parsed.scheme}://{parsed.netloc}{loc}"
                    current = loc
                    continue
                if resp.status_code >= 400:
                    raise ToolError(
                        "web.fetch_failed",
                        f"页面返回 HTTP {resp.status_code}，无法读取正文。",
                    )
                if not _content_type_ok(resp.headers.get("content-type")):
                    raise ToolError("web.denied", "拒绝读取非文本页面")
                raw = resp.content[: _MAX_FETCH_BYTES + 1]
                truncated_raw = len(raw) > _MAX_FETCH_BYTES
                raw = raw[:_MAX_FETCH_BYTES]
                charset = "utf-8"
                ct = resp.headers.get("content-type") or ""
                if "charset=" in ct.lower():
                    charset = ct.split("charset=", 1)[-1].split(";")[0].strip() or "utf-8"
                try:
                    decoded = raw.decode(charset, errors="replace")
                except LookupError:
                    decoded = raw.decode("utf-8", errors="replace")
                ctype = (resp.headers.get("content-type") or "").lower()
                if "html" in ctype or decoded.lstrip()[:15].lower().startswith(
                    ("<!doctype", "<html")
                ):
                    text = _html_to_text(decoded)
                else:
                    text = decoded
                truncated = truncated_raw or len(text) > _MAX_TEXT
                text = text[:_MAX_TEXT]
                host = target.host
                result = {
                    "url": target.url,
                    "host": host,
                    "status": resp.status_code,
                    "retrieved": bool(text.strip()),
                    "honest_miss": not bool(text.strip()),
                    "truncated": truncated,
                    "message": (
                        "未读取到正文"
                        if not text.strip()
                        else ("已读取页面（已截断）" if truncated else "已读取页面")
                    ),
                    "title": host,
                    "text": text,
                    "sources": (
                        [{"title": host, "url": target.url, "snippet": text[:180]}]
                        if text.strip()
                        else []
                    ),
                    "teacher_sources_md": (
                        f"来源：\n- [{host}]({target.url})"
                        if text.strip()
                        else "未检索到可用来源"
                    ),
                }
                await emit_search_usage(
                    principal,
                    tool="web_fetch",
                    extra={
                        "provider": "pico_fetch",
                        "tool": "web_fetch",
                        "host": host,
                        "status": resp.status_code,
                        "truncated": truncated,
                    },
                    ok=bool(text.strip()),
                )
                return result
            raise ToolError("web.denied", "重定向次数过多")
    except ToolError as exc:
        last_error = exc
        host = ""
        try:
            host = parse_public_http_url(current).host
        except ToolError:
            host = urlparse(current).hostname or ""
        await emit_search_usage(
            principal,
            tool="web_fetch",
            extra={
                "provider": "pico_fetch",
                "tool": "web_fetch",
                "host": host,
                "error_code": exc.code,
            },
            ok=False,
        )
        raise last_error from None


def teacher_sources_footer(tool_results: list[tuple[str, dict[str, Any]]] | None) -> str:
    """Append visible sources (or honest 未检索) when search/fetch ran."""
    hits = [
        (name, payload)
        for name, payload in (tool_results or [])
        if name in {"web_search", "web_fetch"} and isinstance(payload, dict)
    ]
    if not hits:
        return ""
    sources: list[dict[str, str]] = []
    for _name, payload in hits:
        for item in payload.get("sources") or []:
            if not isinstance(item, dict):
                continue
            cleaned = _source_item(
                title=str(item.get("title") or item.get("url") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("snippet") or ""),
            )
            if cleaned:
                sources.append(cleaned)
    sources = _dedupe_sources(sources)
    if sources:
        return _teacher_sources_md(sources, honest_miss=False)
    return "未检索到可用来源"


def attach_teacher_sources(
    final_text: str,
    tool_results: list[tuple[str, dict[str, Any]]] | None,
) -> str:
    footer = teacher_sources_footer(tool_results)
    if not footer:
        return final_text
    text = (final_text or "").rstrip()
    if footer.startswith("来源"):
        urls = [u for u in _BARE_URL.findall(footer)]
        if urls and any(u in text for u in urls) and "来源" in text:
            return text
        if text:
            return f"{text}\n\n{footer}"
        return footer
    # honest miss
    if "未检索" in text:
        return text
    if text:
        return f"{text}\n\n{footer}"
    return footer
