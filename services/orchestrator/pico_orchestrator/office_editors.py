"""Thin PyPI adapters that edit existing OOXML. Not a self-built Office engine.

Implementation lives in pico_orchestrator.office.edit (ADR-OFFICE-DOC-PIPELINE).
This module stays as the import path existing tests already use.
"""

from pico_orchestrator.office.edit import edit_docx_bytes, edit_pptx_title_bytes

__all__ = ["edit_docx_bytes", "edit_pptx_title_bytes"]
