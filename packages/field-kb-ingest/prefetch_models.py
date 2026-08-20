"""Build-time: bake Docling layout + RapidOCR ONNX. No runtime Hub/ModelScope."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAPIDOCR_JSON = "rapidocr-onnx.json"
PREFERRED = {
    "det": "onnx/PP-OCRv5/det/ch_PP-OCRv5_server_det.onnx",
    "rec": "onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_server_infer.onnx",
    "cls": "onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_infer.onnx",
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
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    dest = Path(os.environ.get("DOCLING_ARTIFACTS_PATH") or "/opt/docling-models")
    dest.mkdir(parents=True, exist_ok=True)
    from docling.utils.model_downloader import download_models
    from huggingface_hub import snapshot_download

    download_models(
        output_dir=dest,
        force=False,
        progress=True,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=False,
        with_easyocr=False,
    )
    ocr_dir = dest / "RapidAI-RapidOCR"
    snapshot_download(
        repo_id="RapidAI/RapidOCR",
        local_dir=str(ocr_dir),
        allow_patterns=["onnx/PP-OCRv5/**", "onnx/PP-OCRv4/cls/**"],
    )
    paths = _pick_onnx(ocr_dir)
    marker = dest / RAPIDOCR_JSON
    marker.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
    n = sum(1 for _ in dest.rglob("*"))
    print(f"prefetch_ok path={dest} entries={n} rapidocr={paths}", flush=True)
    if n < 3:
        print("prefetch_failed: artifacts dir almost empty", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
