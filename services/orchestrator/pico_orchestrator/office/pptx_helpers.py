"""Thin python-pptx helpers for the isolated sandbox.

Not a second Office OS. These are the same verbs a document-skill
script already writes by hand: title slide, bullets, table.
Upstream: python-pptx. No new spec fields.
"""

from __future__ import annotations

from typing import Any


def add_title_slide(prs: Any, title: str, subtitle: str = "") -> Any:
    """Title layout (owner/date belong in subtitle)."""
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None and getattr(title_shape, "has_text_frame", False):
        title_shape.text = str(title or "")
    if subtitle:
        _set_placeholder_text(slide, 1, str(subtitle))
    return slide


def add_content_slide(prs: Any, title: str, bullets: Any = ()) -> Any:
    """Title-and-content layout. ``bullets`` is a list of strings."""
    layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
    slide = prs.slides.add_slide(layout)
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None and getattr(title_shape, "has_text_frame", False):
        title_shape.text = str(title or "")
    items = [str(item).strip() for item in (bullets or ()) if str(item).strip()]
    if items:
        _set_placeholder_text(slide, 1, "\n".join(items))
    return slide


def add_table(
    slide: Any,
    rows: Any,
    left: Any = None,
    top: Any = None,
    width: Any = None,
    height: Any = None,
) -> Any:
    """Add a table from a list of row lists. Sizes default to the content well."""
    from pptx.util import Inches, Pt

    grid = _table_grid(rows)
    n_rows = len(grid)
    n_cols = len(grid[0])
    shape = slide.shapes.add_table(
        n_rows,
        n_cols,
        left if left is not None else Inches(0.5),
        top if top is not None else Inches(1.7),
        width if width is not None else Inches(9.0),
        height if height is not None else Inches(min(5.2, 0.42 * n_rows + 0.5)),
    )
    table = shape.table
    for r_i, row in enumerate(grid):
        for c_i, cell in enumerate(row):
            table.cell(r_i, c_i).text = cell
            if r_i == 0:
                for para in table.cell(r_i, c_i).text_frame.paragraphs:
                    for run in para.runs:
                        run.font.bold = True
                        run.font.size = Pt(14)
    return shape


def pipe_table_rows(bullets: Any) -> tuple[tuple[str, ...], ...] | None:
    """If every bullet is ``a|b`` (or more), return a table grid. Else None."""
    items = [str(item).strip() for item in (bullets or ()) if str(item).strip()]
    if len(items) < 2:
        return None
    rows: list[tuple[str, ...]] = []
    for item in items:
        if "|" not in item:
            return None
        cells = [part.strip() for part in item.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) < 2:
            return None
        rows.append(tuple(cells))
    width = max(len(row) for row in rows)
    if width < 2:
        return None
    return tuple(row + ("",) * (width - len(row)) for row in rows)


def _table_grid(rows: Any) -> list[list[str]]:
    if not rows:
        raise ValueError("add_table 需要至少一行。")
    grid: list[list[str]] = []
    width = 0
    for row in rows:
        if isinstance(row, (str, bytes)):
            raise TypeError("add_table 每一行必须是单元格列表。")
        cells = ["" if cell is None else str(cell) for cell in row]
        if not cells:
            raise ValueError("add_table 每一行必须是非空列表。")
        width = max(width, len(cells))
        grid.append(cells)
    if width < 1:
        raise ValueError("add_table 需要至少一列。")
    return [row + [""] * (width - len(row)) for row in grid]


def _set_placeholder_text(slide: Any, idx: int, text: str) -> None:
    placeholders = getattr(slide, "placeholders", None)
    if placeholders is None:
        return
    for shape in placeholders:
        fmt = getattr(shape, "placeholder_format", None)
        if getattr(fmt, "idx", None) == idx and getattr(shape, "has_text_frame", False):
            shape.text = text
            return
