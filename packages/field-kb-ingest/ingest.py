"""field-kb-ingest · thin adapter over Docling format backends + RapidOCR.

Office/markdown/html: Docling's per-format backends (msword/msexcel/mspowerpoint/
md/html) called directly. Never ``DocumentConverter`` — its module import pulls
the PDF backend (``docling_parse``) and the torch layout stack, which the
no-torch image does not carry (T-PICO-NO-TORCH). Live 2026-09-14: every Office
ingest failed at that import (#997).

PDF: pypdfium2 text layer first; empty layer → RapidOCR page render (#994 S2,
owner 2026-09-14 — EXPERIENCE §29 amended). Images: RapidOCR. OCR uses the ONNX
models bundled with the ``rapidocr`` wheel unless an artifacts marker overrides.
Not a Pico PDF kernel: no layout, no tables, no torch.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ENGINE = "docling"
ENGINE_PDF = "rapidocr"
ENGINE_PDF_TEXT = "pdfium-text"
ENGINE_OCR = "rapidocr"
MAX_EXCERPT = 800
MAX_SLICES = 8
DEFAULT_ARTIFACTS = "/opt/docling-models"
PDF_RENDER_SCALE = 2.5
PDF_VISION_SCALE = 1.25
MAX_PDF_VISION_PAGES = 32
MAX_PDF_PAGE_PNG = 6 * 1024 * 1024
# Scan OCR page budget for kb/ingest. A 100-page scanned exam is minutes of CPU;
# past the cap we index what we read and say so (tag ``ocr-truncated``).
DEFAULT_OCR_MAX_PAGES = 40

# suffix → (InputFormat name, backend module, backend class). Docling upstream,
# no PDF/IMAGE here (those go to pypdfium2 / RapidOCR below).
OFFICE_BACKENDS: dict[str, tuple[str, str, str]] = {
    ".docx": ("DOCX", "docling.backend.msword_backend", "MsWordDocumentBackend"),
    ".xlsx": ("XLSX", "docling.backend.msexcel_backend", "MsExcelDocumentBackend"),
    ".pptx": ("PPTX", "docling.backend.mspowerpoint_backend", "MsPowerpointDocumentBackend"),
    ".md": ("MD", "docling.backend.md_backend", "MarkdownDocumentBackend"),
    ".markdown": ("MD", "docling.backend.md_backend", "MarkdownDocumentBackend"),
    ".html": ("HTML", "docling.backend.html_backend", "HTMLDocumentBackend"),
    ".htm": ("HTML", "docling.backend.html_backend", "HTMLDocumentBackend"),
}
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
# Legacy OLE / other formats are not converted here (paperclip path converts
# .doc via soffice before it reaches Pico; kb/ingest receives the file as-is).
UNSUPPORTED_HINT = {
    ".doc": "旧版 .doc 请先另存为 .docx 再入库",
    ".xls": "旧版 .xls 请先另存为 .xlsx 再入库",
    ".ppt": "旧版 .ppt 请先另存为 .pptx 再入库",
}


class UnsupportedFormat(Exception):
    """kb/ingest cannot read this suffix. Carries the suffix for the code table."""

    def __init__(self, suffix: str) -> None:
        super().__init__(f"unsupported format {suffix or '(none)'}")
        self.suffix = suffix


def ocr_max_pages() -> int:
    raw = (os.environ.get("PICO_KB_OCR_MAX_PAGES") or "").strip()
    try:
        n = int(raw) if raw else DEFAULT_OCR_MAX_PAGES
    except ValueError:
        n = DEFAULT_OCR_MAX_PAGES
    return max(1, n)


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
    if isinstance(exc, UnsupportedFormat):
        return "unsupported_format"
    msg = f"{type(exc).__name__} {exc}".lower()
    if isinstance(exc, ModuleNotFoundError) and "docling" in msg:
        return "docling_missing"
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


def _office_backend(suffix: str):
    """Resolve (InputFormat, backend class) for an Office/markup suffix."""
    import importlib

    spec = OFFICE_BACKENDS.get(suffix.lower())
    if spec is None:
        raise UnsupportedFormat(suffix)
    fmt_name, module_name, class_name = spec
    from docling.datamodel.base_models import InputFormat

    module = importlib.import_module(module_name)
    return InputFormat[fmt_name], getattr(module, class_name)


def _convert_path(path: Path) -> str:
    """Docling format backend → markdown. No DocumentConverter (see module doc)."""
    from docling.datamodel.document import InputDocument

    fmt, backend_cls = _office_backend(path.suffix)
    in_doc = InputDocument(path_or_stream=path, format=fmt, backend=backend_cls, filename=path.name)
    backend = backend_cls(in_doc, path)
    document = backend.convert()
    export = getattr(document, "export_to_markdown", None)
    if callable(export):
        return str(export() or "")
    return str(document or "")


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


def bundled_rapidocr_onnx_paths() -> dict[str, str]:
    """ONNX shipped inside the ``rapidocr`` wheel (det/rec/cls). Zero downloads."""
    try:
        import rapidocr
    except Exception:
        return {}
    root = Path(getattr(rapidocr, "__file__", "") or "").parent / "models"
    if not root.is_dir():
        return {}
    out: dict[str, str] = {}
    for key in ("det", "rec", "cls"):
        hit = next(iter(sorted(root.glob(f"*{key}*.onnx"))), None)
        if hit is not None:
            out[key] = str(hit)
    return out if len(out) == 3 else {}


def resolve_rapidocr_onnx() -> dict[str, str]:
    """Artifacts marker wins; otherwise the wheel's bundled models."""
    onnx = rapidocr_onnx_paths()
    if all(onnx.get(k) and Path(onnx[k]).is_file() for k in ("det", "rec", "cls")):
        return onnx
    return bundled_rapidocr_onnx_paths()


def _rapidocr_engine():
    global _OCR
    if _OCR is not None:
        return _OCR
    onnx = resolve_rapidocr_onnx()
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


def _ocr_image(path: Path) -> str:
    """Single raster image → text via RapidOCR."""
    import numpy as np
    from PIL import Image

    engine = _rapidocr_engine()
    with Image.open(path) as im:
        arr = np.asarray(im.convert("RGB"))
    return _rapidocr_text(engine(arr)).strip()


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


def _ocr_pdf_pages(path: Path, *, max_pages: int | None = None) -> str:
    """Render each PDF page to an image and OCR. No Docling layout / torch.

    Stops after ``max_pages`` (default ``PICO_KB_OCR_MAX_PAGES`` / 40); the
    caller tags the result ``ocr-truncated`` when pages were skipped.
    """
    import numpy as np
    import pypdfium2 as pdfium

    engine = _rapidocr_engine()
    doc = pdfium.PdfDocument(str(path))
    parts: list[str] = []
    limit = max(1, int(max_pages or ocr_max_pages()))
    try:
        for i in range(min(len(doc), limit)):
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


def _png_bytes(pil) -> bytes:
    from io import BytesIO

    image = pil.convert("RGB")
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    if len(raw) <= MAX_PDF_PAGE_PNG:
        return raw
    width, height = image.size
    scale = (MAX_PDF_PAGE_PNG / max(len(raw), 1)) ** 0.5
    nxt = max(32, int(width * scale)), max(32, int(height * scale))
    image = image.resize(nxt)
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()[:MAX_PDF_PAGE_PNG]


def render_pdf_page_pngs(data: bytes, *, max_pages: int = MAX_PDF_VISION_PAGES) -> list[bytes]:
    """Raster PDF pages with pypdfium2 (same renderer as scan OCR). Not a Pico PDF kernel."""
    if not data:
        return []
    try:
        import pypdfium2 as pdfium
    except Exception:
        return []
    doc = None
    out: list[bytes] = []
    try:
        doc = pdfium.PdfDocument(data)
        limit = min(len(doc), max(1, int(max_pages or MAX_PDF_VISION_PAGES)))
        for i in range(limit):
            page = doc[i]
            bitmap = page.render(scale=PDF_VISION_SCALE)
            try:
                pil = bitmap.to_pil()
            finally:
                close = getattr(bitmap, "close", None)
                if callable(close):
                    close()
            png = _png_bytes(pil)
            if png.startswith(b"\x89PNG"):
                out.append(png)
            close_page = getattr(page, "close", None)
            if callable(close_page):
                close_page()
    except Exception:
        return out
    finally:
        if doc is not None:
            close_doc = getattr(doc, "close", None)
            if callable(close_doc):
                close_doc()
    return out


def _pdf_page_count(path: Path) -> int:
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(path))
        try:
            return len(doc)
        finally:
            close_doc = getattr(doc, "close", None)
            if callable(close_doc):
                close_doc()
    except Exception:
        return 0


def _extract(path: Path, suffix: str) -> tuple[str, str, list[str]]:
    low = suffix.lower()
    if low == ".pdf":
        layer = _pdf_text_layer(path)
        if layer.strip():
            return layer, ENGINE_PDF_TEXT, ["pdfium"]
        # Empty text layer = scan. OCR fallback (#994 S2 · owner 2026-09-14).
        tags = ["pdfium", "empty-layer", "ocr"]
        text = _ocr_pdf_pages(path)
        if _pdf_page_count(path) > ocr_max_pages():
            tags.append("ocr-truncated")
        return text, ENGINE_OCR, tags
    if low in IMAGE_SUFFIXES:
        return _ocr_image(path), ENGINE_OCR, ["image", "ocr"]
    if low in UNSUPPORTED_HINT or low not in OFFICE_BACKENDS:
        raise UnsupportedFormat(low)
    return _convert_path(path), ENGINE, ["docling"]


def human_error(code: str, *, suffix: str = "", engine: str = "") -> str:
    """Teacher-facing line for a failed ingest. edu shows this verbatim."""
    sfx = (suffix or "").lower()
    if code == "unsupported_format":
        hint = UNSUPPORTED_HINT.get(sfx)
        if hint:
            return f"这种格式（{sfx}）知识库读不了。{hint}。"
        return (
            f"这种格式（{sfx or '无后缀'}）知识库读不了。"
            "支持：docx / xlsx / pptx / md / html / PDF / png / jpg。"
        )
    if code == "empty":
        if engine == ENGINE_OCR:
            return "这份是扫描件或图片，OCR 没认出文字。换清晰一点的版本，或先转成带文字层的 PDF。"
        return "文件里没读到文字。空文档、纯图形或受保护的文件都会这样。"
    if code == "ocr_missing":
        return "OCR 引擎没就位，扫描件暂时读不了。请管理员看镜像里的 RapidOCR 模型。"
    if code == "docling_missing":
        return "文档转换引擎没就位，请管理员看镜像里的 Docling 后端。"
    if code == "hf_offline":
        return "文档转换需要的模型没在机上，请管理员看模型目录。"
    return "这份没读出来。换个格式再试；持续失败请把文件名发给管理员。"


def ingest_bytes(*, filename: str, data: bytes, title: str) -> dict:
    suffix = Path(filename or "file.bin").suffix or ".bin"
    low = suffix.lower()
    if low == ".pdf":
        engine = ENGINE_PDF_TEXT
    elif low in IMAGE_SUFFIXES:
        engine = ENGINE_OCR
    else:
        engine = ENGINE
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
            "error": human_error(code, suffix=low, engine=engine),
            "detail": f"{type(exc).__name__}: {str(exc)[:200]}",
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
            "error": human_error("empty", suffix=low, engine=engine),
            "slices": [],
        }
    return {"ok": True, "engine": engine, "tags": tags, "slices": slices}


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
