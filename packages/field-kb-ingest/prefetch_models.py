"""Build-time: bake Docling layout + RapidOCR artifacts. No runtime Hub calls."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    dest = Path(os.environ.get("DOCLING_ARTIFACTS_PATH") or "/opt/docling-models")
    dest.mkdir(parents=True, exist_ok=True)
    from docling.utils.model_downloader import download_models

    download_models(
        output_dir=dest,
        force=False,
        progress=True,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=True,
        with_easyocr=False,
    )
    n = sum(1 for _ in dest.rglob("*"))
    print(f"prefetch_ok path={dest} entries={n}", flush=True)
    if n < 3:
        print("prefetch_failed: artifacts dir almost empty", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
