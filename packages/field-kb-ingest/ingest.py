"""field-kb-ingest · Docling engine. Pointers stay in edu."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ENGINE = "docling"
MAX_EXCERPT = 800
MAX_SLICES = 8
DEFAULT_ARTIFACTS = "/opt/docling-models"

_CONVERTER = None


def artifacts_path() -> Path:
    raw = (os.environ.get("DOCLING_ARTIFACTS_PATH") or DEFAULT_ARTIFACTS).strip()
    return Path(raw)


def rapidocr_onnx_paths() -> dict[str, str]:
    marker = artifacts_path() / "rapidocr-onnx.json"
    if not marker.is_file():
        return {}
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if k in {"det", "rec", "cls"} and v}


def pdf_ocr_settings() -> dict:
    """Flags for the PDF pipeline. Unit-tested without importing Docling."""
    return {
        "do_ocr": True,
        "force_full_page_ocr": True,
        "engine": "rapidocr",
        "artifacts_path": str(artifacts_path()),
    }


def classify_convert_error(exc: BaseException) -> str:
    msg = f"{type(exc).__name__} {exc}".lower()
    ocr_hit = any(
        s in msg for s in ("no ocr engine", "ocr engine found", "libxcb", "cannot open shared object")
    )
    hf_hit = any(
        s in msg
        for s in (
            "huggingface",
            "hf_hub",
            "localentrynotfound",
            "network is unreachable",
            "snapshot_download",
            "connecterror",
        )
    )
    if ocr_hit and not hf_hit:
        return "ocr_missing"
    if hf_hit or "offline" in msg:
        return "hf_offline"
    return "ingest.failed"


def slices_from_markdown(md: str, title: str) -> list[dict]:
    text = (md or "").replace("\r\n", "\n").strip()
    heading = (title or "").strip() or "未命名"
    if not text:
        return [{"title": heading, "excerpt": heading, "tags": ["empty"]}]
    blocks: list[str] = []
    buf: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#"):
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
            blocks.append(line.lstrip("# ").strip())
        elif line.strip() == "":
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line.strip())
    if buf:
        blocks.append("\n".join(buf).strip())
    out = []
    for block in blocks:
        chunk = block.strip()
        if len(chunk) < 1:
            continue
        out.append(
            {
                "title": heading[:200],
                "excerpt": chunk[:MAX_EXCERPT],
                "tags": ["docling"],
            }
        )
        if len(out) >= MAX_SLICES:
            break
    if not out:
        out.append({"title": heading[:200], "excerpt": text[:MAX_EXCERPT], "tags": ["docling"]})
    return out


def _make_converter():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    flags = pdf_ocr_settings()
    onnx = rapidocr_onnx_paths()
    kwargs = {
        "force_full_page_ocr": True,
        "lang": ["chinese", "english"],
        "backend": "onnxruntime",
    }
    if onnx.get("det"):
        kwargs["det_model_path"] = onnx["det"]
    if onnx.get("rec"):
        kwargs["rec_model_path"] = onnx["rec"]
    if onnx.get("cls"):
        kwargs["cls_model_path"] = onnx["cls"]
    try:
        from docling.datamodel.pipeline_options import OcrMode

        ocr = RapidOcrOptions(mode=OcrMode.FULL_PAGE, **kwargs)
    except TypeError:
        kwargs.pop("backend", None)
        try:
            ocr = RapidOcrOptions(**kwargs)
        except TypeError:
            ocr = RapidOcrOptions(force_full_page_ocr=True)
    art = Path(flags["artifacts_path"])
    opts = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=ocr,
        artifacts_path=str(art) if art.exists() else None,
    )
    if hasattr(opts, "enable_remote_services"):
        opts.enable_remote_services = False
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def _converter():
    global _CONVERTER
    if _CONVERTER is None:
        _CONVERTER = _make_converter()
    return _CONVERTER


def _convert_path(path: Path) -> str:
    result = _converter().convert(str(path))
    document = getattr(result, "document", None)
    if document is None:
        return ""
    export = getattr(document, "export_to_markdown", None)
    if callable(export):
        return str(export() or "")
    return str(document)


def ingest_bytes(*, filename: str, data: bytes, title: str) -> dict:
    suffix = Path(filename or "file.bin").suffix or ".bin"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / f"src{suffix}"
            dest.write_bytes(data or b"")
            md = _convert_path(dest)
    except Exception as exc:
        code = classify_convert_error(exc)
        return {
            "ok": False,
            "engine": ENGINE,
            "unread": True,
            "code": code,
            "error": str(exc),
            "slices": [],
        }
    slices = slices_from_markdown(md, title or filename or "文件")
    body = " ".join(s.get("excerpt") or "" for s in slices).strip()
    heading = (title or filename or "").strip()
    if not md.strip() or not body or body == heading:
        return {
            "ok": False,
            "engine": ENGINE,
            "unread": True,
            "code": "empty",
            "error": "empty",
            "slices": [],
        }
    return {"ok": True, "engine": ENGINE, "slices": slices}


def ingest_text(*, text: str, title: str) -> dict:
    md = text or ""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "src.md"
            dest.write_text(md, encoding="utf-8")
            md = _convert_path(dest) or md
    except Exception:
        pass
    return {
        "ok": True,
        "engine": ENGINE,
        "slices": slices_from_markdown(md or text, title or "文"),
    }
