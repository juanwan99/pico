"""Compatibility re-export. Path B edits live in ``office.edit``.

Upstream: python-docx / python-pptx. Do not add a second editor here.
"""

from pico_orchestrator.office.edit import edit_by_address, edit_docx_bytes, edit_pptx_title_bytes

__all__ = ("edit_by_address", "edit_docx_bytes", "edit_pptx_title_bytes")
