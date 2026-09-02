"""Pass ledger originals to GPT Responses input_file. Not a Pico reader."""

from __future__ import annotations

import base64
import copy
import os
from dataclasses import dataclass

NATIVE_EXTS = (".pdf", ".docx", ".xlsx", ".pptx")
LEGACY_EXTS = (".doc", ".ppt", ".xls")
MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
MAX_FILES = 4
MAX_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class NativeFile:
    filename: str
    data: bytes

    @property
    def ext(self) -> str:
        name = self.filename.lower()
        for ext in NATIVE_EXTS:
            if name.endswith(ext):
                return ext
        return ""

    @property
    def mime(self) -> str:
        return MIME.get(self.ext, "application/octet-stream")


_TURN: dict[str, list[NativeFile]] = {}


def native_ext(filename: str) -> str | None:
    name = (filename or "").strip().lower()
    for ext in NATIVE_EXTS:
        if name.endswith(ext):
            return ext
    return None


def is_legacy_office(filename: str) -> bool:
    name = (filename or "").strip().lower()
    return any(name.endswith(ext) for ext in LEGACY_EXTS)


def accept_native(filename: str, data: bytes) -> NativeFile | None:
    if is_legacy_office(filename):
        return None
    if native_ext(filename) is None:
        return None
    if not isinstance(data, (bytes, bytearray)) or not data:
        return None
    raw = bytes(data)
    if len(raw) > MAX_BYTES:
        return None
    title = (filename or "file").strip() or "file"
    return NativeFile(filename=title[:180], data=raw)


def remember_turn_files(run_id: str, files: list[NativeFile]) -> None:
    rid = str(run_id or "").strip()
    if not rid:
        return
    kept = [item for item in files if isinstance(item, NativeFile)][:MAX_FILES]
    if kept:
        _TURN[rid] = kept
    else:
        _TURN.pop(rid, None)


def turn_files(run_id: str) -> list[NativeFile]:
    return list(_TURN.get(str(run_id or "").strip()) or [])


def has_turn_files(run_id: str) -> bool:
    return bool(turn_files(run_id))


def forget_turn_files(run_id: str) -> None:
    _TURN.pop(str(run_id or "").strip(), None)


def pass_base_url(run_id: str, *, port: str | None = None) -> str:
    listen = (port or os.environ.get("PICO_API_PORT") or "18765").strip() or "18765"
    rid = str(run_id or "").strip()
    return f"http://127.0.0.1:{listen}/internal/llm-pass/{rid}/v1"


def _as_content_list(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    if isinstance(content, list):
        out: list[dict[str, object]] = []
        for part in content:
            if isinstance(part, dict):
                out.append(dict(part))
            elif isinstance(part, str):
                out.append({"type": "input_text", "text": part})
        return out
    return [{"type": "input_text", "text": str(content or "")}]


def _file_part(item: NativeFile) -> dict[str, str]:
    b64 = base64.b64encode(item.data).decode("ascii")
    return {
        "type": "input_file",
        "filename": item.filename,
        "file_data": f"data:{item.mime};base64,{b64}",
    }


def splice_responses_body(body: dict[str, object], files: list[NativeFile]) -> dict[str, object]:
    """Append original files onto the last user turn. No extract."""
    if not files or not isinstance(body, dict):
        return body
    payload = copy.deepcopy(body)
    raw_input = payload.get("input")
    if isinstance(raw_input, str):
        payload["input"] = [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": raw_input}]
                + [_file_part(item) for item in files],
            }
        ]
        return payload
    if not isinstance(raw_input, list) or not raw_input:
        return payload
    target_i = None
    for i in range(len(raw_input) - 1, -1, -1):
        item = raw_input[i]
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        kind = str(item.get("type") or "")
        if role == "user" or kind == "message" and role != "assistant":
            target_i = i
            break
    if target_i is None:
        payload["input"] = list(raw_input) + [
            {
                "role": "user",
                "content": [_file_part(item) for item in files],
            }
        ]
        return payload
    message = dict(raw_input[target_i])
    content = _as_content_list(message.get("content"))
    existing = {
        str(part.get("filename") or "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "input_file"
    }
    for item in files:
        if item.filename in existing:
            continue
        content.append(_file_part(item))
    message["content"] = content
    if not message.get("role"):
        message["role"] = "user"
    if not message.get("type"):
        message["type"] = "message"
    new_input = list(raw_input)
    new_input[target_i] = message
    payload["input"] = new_input
    return payload
