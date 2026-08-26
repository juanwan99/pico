"""Isolated python-pptx ceiling. Not a second Office OS. No host bash.

Default decks still go through spec / generate_pptx_document.
This module runs a tightly allowlisted snippet in a subprocess and
returns OOXML bytes. Empty shells fail closed.
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

_TIMEOUT_S = 20.0
_MAX_SOURCE = 20_000
_DENIED_CALLS = frozenset({"exec", "eval", "compile", "open", "__import__"})


def assert_pptx_lib_source(source: str) -> None:
    text = (source or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "source 必须是非空的 python-pptx 脚本。")
    if len(text) > _MAX_SOURCE:
        raise ToolError("tool.invalid_arguments", f"source 不能超过 {_MAX_SOURCE} 字。")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ToolError("sandbox.exec_invalid", "python-pptx 脚本无法解析。") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ToolError(
                "sandbox.exec_denied",
                "不要自己 import。沙箱已注入 Presentation / Inches / save_deck。",
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DENIED_CALLS
        ):
            raise ToolError("sandbox.exec_denied", "禁止动态执行或打开宿主文件。")
        if isinstance(node, ast.Attribute) and str(node.attr).startswith("__"):
            raise ToolError("sandbox.exec_denied", "禁止访问内部属性。")
        if isinstance(node, ast.Name) and str(node.id).startswith("__"):
            raise ToolError("sandbox.exec_denied", "禁止访问内部名字。")


def _looks_like_pptx_zip(raw: bytes) -> bool:
    if not raw or raw[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "ppt/presentation.xml" in names


def _validate_pptx_bytes(raw: bytes) -> bytes:
    if not raw:
        raise ToolError("sandbox.pptx_empty", "沙箱没有写出 PPT。请调用 save_deck(prs)。")
    if _looks_like_pptx_zip(raw):
        reason = office_shell_reason(raw, ".pptx")
        if reason:
            raise ToolError("sandbox.pptx_shell", reason)
        if is_valid_ooxml_package(raw, ".pptx"):
            return raw
    raise ToolError("sandbox.pptx_invalid", "沙箱写出的不是真 PPT（OOXML）。")


def run_pptx_lib_source(
    source: str,
    *,
    images: dict[str, bytes] | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    """Sync runner used by the subprocess and tests."""
    assert_pptx_lib_source(source)
    with tempfile.TemporaryDirectory(prefix="pico-pptx-lib-") as tmp:
        root = Path(tmp)
        out_path = root / "deck.pptx"
        image_paths: dict[str, str] = {}
        for key, blob in (images or {}).items():
            if not blob:
                continue
            name = f"{key}.png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else f"{key}.jpg"
            dest = root / name
            dest.write_bytes(blob)
            image_paths[str(key)] = str(dest)
        wrapper = root / "runner.py"
        wrapper.write_text(
            _wrapper_source(source, str(out_path), image_paths),
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(wrapper)],
                cwd=str(root),
                capture_output=True,
                timeout=max(1.0, float(timeout_s)),
                env=_isolated_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError("sandbox.exec_timeout", "沙箱 python-pptx 超时已杀掉。") from exc
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[:240]
            raise ToolError(
                "sandbox.pptx_failed",
                f"隔离 python-pptx 失败：{err or 'exit ' + str(proc.returncode)}",
            )
        return _validate_pptx_bytes(out_path.read_bytes() if out_path.is_file() else b"")


async def run_pptx_lib_source_async(
    source: str,
    *,
    images: dict[str, bytes] | None = None,
    timeout_s: float = _TIMEOUT_S,
) -> bytes:
    return await asyncio.to_thread(
        run_pptx_lib_source, source, images=images, timeout_s=timeout_s
    )


def _isolated_env() -> dict[str, str]:
    keep = ("PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "VIRTUAL_ENV")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _wrapper_source(user_source: str, output_path: str, image_paths: dict[str, str]) -> str:
    payload = json.dumps(
        {"output": output_path, "images": image_paths, "source": user_source},
        ensure_ascii=False,
    )
    return (
        "import json\n"
        "from pptx import Presentation\n"
        "from pptx.util import Emu, Inches, Pt\n"
        f"cfg = json.loads({payload!r})\n"
        "OUTPUT_PATH = cfg['output']\n"
        "IMAGE_PATHS = cfg['images']\n"
        "def save_deck(prs):\n"
        "    if not hasattr(prs, 'save'):\n"
        "        raise SystemExit('save_deck 需要 Presentation')\n"
        "    prs.save(OUTPUT_PATH)\n"
        "exec(cfg['source'], {\n"
        "    '__builtins__': {'range': range, 'len': len, 'str': str, 'int': int, 'list': list, 'dict': dict},\n"
        "    'Presentation': Presentation,\n"
        "    'Inches': Inches,\n"
        "    'Emu': Emu,\n"
        "    'Pt': Pt,\n"
        "    'save_deck': save_deck,\n"
        "    'IMAGE_PATHS': IMAGE_PATHS,\n"
        "    'OUTPUT_PATH': OUTPUT_PATH,\n"
        "    '__name__': '__sandbox_pptx__',\n"
        "})\n"
    )


def main() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8")
    body: dict[str, Any] = json.loads(raw or "{}")
    out = run_pptx_lib_source(
        str(body.get("source") or ""),
        images={
            str(k): bytes(v) if isinstance(v, list) else v
            for k, v in (body.get("images") or {}).items()
        },
    )
    sys.stdout.buffer.write(out)


if __name__ == "__main__":
    main()
