"""Thin PyPI adapters that edit existing OOXML. Not a self-built Office engine.

Implementation lives in pico_orchestrator.office.edit (ADR-OFFICE-DOC-PIPELINE).
This module stays as the import path existing tests already use.
"""

from pico_orchestrator.office.edit import (
    comment_docx_bytes,
    edit_docx_bytes,
    edit_pptx_title_bytes,
    edit_xlsx_cell_bytes,
)
from pico_orchestrator.office.fill import (
    FillReceipt,
    fill_office_bytes,
    fill_office_with_receipt,
)

__all__ = [
    "FillReceipt",
    "comment_docx_bytes",
    "edit_docx_bytes",
    "edit_pptx_title_bytes",
    "edit_xlsx_cell_bytes",
    "fill_office_bytes",
    "fill_office_with_receipt",
]
