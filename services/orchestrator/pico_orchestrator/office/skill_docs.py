"""Office document-skill bodies. Catalog in SYSTEM; full text on demand.

Not a second LibreChat store. Not Pi market packages. Not host bash.
"""

from __future__ import annotations

from pathlib import Path

from pico_orchestrator.gateway import ToolError

_ROOT = Path(__file__).resolve().parent / "skills"

OFFICE_SKILL_IDS: tuple[str, ...] = ("docx", "xlsx", "pptx")

OFFICE_SKILL_WHEN: dict[str, str] = {
    "docx": "Teacher asked for a real Word file (.docx) or to change one.",
    "xlsx": "Teacher asked for a real Excel file (.xlsx) or to change one.",
    "pptx": "Teacher asked for a real PowerPoint file (.pptx) or to change one.",
}

_ALIASES: dict[str, str] = {
    "docx": "docx",
    "word": "docx",
    "doc": "docx",
    ".docx": "docx",
    "xlsx": "xlsx",
    "excel": "xlsx",
    "xls": "xlsx",
    "sheet": "xlsx",
    ".xlsx": "xlsx",
    "pptx": "pptx",
    "ppt": "pptx",
    "powerpoint": "pptx",
    "slides": "pptx",
    "deck": "pptx",
    ".pptx": "pptx",
}


def normalize_office_skill_id(raw: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    token = raw.strip().lower()
    if not token:
        return None
    if token.startswith("office-"):
        token = token[len("office-") :]
    if token.startswith("skill-"):
        token = token[len("skill-") :]
    return _ALIASES.get(token)


def office_skill_catalog_block() -> str:
    lines = [
        "- `docx`: " + OFFICE_SKILL_WHEN["docx"],
        "- `xlsx`: " + OFFICE_SKILL_WHEN["xlsx"],
        "- `pptx`: " + OFFICE_SKILL_WHEN["pptx"],
    ]
    return "\n".join(lines)


def load_office_skill_body(skill_id: str) -> str:
    sid = normalize_office_skill_id(skill_id)
    if sid is None:
        raise ToolError(
            "office_skill.unknown",
            "office skill id must be docx, xlsx, or pptx",
        )
    path = _ROOT / f"{sid}.md"
    if not path.is_file():
        raise ToolError("office_skill.missing", f"office skill {sid} is not on disk")
    body = path.read_text(encoding="utf-8")
    if not body.strip():
        raise ToolError("office_skill.empty", f"office skill {sid} is empty")
    return body
