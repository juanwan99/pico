"""Thin Office adapter: spec → inspect / render / edit / qa.

Upstream: python-docx · python-pptx · openpyxl. Not a self-built Office engine.
See docs/ADR-OFFICE-DOC-PIPELINE.md.
"""

from pico_orchestrator.office.edit import (
    comment_docx_bytes,
    edit_docx_bytes,
    edit_pptx_title_bytes,
    edit_xlsx_cell_bytes,
)
from pico_orchestrator.office.fill import fill_office_bytes
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.qa import verify_office_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import OfficeSpec, parse_spec, spec_from_plain

__all__ = [
    "OfficeSpec",
    "comment_docx_bytes",
    "edit_docx_bytes",
    "edit_pptx_title_bytes",
    "edit_xlsx_cell_bytes",
    "fill_office_bytes",
    "inspect_office_bytes",
    "parse_spec",
    "render_spec",
    "spec_from_plain",
    "verify_office_bytes",
]
