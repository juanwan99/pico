"""Office write path: thin client to the pico-office container.

The script runs in ``pico-office`` (same image as pico-sandbox, ``network_mode:
none``, tmpfs, rlimit) with a full Python 3 + python-docx / openpyxl /
python-pptx. Pico keeps no import allowlist and no AST jail here (#959,
TRUTH-FREEZE v2.0). What stays on this side is the latch: OOXML validity,
empty-shell refusal, source size, and the ledger write in tools_builtin.

``PICO_OFFICE_URL``:
  unix:///run/pico-office/office.sock   (default · production)
  http://127.0.0.1:18769                (dev · tcp)
  embedded                              (tests · run_office_job in-process)
"""

from __future__ import annotations

import ast
import asyncio
import base64
import contextlib
import io
import os
import zipfile
from typing import Any

import httpx

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.document_generators import office_shell_reason
from pico_orchestrator.gateway import ToolError

_TIMEOUT_S = 60.0
PPTX_LIB_MAX_SOURCE = 200_000
OFFICE_LIB_MAX_SOURCE = PPTX_LIB_MAX_SOURCE
_MAX_SOURCE = OFFICE_LIB_MAX_SOURCE
_OFFICE_KINDS = frozenset({"pptx", "docx", "xlsx"})
_DEFAULT_OFFICE_URL = "unix:///run/pico-office/office.sock"
_RUN_PATH = "/v1/internal/office/run"


def office_url() -> str:
    raw = (os.environ.get("PICO_OFFICE_URL") or "").strip()
    return raw or _DEFAULT_OFFICE_URL


def _office_token() -> dict[str, str]:
    token = (os.environ.get("PICO_SANDBOX_TOKEN") or "").strip()
    return {"X-Pico-Sandbox-Token": token} if token else {}


def normalize_office_kind(kind: str | None, *, title: str | None = None) -> str:
    token = str(kind or "").strip().lower().lstrip(".")
    if token in _OFFICE_KINDS:
        return token
    name = str(title or "").strip().lower()
    if name.endswith(".docx"):
        return "docx"
    if name.endswith(".xlsx"):
        return "xlsx"
    if name.endswith(".pptx"):
        return "pptx"
    raise ToolError(
        "tool.invalid_arguments",
        "kind 必须是 docx、xlsx 或 pptx（也可从 title 后缀推断）。",
    )


def assert_office_lib_source(source: str, *, kind: str = "pptx") -> None:
    """Cheap door: non-empty, size cap, parses. Not an allowlist."""
    text = (source or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "source 必须是非空的办公库脚本。")
    if len(text) > _MAX_SOURCE:
        raise ToolError("tool.invalid_arguments", f"source 不能超过 {_MAX_SOURCE} 字。")
    normalize_office_kind(kind)
    try:
        ast.parse(text)
    except SyntaxError as exc:
        raise ToolError(
            "sandbox.exec_invalid",
            f"办公脚本无法解析：第 {exc.lineno} 行 {exc.msg}。",
        ) from exc


def assert_pptx_lib_source(source: str) -> None:
    assert_office_lib_source(source, kind="pptx")


def _looks_like_office_zip(raw: bytes, kind: str) -> bool:
    if not raw or raw[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False
    if "[Content_Types].xml" not in names:
        return False
    if kind == "pptx":
        return "ppt/presentation.xml" in names
    if kind == "docx":
        return "word/document.xml" in names
    if kind == "xlsx":
        return "xl/workbook.xml" in names
    return False


def _xlsx_has_cell(raw: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            sheets = [n for n in zf.namelist() if n.startswith("xl/worksheets/")]
            blob = b"".join(zf.read(n) for n in sheets)
    except zipfile.BadZipFile:
        return False
    return b"<v>" in blob or b"<t>" in blob or b't="inlineStr"' in blob or b"t='inlineStr'" in blob


def _validate_office_bytes(raw: bytes, kind: str) -> bytes:
    kind = normalize_office_kind(kind)
    ext = f".{kind}"
    if not raw:
        if kind == "pptx":
            raise ToolError(
                "sandbox.pptx_empty", "沙箱没有写出 PPT。请调用 save_deck(prs) 或 prs.save。"
            )
        if kind == "docx":
            raise ToolError(
                "sandbox.docx_empty", "沙箱没有写出 Word。请调用 save_doc(doc) 或 doc.save。"
            )
        raise ToolError(
            "sandbox.xlsx_empty", "沙箱没有写出 Excel。请调用 save_book(wb) 或 wb.save。"
        )
    if _looks_like_office_zip(raw, kind):
        reason = office_shell_reason(raw, ext)
        if reason:
            raise ToolError(f"sandbox.{kind}_shell", reason)
        if kind == "xlsx" and not _xlsx_has_cell(raw):
            raise ToolError("sandbox.xlsx_shell", "Excel 打开后几乎是空壳。请写入单元格后再交。")
        if is_valid_ooxml_package(raw, ext):
            return raw
    raise ToolError(f"sandbox.{kind}_invalid", f"沙箱写出的不是真 {kind.upper()}（OOXML）。")


def _validate_pptx_bytes(raw: bytes) -> bytes:
    return _validate_office_bytes(raw, "pptx")


def _check_input(input_bytes: bytes | None, *, kind: str, input_name: str | None) -> None:
    """Any ledger original may go in. Only a same-kind office name must be real OOXML."""
    if input_bytes is None:
        return
    if not isinstance(input_bytes, (bytes, bytearray)) or not input_bytes:
        raise ToolError("sandbox.input_invalid", "原件是空的或不是字节，不能载入隔离办公库。")
    name = str(input_name or "").strip().lower()
    if (not name or name.endswith(f".{kind}")) and not (
        _looks_like_office_zip(bytes(input_bytes), kind)
        and is_valid_ooxml_package(bytes(input_bytes), f".{kind}")
    ):
        raise ToolError(
            "sandbox.input_invalid",
            f"原件不是真 {kind.upper()}（OOXML），不能当改稿载入。",
        )


def _call_office_box(payload: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    base = office_url()
    if base == "embedded":
        from sandbox_worker.office_runner import run_office_job

        return run_office_job(
            kind=payload["kind"],
            source=payload["source"],
            input_bytes=base64.b64decode(payload["input_b64"])
            if payload.get("input_b64")
            else None,
            input_name=payload.get("input_name"),
            images={k: base64.b64decode(v) for k, v in (payload.get("images") or {}).items()},
            timeout_s=timeout_s,
        )
    http_timeout = httpx.Timeout(timeout_s + 15.0, connect=5.0)
    try:
        if base.startswith("unix://"):
            transport = httpx.HTTPTransport(uds=base[len("unix://") :])
            with httpx.Client(transport=transport, timeout=http_timeout, trust_env=False) as client:
                resp = client.post(
                    "http://pico-office" + _RUN_PATH, json=payload, headers=_office_token()
                )
        else:
            with httpx.Client(timeout=http_timeout, trust_env=False) as client:
                resp = client.post(
                    base.rstrip("/") + _RUN_PATH, json=payload, headers=_office_token()
                )
    except httpx.HTTPError as exc:
        raise ToolError(
            "sandbox.unavailable",
            "隔离办公容器（pico-office）未运行。办公脚本不会在 pico-api 进程里跑。",
        ) from exc
    if resp.status_code >= 400:
        code, message = "sandbox.unavailable", f"隔离办公容器返回 HTTP {resp.status_code}"
        with contextlib.suppress(Exception):  # error body is optional JSON
            detail = resp.json().get("detail")
            if isinstance(detail, dict):
                code = str(detail.get("code") or code)
                message = str(detail.get("message") or message)
        raise ToolError(code, message)
    try:
        body = resp.json()
    except Exception as exc:
        raise ToolError("sandbox.unavailable", "隔离办公容器返回了无法解析的响应") from exc
    if not isinstance(body, dict):
        raise ToolError("sandbox.unavailable", "隔离办公容器返回了无法解析的响应")
    return body


def run_office_lib_source(
    source: str,
    *,
    kind: str = "pptx",
    images: dict[str, bytes] | None = None,
    input_bytes: bytes | None = None,
    input_name: str | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    """Sync path (tests and to_thread). Bytes come back validated or a ToolError is raised."""
    kind = normalize_office_kind(kind)
    assert_office_lib_source(source, kind=kind)
    _check_input(input_bytes, kind=kind, input_name=input_name)
    payload: dict[str, Any] = {
        "kind": kind,
        "source": source,
        "input_name": input_name or (f"in.{kind}" if input_bytes else None),
        "input_b64": base64.b64encode(bytes(input_bytes)).decode("ascii") if input_bytes else None,
        "images": {
            str(k): base64.b64encode(v).decode("ascii") for k, v in (images or {}).items() if v
        },
        "timeout_s": float(timeout_s),
    }
    receipt = _call_office_box(payload, timeout_s=float(timeout_s))
    if not receipt.get("ok"):
        code = str(receipt.get("code") or f"sandbox.{kind}_failed")
        message = str(receipt.get("message") or "隔离办公库失败。")
        stderr = str(receipt.get("stderr_tail") or "").strip()
        if stderr:
            message = f"{message}\n{stderr[-1200:]}"
        raise ToolError(code, message)
    raw = base64.b64decode(str(receipt.get("output_b64") or ""))
    return _validate_office_bytes(raw, kind)


def run_pptx_lib_source(
    source: str,
    *,
    images: dict[str, bytes] | None = None,
    input_bytes: bytes | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    return run_office_lib_source(
        source, kind="pptx", images=images, input_bytes=input_bytes, timeout_s=timeout_s
    )


async def run_office_lib_source_async(
    source: str,
    *,
    kind: str = "pptx",
    images: dict[str, bytes] | None = None,
    input_bytes: bytes | None = None,
    input_name: str | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    return await asyncio.to_thread(
        run_office_lib_source,
        source,
        kind=kind,
        images=images,
        input_bytes=input_bytes,
        input_name=input_name,
        timeout_s=timeout_s,
    )


async def run_pptx_lib_source_async(
    source: str,
    *,
    images: dict[str, bytes] | None = None,
    input_bytes: bytes | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    return await run_office_lib_source_async(
        source,
        kind="pptx",
        images=images,
        input_bytes=input_bytes,
        timeout_s=timeout_s,
    )
