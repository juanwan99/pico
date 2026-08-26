"""Office document kernel — thin adapter over python-docx / python-pptx.

True source is ``pico.office.spec/v1``. Files are a projection. See
``docs/ADR-OFFICE-DOC-PIPELINE.md``. Card 1: docx/pptx + table/image.
Excel product surface is card 2.
"""

from pico_orchestrator.office.edit import (
    edit_by_address,
    edit_docx_bytes,
    edit_pptx_title_bytes,
)
from pico_orchestrator.office.inspect import inspect_bytes
from pico_orchestrator.office.qa import verify_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import (
    SPEC_VERSION,
    parse_spec,
    spec_from_plain_body,
)

__all__ = (
    "SPEC_VERSION",
    "edit_by_address",
    "edit_docx_bytes",
    "edit_pptx_title_bytes",
    "inspect_bytes",
    "parse_spec",
    "render_spec",
    "spec_from_plain_body",
    "verify_bytes",
)
