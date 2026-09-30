"""Seat students row by row."""


def make_seating(names, cols):
    """Rows of at most ``cols`` names, in order; the last row may be short."""
    if cols < 1:
        raise ValueError("cols must be >= 1")
    rows = []
    for start in range(0, len(names) - cols + 1, cols):
        rows.append(names[start : start + cols])
    return rows
