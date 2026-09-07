"""Isolated office-library ceiling. Not a second Office OS. No host bash.

Default files still go through spec / generate_*.
This module runs a tightly allowlisted snippet in a subprocess and
returns OOXML bytes. Empty shells fail closed.

Thin adapters vs naked GPT office libs: pathlib is a stub (mkdir
ignored), Document/Workbook/Presentation.save always book to OUTPUT_PATH,
source cap is OFFICE_LIB_MAX_SOURCE. os / open / eval stay denied. Stdlib
without host IO (copy/math/datetime/io.BytesIO) is allowed so naked GPT
drafts are not sent back to stock layouts (#829).
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.document_generators import office_shell_reason
from pico_orchestrator.gateway import ToolError

_TIMEOUT_S = 45.0
PPTX_LIB_MAX_SOURCE = 200_000
OFFICE_LIB_MAX_SOURCE = PPTX_LIB_MAX_SOURCE
_MAX_SOURCE = OFFICE_LIB_MAX_SOURCE
_DENIED_CALLS = frozenset({"exec", "eval", "compile", "open", "__import__"})
_OFFICE_KINDS = frozenset({"pptx", "docx", "xlsx"})
# Keep in sync with office/sandbox_exec.py STDLIB_OK.
STDLIB_OK = frozenset(
    {
        "copy",
        "math",
        "datetime",
        "collections",
        "itertools",
        "functools",
        "typing",
        "dataclasses",
        "enum",
        "re",
        "json",
        "uuid",
        "statistics",
        "decimal",
        "numbers",
        "operator",
        "string",
        "textwrap",
        "heapq",
        "bisect",
        "array",
        "contextlib",
        "abc",
        "warnings",
        "time",
        "random",
        "base64",
        "struct",
        "io",
        "calendar",
        "fractions",
    }
)
_IO_FROM_OK = frozenset({"BytesIO", "StringIO"})
# Upstream office PyPI. os / subprocess stay denied. pathlib is a stub (mkdir only).
_ALLOWED_IMPORT_ROOTS = frozenset(
    {"pptx", "pptx_helpers", "docx", "openpyxl", "pathlib"}
) | STDLIB_OK


def _import_root(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        roots = {alias.name.split(".")[0] for alias in node.names if alias.name}
        if len(roots) == 1:
            return next(iter(roots))
        return None
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        mod = node.module or ""
        return mod.split(".")[0] if mod else None
    return None


def _pathlib_import_ok(node: ast.AST) -> bool:
    """Allow `import pathlib` / `from pathlib import Path` only. Not pathlib.abc."""
    if isinstance(node, ast.Import):
        return all(alias.name == "pathlib" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        if node.level or node.module != "pathlib":
            return False
        allowed = {"Path", "PurePath", "PurePosixPath"}
        return bool(node.names) and all(
            alias.name == "*" or alias.name in allowed for alias in node.names
        )
    return False


def _io_import_ok(node: ast.AST) -> bool:
    """Allow `import io` / `from io import BytesIO, StringIO`. Not io.open."""
    if isinstance(node, ast.Import):
        return all(alias.name == "io" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        if node.level or node.module != "io":
            return False
        return bool(node.names) and all(alias.name in _IO_FROM_OK for alias in node.names)
    return False


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
    text = (source or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "source 必须是非空的办公库脚本。")
    if len(text) > _MAX_SOURCE:
        raise ToolError("tool.invalid_arguments", f"source 不能超过 {_MAX_SOURCE} 字。")
    kind = normalize_office_kind(kind)
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ToolError("sandbox.exec_invalid", "办公库脚本无法解析。") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            root = _import_root(node)
            if root == "pathlib" and not _pathlib_import_ok(node):
                raise ToolError(
                    "sandbox.exec_denied",
                    "pathlib 只允许 import pathlib 或 from pathlib import Path；禁止 pathlib.abc / 宿主文件。",
                )
            if root == "io" and not _io_import_ok(node):
                raise ToolError(
                    "sandbox.exec_denied",
                    "io 只允许 BytesIO/StringIO，禁止 io.open / 宿主文件。",
                )
            if root not in _ALLOWED_IMPORT_ROOTS:
                raise ToolError(
                    "sandbox.exec_denied",
                    "禁止 import os/宿主库。办公库可用 python-docx / openpyxl / python-pptx。"
                    "copy/math/datetime/io.BytesIO 可用。",
                )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DENIED_CALLS
        ):
            raise ToolError("sandbox.exec_denied", "禁止动态执行或打开宿主文件。")
        if isinstance(node, ast.Attribute) and str(node.attr).startswith("__"):
            raise ToolError("sandbox.exec_denied", "禁止访问内部属性。")
        if isinstance(node, ast.Name) and str(node.id).startswith("__") and node.id != "__name__":
            raise ToolError("sandbox.exec_denied", "禁止访问内部名字。")


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
    return b"<v>" in blob or b"<t>" in blob or b"t=\"inlineStr\"" in blob or b"t='inlineStr'" in blob


def _validate_office_bytes(raw: bytes, kind: str) -> bytes:
    kind = normalize_office_kind(kind)
    ext = f".{kind}"
    if not raw:
        if kind == "pptx":
            raise ToolError("sandbox.pptx_empty", "沙箱没有写出 PPT。请调用 save_deck(prs) 或 prs.save。")
        if kind == "docx":
            raise ToolError("sandbox.docx_empty", "沙箱没有写出 Word。请调用 save_doc(doc) 或 doc.save。")
        raise ToolError("sandbox.xlsx_empty", "沙箱没有写出 Excel。请调用 save_book(wb) 或 wb.save。")
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


def run_office_lib_source(
    source: str,
    *,
    kind: str = "pptx",
    images: dict[str, bytes] | None = None,
    input_bytes: bytes | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    """Sync runner used by the subprocess and tests."""
    kind = normalize_office_kind(kind)
    assert_office_lib_source(source, kind=kind)
    if input_bytes is not None:
        if not isinstance(input_bytes, (bytes, bytearray)) or not input_bytes:
            raise ToolError(
                "sandbox.input_invalid",
                "原件是空的或不是字节，不能载入隔离办公库。",
            )
        raw_in = bytes(input_bytes)
        if not _looks_like_office_zip(raw_in, kind) or not is_valid_ooxml_package(
            raw_in, f".{kind}"
        ):
            raise ToolError(
                "sandbox.input_invalid",
                f"原件不是真 {kind.upper()}（OOXML），不能当改稿载入。",
            )
    with tempfile.TemporaryDirectory(prefix="pico-office-lib-") as tmp:
        root = Path(tmp)
        out_path = root / f"out.{kind}"
        input_path = ""
        if input_bytes is not None:
            in_file = root / f"in.{kind}"
            in_file.write_bytes(bytes(input_bytes))
            input_path = str(in_file)
        image_paths: dict[str, str] = {}
        for key, blob in (images or {}).items():
            if not blob:
                continue
            name = f"{key}.png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else f"{key}.jpg"
            dest = root / name
            dest.write_bytes(blob)
            image_paths[str(key)] = str(dest)
        helpers_src = Path(__file__).with_name("pptx_helpers.py").read_text(encoding="utf-8")
        (root / "pptx_helpers.py").write_text(helpers_src, encoding="utf-8")
        exec_src = Path(__file__).with_name("sandbox_exec.py").read_text(encoding="utf-8")
        wrapper = root / "runner.py"
        wrapper.write_text(exec_src, encoding="utf-8")
        cfg_path = root / "cfg.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "output": str(out_path),
                    "input": input_path,
                    "images": image_paths,
                    "source": source,
                    "kind": kind,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(wrapper), str(cfg_path)],
                cwd=str(root),
                capture_output=True,
                timeout=max(1.0, float(timeout_s)),
                env=_isolated_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError("sandbox.exec_timeout", "沙箱办公库超时已杀掉。") from exc
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[:800]
            raise ToolError(
                f"sandbox.{kind}_failed",
                f"隔离办公库失败：{err or 'exit ' + str(proc.returncode)}",
            )
        return _validate_office_bytes(
            out_path.read_bytes() if out_path.is_file() else b"", kind
        )


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
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    return await asyncio.to_thread(
        run_office_lib_source,
        source,
        kind=kind,
        images=images,
        input_bytes=input_bytes,
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


def _isolated_env() -> dict[str, str]:
    keep = ("PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "VIRTUAL_ENV")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def main() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8")
    body: dict[str, Any] = json.loads(raw or "{}")
    out = run_office_lib_source(
        str(body.get("source") or ""),
        kind=str(body.get("kind") or "pptx"),
        images={
            str(k): bytes(v) if isinstance(v, list) else v
            for k, v in (body.get("images") or {}).items()
        },
    )
    sys.stdout.buffer.write(out)


if __name__ == "__main__":
    main()
