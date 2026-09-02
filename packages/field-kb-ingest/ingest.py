"""field-kb-ingest · Office: Docling. Scan PDF: pypdfium2 + RapidOCR ONNX."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ENGINE = "docling"
ENGINE_PDF = "rapidocr"
ENGINE_PDF_TEXT = "pdfium-text"
MAX_EXCERPT = 800
MAX_SLICES = 8
DEFAULT_ARTIFACTS = "/opt/docling-models"
PDF_RENDER_SCALE = 2.5

_CONVERTER = None
_OCR = None


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
    """Flags for the scan-PDF path. Unit-tested without importing RapidOCR."""
    return {
        "do_ocr": True,
        "force_full_page_ocr": True,
        "engine": "rapidocr",
        "renderer": "pypdfium2",
        "artifacts_path": str(artifacts_path()),
    }


def classify_convert_error(exc: BaseException) -> str:
    msg = f"{type(exc).__name__} {exc}".lower()
    ocr_hit = any(
        s in msg
        for s in (
            "no ocr engine",
            "ocr engine found",
            "libxcb",
            "cannot open shared object",
            "rapidocr onnx",
            "onnx missing",
        )
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


def slices_from_markdown(md: str, title: str, tags: list[str] | None = None) -> list[dict]:
    text = (md or "").replace("\r\n", "\n").strip()
    heading = (title or "").strip() or "未命名"
    tag_list = list(tags) if tags else ["docling"]
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
                "tags": tag_list,
            }
        )
        if len(out) >= MAX_SLICES:
            break
    if not out:
        out.append({"title": heading[:200], "excerpt": text[:MAX_EXCERPT], "tags": tag_list})
    return out


def _make_converter():
    """Office (docx/xlsx). Scan PDF does not use this path."""
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


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


def _rapidocr_text(out) -> str:
    if out is None:
        return ""
    txts = getattr(out, "txts", None)
    if txts:
        return "\n".join(str(t) for t in txts if t)
    to_md = getattr(out, "to_markdown", None)
    if callable(to_md):
        return str(to_md() or "")
    return str(out or "")


def _rapidocr_engine():
    global _OCR
    if _OCR is not None:
        return _OCR
    onnx = rapidocr_onnx_paths()
    missing = [k for k in ("det", "rec", "cls") if not onnx.get(k) or not Path(onnx[k]).is_file()]
    if missing:
        raise RuntimeError(f"No OCR engine found: rapidocr onnx missing {missing}")
    from rapidocr import RapidOCR

    _OCR = RapidOCR(
        params={
            "Det.model_path": onnx["det"],
            "Rec.model_path": onnx["rec"],
            "Cls.model_path": onnx["cls"],
        }
    )
    return _OCR


def _pdf_text_layer(path: Path) -> str:
    """Digital PDF text layer via pypdfium2 (already the scan renderer). Not a Pico PDF kernel."""
    try:
        import pypdfium2 as pdfium
    except Exception:
        return ""
    doc = None
    try:
        doc = pdfium.PdfDocument(str(path))
        parts: list[str] = []
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            try:
                text = ""
                bounded = getattr(tp, "get_text_bounded", None)
                if callable(bounded):
                    text = str(bounded() or "")
                if not text.strip():
                    ranged = getattr(tp, "get_text_range", None)
                    if callable(ranged):
                        text = str(ranged() or "")
                text = text.replace("\r\n", "\n").strip()
                if text:
                    parts.append(text)
            finally:
                close_tp = getattr(tp, "close", None)
                if callable(close_tp):
                    close_tp()
                close_page = getattr(page, "close", None)
                if callable(close_page):
                    close_page()
        return "\n\n".join(parts)
    except Exception:
        return ""
    finally:
        if doc is not None:
            close_doc = getattr(doc, "close", None)
            if callable(close_doc):
                close_doc()


def _ocr_pdf_pages(path: Path) -> str:
    """Render each PDF page to an image and OCR. No Docling layout / torch."""
    import numpy as np
    import pypdfium2 as pdfium

    engine = _rapidocr_engine()
    doc = pdfium.PdfDocument(str(path))
    parts: list[str] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            bitmap = page.render(scale=PDF_RENDER_SCALE)
            try:
                pil = bitmap.to_pil()
            finally:
                close = getattr(bitmap, "close", None)
                if callable(close):
                    close()
            arr = np.asarray(pil.convert("RGB"))
            text = _rapidocr_text(engine(arr)).strip()
            if text:
                parts.append(text)
            close_page = getattr(page, "close", None)
            if callable(close_page):
                close_page()
    finally:
        close_doc = getattr(doc, "close", None)
        if callable(close_doc):
            close_doc()
    return "\n\n".join(parts)


def _extract(path: Path, suffix: str) -> tuple[str, str, list[str]]:
    if suffix.lower() == ".pdf":
        layer = _pdf_text_layer(path)
        if layer.strip():
            return layer, ENGINE_PDF_TEXT, ["pdfium"]
        return _ocr_pdf_pages(path), ENGINE_PDF, ["rapidocr"]
    return _convert_path(path), ENGINE, ["docling"]


def ingest_bytes(*, filename: str, data: bytes, title: str) -> dict:
    suffix = Path(filename or "file.bin").suffix or ".bin"
    engine = ENGINE_PDF if suffix.lower() == ".pdf" else ENGINE
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / f"src{suffix}"
            dest.write_bytes(data or b"")
            md, engine, tags = _extract(dest, suffix)
    except Exception as exc:
        code = classify_convert_error(exc)
        return {
            "ok": False,
            "engine": engine,
            "unread": True,
            "code": code,
            "error": str(exc),
            "slices": [],
        }
    slices = slices_from_markdown(md, title or filename or "文件", tags=tags)
    body = " ".join(s.get("excerpt") or "" for s in slices).strip()
    heading = (title or filename or "").strip()
    if not md.strip() or not body or body == heading:
        return {
            "ok": False,
            "engine": engine,
            "unread": True,
            "code": "empty",
            "error": "empty",
            "slices": [],
        }
    return {"ok": True, "engine": engine, "slices": slices}


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
