"""SSRF / intranet deny for gateway web_fetch (and search URL filtering).

Allow http(s) public hosts only. Deny loopback, RFC1918, link-local, cloud
metadata, and Pico/edu admin surfaces. DNS is resolved and every address is
checked (including redirect hops).
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from pico_orchestrator.gateway import ToolError

_MAX_URL = 2048
_BLOCKED_PORTS = frozenset(
    {
        18765,  # pico-api loopback
        27017,  # mongo
        2375,
        2376,  # docker
        6443,
        10250,  # k8s
        8500,  # consul
        9200,
        9300,  # elasticsearch
    }
)

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.google.com",
        "metadata",
        "kubernetes",
        "kubernetes.default",
        "kubernetes.default.svc",
        "pico-api",
        "pico-mongo",
        "pico-meilisearch",
    }
)

_BLOCKED_HOST_SUFFIXES = (
    ".internal",
    ".local",
    ".localhost",
    ".localdomain",
    ".lan",
    ".corp",
    ".home",
    ".mcu.asia",
    ".edu-cloud.internal",
)

_BLOCKED_EXACT_ADMIN = frozenset(
    {
        "pico.aivia.asia",
        "mcu.asia",
        "metadata.google.internal",
    }
)

_PRIVATE_NETS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "192.0.0.0/29",
        "192.0.2.0/24",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::1/128",
        "::/128",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
        "2001:db8::/32",
    )
)


@dataclass(frozen=True)
class PublicHttpTarget:
    url: str
    scheme: str
    host: str
    port: int
    hostname_is_ip: bool


def _extra_deny_hosts() -> set[str]:
    raw = os.environ.get("PICO_WEB_FETCH_DENY_HOSTS", "").strip()
    if not raw:
        return set()
    return {p.strip().lower().rstrip(".") for p in raw.split(",") if p.strip()}


def _human(code: str, message: str) -> ToolError:
    return ToolError(code, message)


def _host_as_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    text = (host or "").strip().strip("[]")
    if not text:
        return None
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        pass
    if text.isdigit():
        try:
            n = int(text)
            if 0 <= n <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(n)
        except ValueError:
            return None
    if text.lower().startswith("0x"):
        try:
            n = int(text, 16)
            if 0 <= n <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(n)
        except ValueError:
            return None
    return None


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_private_ip(ip.ipv4_mapped)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified or getattr(ip, "is_site_local", False):
        return True
    return any(ip in net for net in _PRIVATE_NETS)


def _deny_host_name(host: str) -> str | None:
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return "地址缺少主机名"
    if h in _BLOCKED_HOSTS or h in _BLOCKED_EXACT_ADMIN:
        return "拒绝访问管理域或本机名"
    extras = _extra_deny_hosts()
    if h in extras:
        return "拒绝访问管理域或本机名"
    for suffix in _BLOCKED_HOST_SUFFIXES:
        if h.endswith(suffix):
            return "拒绝访问内网或链路本地地址"
    for extra in extras:
        if extra.startswith(".") and h.endswith(extra):
            return "拒绝访问管理域或本机名"
        if h.endswith("." + extra):
            return "拒绝访问管理域或本机名"
    return None


def parse_public_http_url(url: str) -> PublicHttpTarget:
    """Syntax + host/IP precheck (no DNS). Used by unit tests and fetch."""
    if not isinstance(url, str) or not url.strip():
        raise _human("tool.invalid_arguments", "url 必须是非空字符串")
    raw = url.strip()
    if len(raw) > _MAX_URL:
        raise _human("tool.invalid_arguments", f"url 超过 {_MAX_URL} 字符")
    if any(ord(ch) < 32 for ch in raw):
        raise _human("tool.invalid_arguments", "url 含非法控制字符")
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise _human("web.denied", "仅支持 http/https 公网地址")
    if parsed.username or parsed.password:
        raise _human("web.denied", "拒绝带用户名的地址")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise _human("web.denied", "地址缺少主机名")
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    if port in _BLOCKED_PORTS:
        raise _human("web.denied", "拒绝访问管理端口")
    reason = _deny_host_name(host)
    if reason:
        raise _human("web.denied", reason)
    ip = _host_as_ip(host)
    if ip is not None:
        if _is_private_ip(ip):
            raise _human("web.denied", "拒绝访问内网或链路本地地址")
        hostname_is_ip = True
    else:
        hostname_is_ip = False
    # Rebuild without fragment; keep query.
    cleaned = urlunparse(
        (scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, "")
    )
    return PublicHttpTarget(
        url=cleaned,
        scheme=scheme,
        host=host,
        port=port,
        hostname_is_ip=hostname_is_ip,
    )


def _resolve_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    found: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise _human("web.denied", f"无法解析主机名：{host}") from exc
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        addr = sockaddr[0]
        ip = _host_as_ip(str(addr))
        if ip is not None:
            found.append(ip)
    if not found:
        raise _human("web.denied", f"无法解析主机名：{host}")
    return found


def public_ips(
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    return [ip for ip in ips if not _is_private_ip(ip)]


def assert_resolved_public(host: str, ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address]) -> None:
    """Allow the host when at least one address is public.

    Mixed answers (public A + poisoned AAAA like ``2001::1`` / ``127.0.0.1``)
    used to fail closed and look like 「读不了维基」。Only deny when every
    resolved address is private.
    """
    _ = host
    if not public_ips(ips):
        raise _human("web.denied", "拒绝访问内网或链路本地地址")


_GAI_TLS = threading.local()
_ORIG_GETADDRINFO = socket.getaddrinfo


def _public_only_getaddrinfo(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
    results = _ORIG_GETADDRINFO(host, port, *args, **kwargs)
    if not getattr(_GAI_TLS, "public_only", False):
        return results
    kept = []
    for item in results:
        sockaddr = item[4] if len(item) > 4 else None
        addr = sockaddr[0] if sockaddr else ""
        ip = _host_as_ip(str(addr).split("%")[0])
        if ip is None or not _is_private_ip(ip):
            kept.append(item)
    return kept or results


if socket.getaddrinfo is _ORIG_GETADDRINFO:
    socket.getaddrinfo = _public_only_getaddrinfo  # type: ignore[assignment]


@contextmanager
def public_dns_only() -> Iterator[None]:
    """During a fetch, ignore poisoned/private A/AAAA so httpx does not connect there."""
    prev = getattr(_GAI_TLS, "public_only", False)
    _GAI_TLS.public_only = True
    try:
        yield
    finally:
        _GAI_TLS.public_only = prev


async def assert_public_http_url(url: str) -> PublicHttpTarget:
    """Full check including DNS. Safe to call before each hop."""
    target = parse_public_http_url(url)
    if target.hostname_is_ip:
        return target
    ips = await asyncio.to_thread(_resolve_ips, target.host)
    assert_resolved_public(target.host, ips)
    return target
