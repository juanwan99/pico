"""Build-time: record RapidOCR ONNX paths. No torch, no HF layout, no TableFormer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAPIDOCR_JSON = "rapidocr-onnx.json"
PREFERRED = {
    "det": "onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx",
    "rec": "onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx",
    "cls": "onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
}


def _pick_onnx(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, rel in PREFERRED.items():
        hit = root / rel
        if hit.is_file():
            out[key] = str(hit)
    if len(out) == 3:
        return out
    det = next(root.rglob("*det*.onnx"), None)
    rec = next(root.rglob("*rec*.onnx"), None)
    cls = next(root.rglob("*cls*.onnx"), None)
    if det and rec and cls:
        return {"det": str(det), "rec": str(rec), "cls": str(cls)}
    raise FileNotFoundError(f"RapidOCR onnx not found under {root}")


def main() -> int:
    dest = Path(os.environ.get("DOCLING_ARTIFACTS_PATH") or "/opt/docling-models")
    dest.mkdir(parents=True, exist_ok=True)
    roots = [dest / "RapidAI-RapidOCR", dest]
    last_err: Exception | None = None
    paths: dict[str, str] | None = None
    for root in roots:
        try:
            paths = _pick_onnx(root)
            break
        except FileNotFoundError as exc:
            last_err = exc
    if paths is None:
        onnx_n = sum(1 for _ in dest.rglob("*.onnx"))
        if onnx_n == 0:
            print(f"prefetch_skip path={dest} reason=no_onnx (host copies models at deploy)", flush=True)
            return 0
        print(f"prefetch_failed: {last_err}", file=sys.stderr)
        return 2
    marker = dest / RAPIDOCR_JSON
    marker.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"prefetch_ok path={dest} rapidocr={paths} layout=skipped tableformer=skipped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
