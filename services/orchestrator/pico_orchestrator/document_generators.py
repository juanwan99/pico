"""Deterministic allowlist document generators (HTML / DOCX / PPTX / XLSX).

HTML stays stdlib. Word / PPT / Excel are thin python-docx / python-pptx /
openpyxl adapters. Hand-written XLSX XML is a test fixture only.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

# Empty-shell floor only. Do not invent 套话, and do not demand a page quota.
MIN_DOCX_BODY_CHARS = 20
MIN_PPTX_SLIDES = 1
DOCX_BODY_TOO_SHORT = (
    "Word 正文是空的。请写入实际内容再调用 generate_docx_document，"
    "系统不会垫字。"
)
PPTX_SLIDES_TOO_FEW = (
    "PPT 没有可渲染的页。请写入至少一页再调用 generate_pptx_document，"
    "系统不会垫页。"
)
# Interactive HTML must run with no network (school offline / CSP). Do not
# allowlist jsdelivr. Do not vendor Three.js. Body over DOC_BODY_MAX fails
# closed — never silent-slice a draft (#829).
DOC_BODY_MAX = 200_000
HTML_INTERACTIVE_CSP = (
    "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
    "script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none';"
)
HTML_REMOTE_ENGINE_ERROR = (
    "这份 HTML 依赖外网资源或外链引擎（script/import/CDN/外链图/"
    "Three.js/Chart.js），本地或学校网会打不开。"
    "请用页内脚本和 canvas 自绘，图片只用 data: URL。"
    "不要 Three.js/Chart.js/ECharts/KaTeX CDN，不要 import 或 script src 外链，"
    "也不要假定 window.THREE 已经加载。"
)
# Protocol-relative //cdn… and https?:// — teacher HTML is srcDoc/file, no host.
_REMOTE_URL = r"(?:https?:)?//[A-Za-z0-9]"
_CSP_META_RE = re.compile(
    r"<meta\b[^>]*http-equiv\s*=\s*[\"']Content-Security-Policy[\"'][^>]*>\s*",
    re.IGNORECASE,
)
_LINK_HTTPS_RE = re.compile(
    r"<link\b(?=[^>]*\bhref\s*=\s*[\"']?(?:https?:)?//)[^>]*>",
    re.IGNORECASE,
)

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _visible_len(text: str) -> int:
    return sum(1 for ch in (text or "") if not ch.isspace())


def _display_title(title: str, fallback: str) -> str:
    name = (title or "").strip() or fallback
    lower = name.lower()
    for ext in (".docx", ".pptx", ".xlsx", ".html", ".htm", ".md"):
        if lower.endswith(ext):
            stem = name[: -len(ext)].strip()
            return stem or fallback
    return name


def _split_blocks(raw: str) -> list[str]:
    text = (raw or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    if "\n---\n" in f"\n{text}\n":
        parts = [p.strip() for p in text.split("\n---\n") if p.strip()]
        if parts:
            return parts
    chunks = [part.strip() for part in text.split("\n\n") if part.strip()]
    if chunks:
        return chunks
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def docx_visible_text(raw: bytes) -> str:
    """Visible Word paragraphs from OOXML (stdlib zip+xml). Empty on junk."""
    if not raw or raw[:2] != b"PK":
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml = zf.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile):
        return ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    paras: list[str] = []
    for p in root.iter(f"{_W_NS}p"):
        line = "".join(t.text or "" for t in p.iter(f"{_W_NS}t")).strip()
        if line:
            paras.append(line)
    return "\n".join(paras)


def pptx_slide_titles(raw: bytes) -> list[str]:
    """First text run on each slide (title-ish). Empty list on junk."""
    if not raw or raw[:2] != b"PK":
        return []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            slides = sorted(
                n
                for n in names
                if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            )
            titles: list[str] = []
            for path in slides:
                try:
                    xml = zf.read(path)
                except KeyError:
                    titles.append("")
                    continue
                try:
                    root = ET.fromstring(xml)
                except ET.ParseError:
                    titles.append("")
                    continue
                texts = [
                    (node.text or "").strip()
                    for node in root.iter(f"{_A_NS}t")
                    if (node.text or "").strip()
                ]
                titles.append(texts[0] if texts else "")
    except zipfile.BadZipFile:
        return []
    return titles


def office_shell_reason(raw: bytes, ext: str) -> str | None:
    """Chinese reason when a supposed Office file is an empty shell. None if ok."""
    suffix = (ext or "").lower()
    if not suffix.startswith("."):
        suffix = f".{suffix}" if suffix else ""
    if suffix == ".docx":
        text = docx_visible_text(raw)
        if _visible_len(text) < MIN_DOCX_BODY_CHARS:
            return (
                "Word 打开后几乎是空壳。"
                "请用 generate_docx_document 写入实际正文后再交。"
            )
        return None
    if suffix == ".pptx":
        titles = pptx_slide_titles(raw)
        titled = sum(1 for t in titles if (t or "").strip())
        if len(titles) < MIN_PPTX_SLIDES or titled < MIN_PPTX_SLIDES:
            return (
                "PPT 打开后没有可看的页。"
                "请用 generate_pptx_document 写出至少一页后再交。"
            )
        return None
    return None


def require_docx_body(body: str | None) -> None:
    """Fail closed when the caller did not pass enough 题面正文. No padding."""
    if _visible_len(body or "") < MIN_DOCX_BODY_CHARS:
        raise ValueError(DOCX_BODY_TOO_SHORT)


def require_pptx_body(body: str | None) -> None:
    """Fail closed when the caller did not pass any slide block. No padding."""
    if len(_split_blocks(body or "")) < MIN_PPTX_SLIDES:
        raise ValueError(PPTX_SLIDES_TOO_FEW)


def _docx_body_paragraphs(body: str | None) -> list[str]:
    """Caller text only. Never invent 事项说明 / 打开说明 filler."""
    return _split_blocks(body or "")


def _pptx_slides(body: str | None, *, title: str, marker: str) -> list[tuple[str, str]]:
    """One slide per caller block. Never pad 要点/说明 pages."""
    heading = _display_title(title, "Pico PPTX")
    parts = _split_blocks(body or "")
    if not parts:
        return [(heading, f"标记：{marker}")]
    slides: list[tuple[str, str]] = []
    for index, chunk in enumerate(parts):
        first = chunk.split("\n", 1)[0].strip()[:40] or (heading if index == 0 else f"第{index + 1}页")
        slide_body = f"标记：{marker}\n{chunk}" if index == 0 else chunk
        slides.append((first, slide_body))
    return slides[:20]


def _require_marker(marker: str) -> str:
    value = (marker or "").strip()
    if not value:
        # Marker is an internal traceability tag. Auto-generate one when the
        # model omits it — hard-failing here made the true-Pi agent retry the
        # same tool call forever (message_update flood → OOM). A unique tag
        # keeps deliveries traceable without requiring the model to know the
        # internal field.
        import uuid

        value = f"pico-{uuid.uuid4().hex[:12]}"
    if len(value) > 200:
        raise ValueError("marker exceeds 200 characters")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("marker contains control characters")
    return value


def require_doc_body_max(raw: str | None, *, what: str = "正文") -> str:
    """Fail closed when the draft is too long. Never slice."""
    text = raw or ""
    if len(text) > DOC_BODY_MAX:
        raise ValueError(
            f"{what}超过 {DOC_BODY_MAX} 字。请缩短后再交，系统不会截断。"
        )
    return text


def _html_marker_meta(marker: str) -> str:
    """Ledger marker as hidden meta — not a visible 「标记：」 chrome bar."""
    safe = html.escape(marker)
    return (
        f'<meta name="pico-marker" content="{safe}" '
        f'data-pico-marker="{safe}" />'
    )


def _html_body_paragraphs(body: str | None, *, marker: str) -> str:
    """Escape body into one or more <p> blocks (blank-line separated)."""
    raw = require_doc_body_max(
        (body or "").strip() or f"Pico HTML deliverable · {marker}",
        what="这份 HTML",
    )
    chunks = [part.strip() for part in raw.replace("\r\n", "\n").split("\n\n") if part.strip()]
    if not chunks:
        chunks = [f"Pico HTML deliverable · {marker}"]
    parts: list[str] = []
    for chunk in chunks:
        # Single newlines inside a paragraph become <br/>; still fully escaped.
        lines = [html.escape(line) for line in chunk.split("\n")]
        parts.append("<p>" + "<br />\n".join(lines) + "</p>")
    return "\n  ".join(parts)


def _looks_like_full_html_document(raw: str) -> bool:
    """True when agent passed a complete page (not prose to escape into <p>)."""
    s = (raw or "").lstrip().lower()
    if not s:
        return False
    if s.startswith(("<!doctype html", "<html")):
        return True
    # Fragment that is already a self-contained interactive page shell.
    return "<html" in s[:500] and ("</html>" in s or "<body" in s)


def _looks_like_html_markup(raw: str) -> bool:
    """True when body is HTML markup (full page or fragment) — must not escape to a tag wall.

    #399 R2: models often pass ``<h2>…</h2><button>…`` without doctype/html.
    Escaping those tags into ``&lt;h2&gt;`` makes downloads open as a source/tag wall.
    Plain prose without tags still uses the safe paragraph shell.
    """
    if _looks_like_full_html_document(raw):
        return True
    s = (raw or "").strip()
    if not s or "<" not in s:
        return False
    # Structural / interactive tags ⇒ treat as markup to preserve.
    if re.search(
        r"<\s*(?:button|input|table|thead|tbody|tr|td|th|form|script|style|"
        r"div|section|article|nav|header|footer|main|h[1-6]|ul|ol|li|a|span|"
        r"p|img|canvas|svg|label|select|textarea|details|summary)\b",
        s,
        flags=re.IGNORECASE,
    ):
        return True
    # ≥2 generic tags is almost never pure prose.
    tags = re.findall(r"<\s*/?\s*[a-zA-Z][a-zA-Z0-9]*\b", s)
    return len(tags) >= 2


def html_remote_violations(doc: str) -> tuple[str, ...]:
    """Executable or render remote loads. ``<a href=https>`` in prose is allowed."""
    text = doc or ""
    hits: list[str] = []

    def add(name: str) -> None:
        if name not in hits:
            hits.append(name)

    if re.search(rf"<script\b[^>]*\bsrc\s*=\s*[\"']?{_REMOTE_URL}", text, re.IGNORECASE):
        add("script_src")
    if re.search(
        rf"""(?:^|[\s;{{}}(])from\s+["']{_REMOTE_URL}""",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        add("es_import")
    if re.search(
        rf"""(?:^|[\s;{{}}(])import\s+["']{_REMOTE_URL}""",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        add("es_import")
    if re.search(rf"""import\s*\(\s*["']{_REMOTE_URL}""", text, re.IGNORECASE):
        add("es_import")
    if re.search(
        rf"<script\b[^>]*type\s*=\s*[\"']importmap[\"'][^>]*>[\s\S]*?{_REMOTE_URL}",
        text,
        re.IGNORECASE,
    ):
        add("importmap")
    if re.search(rf"<link\b[^>]*\bhref\s*=\s*[\"']?{_REMOTE_URL}", text, re.IGNORECASE):
        add("link_href")
    if re.search(rf"<iframe\b[^>]*\bsrc\s*=\s*[\"']?{_REMOTE_URL}", text, re.IGNORECASE):
        add("iframe_src")
    if re.search(rf"<img\b[^>]*\bsrc\s*=\s*[\"']?{_REMOTE_URL}", text, re.IGNORECASE):
        add("img_src")
    if re.search(rf"\bsrcset\s*=\s*[\"'][^\"']*{_REMOTE_URL}", text, re.IGNORECASE):
        add("img_src")
    if re.search(
        rf"<(?:video|audio|source|embed)\b[^>]*\bsrc\s*=\s*[\"']?{_REMOTE_URL}",
        text,
        re.IGNORECASE,
    ):
        add("media_src")
    if re.search(rf"<object\b[^>]*\bdata\s*=\s*[\"']?{_REMOTE_URL}", text, re.IGNORECASE):
        add("media_src")
    if re.search(rf"""\bfetch\s*\(\s*["']{_REMOTE_URL}""", text, re.IGNORECASE):
        add("fetch")
    if re.search(rf"url\s*\(\s*['\"]?{_REMOTE_URL}", text, re.IGNORECASE):
        add("css_url")
    return tuple(hits)


def html_engine_violations(doc: str) -> tuple[str, ...]:
    """Page expects Three/Chart/ECharts/KaTeX that Pico will not load."""
    text = doc or ""
    hits: list[str] = []

    def add(name: str) -> None:
        if name not in hits:
            hits.append(name)

    if re.search(r"""from\s+['"]three(?:/[^'"]*)?['"]""", text, re.IGNORECASE):
        add("three_import")
    if re.search(r"""import\s*\(\s*['"]three(?:/[^'"]*)?['"]""", text, re.IGNORECASE):
        add("three_import")
    if re.search(r"""from\s+['"]chart\.js['"]""", text, re.IGNORECASE):
        add("chart_import")
    if re.search(r"""from\s+['"]echarts['"]""", text, re.IGNORECASE):
        add("echarts_import")
    if re.search(
        r"\bwindow\.THREE\b|\btypeof\s+THREE\b|\bnew\s+THREE\.|"
        r"\bTHREE\.(?:Scene|WebGLRenderer|PerspectiveCamera|Clock|Mesh)\b",
        text,
    ):
        add("three_global")
    if re.search(r"\bnew\s+Chart\s*\(", text):
        add("chart_global")
    if re.search(r"\becharts\s*\.\s*init\s*\(", text):
        add("echarts_global")
    if re.search(r"\bkatex\s*\.\s*render", text, re.IGNORECASE):
        add("katex_global")
    return tuple(hits)


def _strip_remote_stylesheets(doc: str) -> str:
    """Drop remote CSS/font links. Engine scripts are not stripped-to-succeed."""
    return _LINK_HTTPS_RE.sub("<!-- stripped remote stylesheet -->", doc or "")


def _strip_remote_script_src(doc: str) -> str:
    """Legacy helper. CDN engines fail-closed; this only strips https stylesheets."""
    return _strip_remote_stylesheets(doc)


def _require_offline_html(doc: str) -> str:
    """Fail closed if the page still needs the network or a CDN engine."""
    cleaned = _strip_remote_stylesheets(doc)
    if html_remote_violations(cleaned) or html_engine_violations(cleaned):
        raise ValueError(HTML_REMOTE_ENGINE_ERROR)
    return cleaned


def _force_interactive_csp(doc: str) -> str:
    """Replace every CSP meta with one legal offline policy (no quote-truncation)."""
    text = _CSP_META_RE.sub("", doc or "")
    meta = (
        f'<meta http-equiv="Content-Security-Policy" content="{HTML_INTERACTIVE_CSP}" />'
    )
    if re.search(r"<head\b", text, re.IGNORECASE):
        return re.sub(
            r"(<head\b[^>]*>)",
            rf"\1\n  {meta}",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    if re.search(r"<html\b", text, re.IGNORECASE):
        return re.sub(
            r"(<html\b[^>]*>)",
            rf"\1\n<head>\n  {meta}\n</head>",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"<head>\n  {meta}\n</head>\n{text}"


def _wrap_html_fragment(raw_body: str, *, title: str, marker: str) -> str:
    """Wrap an HTML fragment in a minimal interactive document shell (tags kept)."""
    safe_title = html.escape((title or "Pico HTML").strip() or "Pico HTML")
    body = _CSP_META_RE.sub("", _require_offline_html(raw_body))
    csp = HTML_INTERACTIVE_CSP
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="Content-Security-Policy" content="{csp}" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  {_html_marker_meta(marker)}
  <title>{safe_title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; color: #1a1a1a; line-height: 1.5; max-width: 48rem; }}
    h1, h2, h3 {{ line-height: 1.25; }}
  </style>
</head>
<body>
  {body}
</body>
</html>
"""


def _inject_marker_into_html(doc: str, *, marker: str, title: str) -> str:
    """Ensure marker is present; do not wrap interactive markup as escaped prose."""
    if "data-pico-marker=" not in doc:
        meta = _html_marker_meta(marker)
        if re.search(r"<head\b", doc, flags=re.IGNORECASE):
            doc = re.sub(
                r"(<head\b[^>]*>)",
                r"\1\n  " + meta,
                doc,
                count=1,
                flags=re.IGNORECASE,
            )
        elif re.search(r"<html\b", doc, flags=re.IGNORECASE):
            doc = re.sub(
                r"(<html\b[^>]*>)",
                rf"\1\n<head>\n  {meta}\n</head>",
                doc,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            doc = meta + "\n" + doc
    # Prefer caller title when document title is empty/generic.
    if title and re.search(r"<title>\s*</title>", doc, flags=re.IGNORECASE):
        doc = re.sub(
            r"<title>\s*</title>",
            f"<title>{html.escape(title)}</title>",
            doc,
            count=1,
            flags=re.IGNORECASE,
        )
    # Interactive local pages need inline script. Replace the whole CSP meta
    # (values contain quotes; a [^\"]* capture truncates and glues leftover CDN).
    return _force_interactive_csp(doc)


def build_html_document(
    *,
    title: str,
    marker: str,
    body: str | None = None,
) -> bytes:
    """HTML bytes with unique marker.

    - Prose body → safe escaped paragraphs inside a shell (no script).
    - Full HTML document body → kept as interactive page (CDN/engine fail-closed).
      This prevents H-CODEDUMP where agents pass real UI source only to see it
      escaped into a source wall.
    """
    marker = _require_marker(marker)
    safe_title = html.escape((title or "Pico HTML").strip() or "Pico HTML")
    raw_body = require_doc_body_max((body or "").strip(), what="这份 HTML")

    page_title = (title or "").strip() or "Pico HTML"
    if _looks_like_full_html_document(raw_body):
        doc = _require_offline_html(raw_body)
        doc = _inject_marker_into_html(doc, marker=marker, title=page_title)
        if "data-pico-marker=" not in doc:
            # Extremely broken fragment — fall through to markup/prose paths.
            pass
        else:
            return doc.encode("utf-8")

    # #399 R2: HTML fragments keep real tags (wrap shell); only pure prose is escaped.
    if raw_body and _looks_like_html_markup(raw_body) and not _looks_like_full_html_document(
        raw_body
    ):
        doc = _wrap_html_fragment(raw_body, title=page_title, marker=marker)
        return doc.encode("utf-8")

    body_html = _html_body_paragraphs(raw_body or None, marker=marker)
    # Prose shell: CSP blocks scripts (static reading page).
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  {_html_marker_meta(marker)}
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; color: #1a1a1a; line-height: 1.5; max-width: 48rem; }}
    h1 {{ font-size: 1.5rem; }}
  </style>
</head>
<body>
  <h1>{safe_title}</h1>
  {body_html}
</body>
</html>
"""
    return doc.encode("utf-8")


def build_docx_document(
    *,
    title: str,
    marker: str,
    body: str | None = None,
) -> bytes:
    """python-docx Word with the caller body. Does not pad 套话 to hit a quota."""
    marker = _require_marker(marker)
    heading = _display_title(title, "Pico DOCX")
    from pico_orchestrator.office.render import render_spec
    from pico_orchestrator.office.spec import spec_from_plain

    return render_spec(
        spec_from_plain(kind="docx", title=heading, marker=marker, body=body)
    )


KNOWN_CALC_CELL = "NIGHT-P4-CELL-ALPHA"


def build_xlsx_legacy_xml(
    *,
    title: str,
    marker: str,
    body: str | None = None,
) -> bytes:
    """Hand-written XLSX XML — test fixture only. Teacher path uses openpyxl."""
    marker = _require_marker(marker)
    cell = escape((body or "").strip() or KNOWN_CALC_CELL)
    marker_xml = escape(marker)
    heading = escape((title or "Pico XLSX").strip() or "Pico XLSX")

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="16"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf/></cellStyleXfs>
  <cellXfs count="1"><xf/></cellXfs>
</styleSheet>
"""
    sheet = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols><col min="1" max="1" width="42" customWidth="1"/></cols>
  <sheetData>
    <row r="1" ht="24" customHeight="1">
      <c r="A1" t="inlineStr"><is><t>{cell}</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="inlineStr"><is><t>{heading}</t></is></c>
    </row>
    <row r="3">
      <c r="A3" t="inlineStr"><is><t>marker:{marker_xml}</t></is></c>
    </row>
  </sheetData>
</worksheet>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
        zf.writestr("xl/styles.xml", styles)
    return buf.getvalue()


def build_xlsx_document(
    *,
    title: str,
    marker: str,
    body: str | None = None,
) -> bytes:
    """openpyxl Excel. A1 is the caller body (or night-calc marker)."""
    from pico_orchestrator.office.render import render_spec
    from pico_orchestrator.office.spec import spec_from_plain

    marker = _require_marker(marker)
    heading = _display_title(title, "Pico XLSX")
    return render_spec(
        spec_from_plain(kind="xlsx", title=heading, marker=marker, body=body)
    )


def _set_slide_title_body(slide: object, heading: str, body: str) -> None:
    title_shape = getattr(getattr(slide, "shapes", None), "title", None)
    if title_shape is not None and getattr(title_shape, "has_text_frame", False):
        title_shape.text = heading
    body_set = False
    placeholders = getattr(slide, "placeholders", None)
    if placeholders is not None:
        for shape in placeholders:
            idx = getattr(getattr(shape, "placeholder_format", None), "idx", None)
            if idx == 1 and getattr(shape, "has_text_frame", False):
                shape.text = body
                body_set = True
                break
    if not body_set:
        for shape in getattr(slide, "shapes", []):
            if shape is title_shape:
                continue
            if getattr(shape, "has_text_frame", False):
                shape.text = body
                body_set = True
                break
    if title_shape is None:
        for shape in getattr(slide, "shapes", []):
            if getattr(shape, "has_text_frame", False):
                shape.text = heading
                break


def build_pptx_document(
    *,
    title: str,
    marker: str,
    body: str | None = None,
) -> bytes:
    """python-pptx deck from caller slides. Does not pad empty 说明 pages."""
    marker = _require_marker(marker)
    heading = _display_title(title, "Pico PPTX")
    from pico_orchestrator.office.render import render_spec
    from pico_orchestrator.office.spec import spec_from_plain

    return render_spec(
        spec_from_plain(kind="pptx", title=heading, marker=marker, body=body)
    )
