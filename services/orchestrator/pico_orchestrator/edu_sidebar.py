"""edu-core sidebar propose — explicit marker only. Not NL heuristics."""

from __future__ import annotations

JSON_ONLY_OUTPUT = "json_only_no_files"
_JSON_KEY_COMPACT = '"output":"json_only_no_files"'
_JSON_KEY_SPACED = '"output": "json_only_no_files"'


def is_json_only_propose(
    prompt: str | None,
    *,
    output_header: str | None = None,
) -> bool:
    """True only for the edu sidebar contract. Workbench chat stays false."""
    header = output_header if isinstance(output_header, str) else ""
    header = header.strip()
    if header == JSON_ONLY_OUTPUT:
        return True
    text = prompt or ""
    return _JSON_KEY_COMPACT in text or _JSON_KEY_SPACED in text
