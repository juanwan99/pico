"""S1 isolated workspace + same-run HTML preview inspect (no host Chrome).

Isolation key: school_id + membership_id (user) + run_id.
Process-level dirs only — not a micro-VM. See docs/SANDBOX-S1.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
import secrets
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from pico_orchestrator.gateway import Principal, ToolError
from pico_orchestrator.web_guard import parse_public_http_url

logger = logging.getLogger(__name__)

PREVIEW_TTL_S = 15 * 60
IO_TIMEOUT_S = 8.0
EXEC_TIMEOUT_S = 5.0
MAX_CONTENT_CHARS = 200_000
MAX_CONTENT_BYTES = 256_000
MAX_EXEC_SOURCE = 8_000

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_ARTIFACT_IN_PATH = re.compile(
    r"(?:/api/pico)?/v1/artifacts/([^/?#]+)/content(?:/?|$)",
    re.IGNORECASE,
)
_SECRET_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "credentials",
        "secrets.json",
    }
)
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
_FORBIDDEN_EXEC_MODS = frozenset(
    {
        "os",
        "subprocess",
        "socket",
        "pathlib",
        "sys",
        "ctypes",
        "shutil",
        "importlib",
        "pty",
        "posix",
        "signal",
        "multiprocessing",
        "webbrowser",
        "http",
        "urllib",
        "requests",
        "httpx",
    }
)


def preview_signing_secret() -> bytes:
    raw = (
        os.environ.get("PICO_SANDBOX_PREVIEW_SECRET")
        or os.environ.get("PICO_JWT_SECRET")
        or ""
    ).strip()
    if len(raw) < 16:
        raw = "pico-sandbox-s1-dev-only-not-for-prod"
    return raw.encode("utf-8")


def safe_segment(value: str | None, *, fallback: str = "_") -> str:
    text = (value or "").strip()
    if not text or text in {".", ".."} or "/" in text or "\\" in text:
        return fallback
    if any(ord(ch) < 32 for ch in text):
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:128]
    return cleaned or fallback


def isolation_key(
    school_id: str,
    membership_id: str,
    run_id: str | None,
) -> str:
    run = (run_id or "").strip() or "_norun"
    return f"{school_id}\n{membership_id}\n{run}"


def workspace_id_for(
    school_id: str,
    membership_id: str,
    run_id: str | None,
) -> str:
    digest = hashlib.sha256(isolation_key(school_id, membership_id, run_id).encode()).hexdigest()
    return f"ws_{digest[:16]}"


def sandbox_root() -> Path:
    raw = os.environ.get("PICO_SANDBOX_ROOT", "").strip()
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "pico-sandbox-s1"


def isolation_dir(
    school_id: str,
    membership_id: str,
    run_id: str | None,
) -> Path:
    return (
        sandbox_root()
        / safe_segment(school_id, fallback="school")
        / safe_segment(membership_id, fallback="member")
        / safe_segment(run_id, fallback="_norun")
    )


def assert_inside_workspace(root: Path, target: Path) -> Path:
    root_res = root.resolve()
    resolved = target.resolve()
    try:
        resolved.relative_to(root_res)
    except ValueError as exc:
        raise ToolError("sandbox.path_denied", "路径超出隔离工作区") from exc
    return resolved


def deny_secret_filename(title: str) -> None:
    name = Path((title or "").strip()).name.lower()
    if name in _SECRET_NAMES or name.endswith(_SECRET_SUFFIXES):
        raise ToolError("sandbox.path_denied", "禁止把密钥类文件写入工作区")


def current_run_id(principal: Principal, store: Any | None) -> str | None:
    from pico_orchestrator.usage_hook import current_usage_bind

    bind = current_usage_bind()
    if bind and bind.run_id:
        return str(bind.run_id)
    if store is not None:
        rid = getattr(store, "_run_id", None)
        if rid:
            return str(rid)
    return None


def _preview_mac(
    *,
    artifact_id: str,
    school_id: str,
    membership_id: str,
    run_id: str | None,
    exp: int,
) -> str:
    msg = f"{artifact_id}\n{school_id}\n{membership_id}\n{(run_id or '-').strip() or '-'}\n{exp}"
    return hmac.new(preview_signing_secret(), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def mint_preview_query(
    *,
    artifact_id: str,
    school_id: str,
    membership_id: str,
    run_id: str | None,
    now: float | None = None,
    ttl_s: int = PREVIEW_TTL_S,
) -> tuple[str, int]:
    exp = int((now if now is not None else time.time()) + ttl_s)
    sig = _preview_mac(
        artifact_id=artifact_id,
        school_id=school_id,
        membership_id=membership_id,
        run_id=run_id,
        exp=exp,
    )
    query = urlencode({"preview": "1", "exp": str(exp), "sig": sig})
    return f"/v1/artifacts/{artifact_id}/content?{query}", exp


def verify_preview_sig(
    *,
    artifact_id: str,
    school_id: str,
    membership_id: str,
    run_id: str | None,
    exp: int,
    sig: str,
    now: float | None = None,
) -> str | None:
    """Return an error code or None when the signature is valid and unexpired."""
    if exp <= int(now if now is not None else time.time()):
        return "sandbox.preview_expired"
    expected = _preview_mac(
        artifact_id=artifact_id,
        school_id=school_id,
        membership_id=membership_id,
        run_id=run_id,
        exp=exp,
    )
    given = (sig or "").strip().lower()
    if not given or not secrets.compare_digest(expected, given):
        return "sandbox.preview_denied"
    return None


def try_parse_artifact_preview_url(url: str) -> dict[str, Any] | None:
    """If URL path is Pico artifact content, return ids/query. Never fetches."""
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    path = parsed.path or ""
    match = _ARTIFACT_IN_PATH.search(path)
    if not match:
        # Allow relative paths without a host.
        match = _ARTIFACT_IN_PATH.search(raw.split("?", 1)[0])
    if not match:
        return None
    qs = parse_qs(parsed.query)
    exp_raw = (qs.get("exp") or [""])[0]
    try:
        exp = int(exp_raw) if exp_raw else 0
    except ValueError:
        exp = 0
    return {
        "artifact_id": match.group(1).strip(),
        "exp": exp,
        "sig": (qs.get("sig") or [""])[0].strip(),
        "preview": (qs.get("preview") or [""])[0].strip(),
        "has_sig": bool((qs.get("sig") or [""])[0].strip()),
    }


class _TitleH1Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.h1 = ""
        self._buf: list[str] = []
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title" and not self.title:
            self._capture = "title"
            self._buf = []
        elif tag == "h1" and not self.h1:
            self._capture = "h1"
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture == tag:
            text = "".join(self._buf).strip()
            if tag == "title":
                self.title = text
            elif tag == "h1":
                self.h1 = text
            self._capture = None
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)


def extract_title_h1(html: str) -> tuple[str, str]:
    parser = _TitleH1Parser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        logger.debug("html title/h1 parse truncated", exc_info=True)
    return parser.title, parser.h1


def assert_content_caps(content: str) -> None:
    if len(content) > MAX_CONTENT_CHARS:
        raise ToolError(
            "tool.invalid_arguments",
            f"content exceeds {MAX_CONTENT_CHARS} characters",
        )
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise ToolError(
            "tool.invalid_arguments",
            f"content exceeds {MAX_CONTENT_BYTES} bytes",
        )


async def with_io_timeout(awaitable: Any, *, what: str) -> Any:
    try:
        return await asyncio.wait_for(awaitable, timeout=IO_TIMEOUT_S)
    except TimeoutError as exc:
        raise ToolError("workspace.timeout", f"{what} timed out") from exc


def attach_preview_meta(
    result: dict[str, Any],
    principal: Principal,
    *,
    store: Any | None = None,
) -> dict[str, Any]:
    data = dict(result)
    artifact_id = str(data.get("artifact_id") or data.get("id") or "").strip()
    if not artifact_id:
        return data
    run_id = str(data.get("run_id") or "") or current_run_id(principal, store)
    path, exp = mint_preview_query(
        artifact_id=artifact_id,
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        run_id=run_id,
    )
    data["preview_path"] = f"/v1/artifacts/{artifact_id}/content"
    data["preview_url"] = path
    data["preview_expires_at"] = exp
    data["workspace_id"] = workspace_id_for(
        principal.school_id, principal.membership_id, run_id
    )
    if "open_path" not in data:
        data["open_path"] = data["preview_path"]
    return data


def materialize_workspace_html(
    principal: Principal,
    *,
    run_id: str | None,
    title: str,
    content: str,
) -> str | None:
    """Best-effort copy of THIS run's HTML into the isolation dir. Never raises."""
    try:
        deny_secret_filename(title)
        root = isolation_dir(principal.school_id, principal.membership_id, run_id)
        root.mkdir(parents=True, exist_ok=True)
        name = safe_segment(Path(title).name or "page.html", fallback="page.html")
        if not name.lower().endswith((".html", ".htm")):
            name = f"{name}.html"
        dest = assert_inside_workspace(root, root / name)
        dest.write_text(content[:MAX_CONTENT_CHARS], encoding="utf-8")
        return str(dest)
    except Exception:
        logger.debug("sandbox materialize skipped", exc_info=True)
        return None


def deny_non_preview_url(url: str) -> None:
    """SSRF/intranet deny for URLs that are not this-run artifact previews."""
    parse_public_http_url(url)
    raise ToolError(
        "sandbox.not_this_preview",
        "只允许查看本次隔离预览，不能抓取公网或内网地址",
    )


def html_from_artifact_row(row: dict[str, Any]) -> str:
    body = row.get("content")
    if isinstance(body, str) and body.strip():
        if len(body) > MAX_CONTENT_CHARS:
            return body[:MAX_CONTENT_CHARS]
        return body
    b64 = row.get("content_base64")
    if isinstance(b64, str) and b64.strip():
        import base64

        try:
            decoded = base64.b64decode(b64.encode("ascii"), validate=False).decode(
                "utf-8", errors="replace"
            )
        except Exception as exc:
            raise ToolError("artifact.corrupt", "无法读取预览 HTML") from exc
        return decoded[:MAX_CONTENT_CHARS]
    raise ToolError("sandbox.not_html", "产物不是可读的 HTML 文本")


def assert_same_run(row: dict[str, Any], run_id: str | None) -> None:
    if not run_id:
        return
    row_run = str(row.get("run_id") or "").strip()
    if row_run and row_run != str(run_id).strip():
        raise ToolError("sandbox.not_this_run", "只能查看本次 Run 的预览")


def light_exec_source(source: str) -> dict[str, Any]:
    """Optional S1 exec: parse only, never bash, never import host modules."""
    import ast

    text = (source or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "source 必须是非空字符串")
    if len(text) > MAX_EXEC_SOURCE:
        raise ToolError(
            "tool.invalid_arguments",
            f"source exceeds {MAX_EXEC_SOURCE} characters",
        )
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ToolError("sandbox.exec_invalid", "工作区内源码无法解析") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".", 1)[0] for a in node.names]
            elif node.module:
                names = [node.module.split(".", 1)[0]]
            if any(n in _FORBIDDEN_EXEC_MODS for n in names):
                raise ToolError(
                    "sandbox.exec_denied",
                    "禁止在工作区执行宿主机/网络模块",
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
            "exec",
            "eval",
            "compile",
            "open",
            "__import__",
        }:
            raise ToolError("sandbox.exec_denied", "禁止动态执行或打开宿主文件")
    return {"ok": True, "parsed": True, "executed": False, "timeout_s": EXEC_TIMEOUT_S}


async def light_exec_with_timeout(source: str) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(light_exec_source, source),
            timeout=EXEC_TIMEOUT_S,
        )
    except TimeoutError as exc:
        raise ToolError("sandbox.exec_timeout", "工作区执行超时已杀掉") from exc
