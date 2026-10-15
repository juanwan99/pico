"""Make Chinese the matplotlib default in this image (pico#1295).

matplotlib builds rcParamsDefault from its shipped mpl-data/matplotlibrc
with the leading "#" stripped, so the commented lines ARE the defaults.
Rewrite those lines in place: an appended block warns "Duplicate key" on
every import, and a MATPLOTLIBRC env var would not reach office jobs
(office_runner passes a fixed env). Fails the build if a key moved.
"""
from pathlib import Path

import matplotlib

DEFAULTS = {
    "font.sans-serif": "Noto Sans CJK SC, Noto Sans CJK JP, WenQuanYi Zen Hei, DejaVu Sans, Liberation Sans, sans-serif",
    "font.serif": "Noto Serif CJK SC, Noto Serif CJK JP, DejaVu Serif, Liberation Serif, serif",
    "axes.unicode_minus": "False",
}

path = Path(matplotlib.matplotlib_fname())
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
hits = {key: 0 for key in DEFAULTS}
for i, line in enumerate(lines):
    for key, value in DEFAULTS.items():
        if line.startswith(f"#{key}:"):
            lines[i] = f"#{key}: {value}  # pico#1295\n"
            hits[key] += 1
missing = [key for key, n in hits.items() if n != 1]
if missing:
    raise SystemExit(f"matplotlibrc keys not found exactly once: {missing}")
path.write_text("".join(lines), encoding="utf-8")
