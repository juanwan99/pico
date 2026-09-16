"""Meilisearch projection of membership materials. Ledger is the only source of truth."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Protocol

logger = logging.getLogger(__name__)

INDEX = "pico_materials"
PRIMARY_KEY = "chunk_id"
FILTERABLE = ["school_id", "membership_id", "scope", "artifact_id"]
SEARCHABLE = ["title", "heading", "text", "parent_text"]
DISPLAYED = [
    "chunk_id",
    "artifact_id",
    "material_id",
    "title",
    "heading",
    "page",
    "text",
    "parent_text",
    "seq",
    "scope",
    "school_id",
    "membership_id",
    "created_at",
]
MAX_TEXT = 200_000
# Bookkeeping chips that used to flood the index (735/953 on the live school).
NOISE_TITLES = frozenset({"回复摘要", "summary", "run summary", "工具产物"})
# Fixture / probe tenants. Live Meili had 6081 school-a chunks vs 2613 real-school.
# Skip on reindex so prod-update does not put the lab back. Not a janitor service.
LAB_SCHOOLS = frozenset(
    {
        "school-a",
        "school-b",
        "school-other",
        "other-school",
        "other-sch",
        "demo-school",
        "school-demo",
        "regress-school",
        "load-school",
        "gwprobe-school",
        "handtest-kb",
        "kb-usable-684",
        "11111111-1111-4111-8111-111111111111",
        "2a2b0002-7a22-4a22-8a22-000000000022",
        "c1a55e00-1111-4111-8111-00000000a001",
    }
)
LAB_SCHOOL_PREFIXES = ("ttfb-", "s3probe-")
TITLE_ONLY_EXTS = frozenset({".doc", ".ppt", ".xls"})
# Embedding / rerank only via New API (#1005). Pico never PATCHes a vendor
# embedder URL into Meili. Leftover Zhipu/SF REST targets are stripped.

MATERIAL_KINDS = frozenset(
    {
        "file",
        "text",
        "md",
        "doc",
        "material",
        "kb_text",
        "edu_office",
        "edu_excerpt",
        "pdf",
        "docx",
        "xlsx",
        "pptx",
        "txt",
    }
)
SKIP_KINDS = frozenset({"html", "png", "image", "screenshot", "preview", "form_entry"})
PARSE_EXT = frozenset({".pdf", ".docx"})
OFFICE_EXTRACT_EXT = frozenset({".xlsx", ".pptx", ".txt", ".csv", ".tsv"})
TABLE_EXTRACT_EXT = frozenset({".xlsx", ".csv", ".tsv"})
# Embed the stored child only. Title in the vector pulled filename-similar
# junk above the quote (#1020). A 180-char / 400-byte stub makes revision
# siblings look identical. CHILD_MAX is 450 CJK ≈ 1.4KiB; 2000 bytes fits.
EMBED_DOCUMENT_TEMPLATE = "{{doc.text}}"
EMBED_TEMPLATE_MAX_BYTES = 2000
TITLE_HIT_CAP = 20
MATERIAL_EXTS = frozenset({".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".json"})
_ID_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
# Meili primary keys: alphanumeric / hyphen / underscore only. Colon is illegal
# (live A2 wrote uuid:0000 → every documentAddition failed, index stayed empty).
_MEILI_ID_BAD = re.compile(r"[^A-Za-z0-9_-]")


def chunk_doc_id(artifact_id: str, seq: int) -> str:
    """Stable Meili primary key for one chunk of one ledger artifact."""
    base = _MEILI_ID_BAD.sub("_", str(artifact_id or "").strip())[:480]
    if not base:
        raise ValueError("empty artifact_id")
    return f"{base}_{int(seq):04d}"
# Process-local: avoid PATCH settings on every upsert (floods Meili task queue).
_ENSURE_CACHE: dict[str, bool] = {}


class HttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 8.0,
    ) -> tuple[int, Any]: ...


class HttpxClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 8.0,
    ) -> tuple[int, Any]:
        import httpx

        resp = httpx.request(method, url, json=json, headers=headers, timeout=timeout)
        body: Any
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = resp.text
        return resp.status_code, body


def meili_url() -> str:
    return (os.environ.get("PICO_MEILI_URL") or "http://127.0.0.1:7700").rstrip("/")


def meili_key() -> str:
    return (os.environ.get("MEILI_MASTER_KEY") or "").strip()


_VENDOR_EMBED_MARKERS = (
    "open.bigmodel.cn",
    "api.siliconflow.cn",
    "zhipuai",
    "siliconflow",
)


def new_api_base() -> str:
    return (os.environ.get("DEEPSEEK_BASE_URL") or "").strip().rstrip("/")


def new_api_key() -> str:
    return (os.environ.get("DEEPSEEK_API_KEY") or "").strip()


def kb_embed_model() -> str:
    return (os.environ.get("PICO_KB_EMBED_MODEL") or "embedding-3").strip() or "embedding-3"


def kb_rerank_model() -> str:
    return (os.environ.get("PICO_KB_RERANK_MODEL") or "rerank").strip() or "rerank"


def kb_rerank_enabled() -> bool:
    """New API rerank is opt-in. Live cheap scores saturate and bury generic hits."""
    flag = (os.environ.get("PICO_KB_RERANK") or "0").strip().lower()
    return flag not in {"0", "false", "off", "no"}


def rerank_scores_usable(scores: list[float]) -> bool:
    """True only when scores can change order. A flat 1.0 list is noise."""
    if len(scores) < 2:
        return False
    return (max(scores) - min(scores)) > 1e-6


def kb_hybrid_ratio() -> float:
    try:
        value = float(os.environ.get("PICO_KB_HYBRID_RATIO") or "0.5")
    except ValueError:
        value = 0.5
    return min(0.9, max(0.1, value))


def kb_search_fetch() -> int:
    """Meili hits per query before file-collapse. Hybrid recall@30 was 0.63, @80 0.69."""
    try:
        value = int(os.environ.get("PICO_KB_FETCH") or "80")
    except ValueError:
        value = 80
    return min(200, max(20, value))


def kb_rerank_pool() -> int:
    """Chunks sent to New API /v1/rerank; collapse to files after scores land."""
    try:
        value = int(os.environ.get("PICO_KB_RERANK_POOL") or "80")
    except ValueError:
        value = 80
    return min(80, max(5, value))


def _is_new_api_loopback(base: str) -> bool:
    """Embedding/rerank only against the box New API, never a vendor or DeepSeek official."""
    low = (base or "").lower()
    if not low:
        return False
    if any(marker in low for marker in _VENDOR_EMBED_MARKERS):
        return False
    if "api.deepseek.com" in low:
        return False
    return "127.0.0.1:3000" in low or "localhost:3000" in low


def new_api_embedder_spec() -> dict[str, Any] | None:
    """Meili REST embedder aimed at New API. Never a vendor host."""
    base = new_api_base()
    key = new_api_key()
    if not base or not key or not _is_new_api_loopback(base):
        return None
    url = f"{base}/embeddings"
    return {
        "source": "rest",
        "url": url,
        "apiKey": key,
        "dimensions": 2048,
        "documentTemplate": EMBED_DOCUMENT_TEMPLATE,
        "documentTemplateMaxBytes": EMBED_TEMPLATE_MAX_BYTES,
        "request": {"model": kb_embed_model(), "input": ["{{text}}"]},
        "response": {"data": [{"embedding": "{{embedding}}"}]},
    }


def rerank_documents(query: str, texts: list[str]) -> list[int] | None:
    """Reorder via New API /v1/rerank. None = keep Meili order (honest)."""
    base = new_api_base()
    key = new_api_key()
    cleaned = [str(t or "")[:2000] for t in texts]
    if not base or not key or not _is_new_api_loopback(base) or not cleaned:
        return None
    try:
        status, body = HttpxClient().request(
            "POST",
            f"{base}/rerank",
            json={
                "model": kb_rerank_model(),
                "query": query,
                "documents": cleaned,
                "top_n": len(cleaned),
            },
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=12.0,
        )
    except Exception:  # noqa: BLE001
        return None
    if status >= 400 or not isinstance(body, dict):
        return None
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return None
    order: list[int] = []
    scores: list[float] = []
    seen: set[int] = set()
    for row in results:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        raw = row.get("relevance_score", row.get("score"))
        try:
            score = float(raw)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(cleaned) and idx not in seen:
            seen.add(idx)
            order.append(idx)
            scores.append(score)
    if not order or not rerank_scores_usable(scores):
        return None
    for idx in range(len(cleaned)):
        if idx not in seen:
            order.append(idx)
    return order


def _apply_rerank_order(hits: list[Any], order: list[int]) -> list[Any]:
    out: list[Any] = []
    seen: set[int] = set()
    for idx in order:
        if 0 <= idx < len(hits) and idx not in seen:
            seen.add(idx)
            out.append(hits[idx])
    for idx, row in enumerate(hits):
        if idx not in seen:
            out.append(row)
    return out


def embedder_provider() -> str | None:
    return "new-api" if new_api_embedder_spec() else None


def embedding_api_key() -> str:
    return new_api_key() if new_api_embedder_spec() else ""


_EMBED_PROBE: tuple[float, bool] | None = None


def embed_query_ok() -> bool:
    """Query-time embed must work. Documents can have leftover vectors while /embeddings is 1113."""
    global _EMBED_PROBE
    spec = new_api_embedder_spec()
    if not spec:
        return False
    import time

    now = time.monotonic()
    if _EMBED_PROBE is not None and now - _EMBED_PROBE[0] < 45.0:
        return _EMBED_PROBE[1]
    ok = False
    try:
        status, body = HttpxClient().request(
            "POST",
            str(spec["url"]),
            json={"model": kb_embed_model(), "input": ["probe"]},
            headers={
                "Authorization": f"Bearer {new_api_key()}",
                "Content-Type": "application/json",
            },
            timeout=4.0,
        )
        ok = status < 400 and isinstance(body, dict) and bool(body.get("data"))
    except Exception:  # noqa: BLE001
        ok = False
    _EMBED_PROBE = (now, ok)
    return ok


def expand_search_queries(query: str) -> list[str]:
    """Two extra keyword strings from New API chat. Empty if the channel is down."""
    flag = (os.environ.get("PICO_KB_QUERY_EXPAND") or "0").strip().lower()
    if flag in {"0", "false", "off", "no"}:
        return []
    q = (query or "").strip()
    if not q or not new_api_base() or not new_api_key() or not _is_new_api_loopback(new_api_base()):
        return []
    model = (os.environ.get("DEEPSEEK_MODEL") or "gpt-5.6-sol").strip() or "gpt-5.6-sol"
    prompt = (
        "老师在搜学校材料。根据这个问题写出 2 条检索词，要用材料里可能出现的专名、文件名、地名、日期，"
        "不要解释。只输出 JSON：{\"q\":[\"...\",\"...\"]}\n问题：" + q[:300]
    )
    try:
        status, body = HttpxClient().request(
            "POST",
            f"{new_api_base()}/responses",
            json={
                "model": model,
                "input": [{"role": "user", "content": prompt}],
                "reasoning": {"effort": "low"},
                "stream": False,
            },
            headers={
                "Authorization": f"Bearer {new_api_key()}",
                "Content-Type": "application/json",
            },
            timeout=8.0,
        )
    except Exception:  # noqa: BLE001
        return []
    if status >= 400 or not isinstance(body, dict):
        return []
    text = ""
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                text += str(part.get("text") or "")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except Exception:  # noqa: BLE001
        return []
    raw = parsed.get("q") if isinstance(parsed, dict) else None
    out: list[str] = []
    seen = {q}
    for row in raw if isinstance(raw, list) else []:
        s = str(row or "").strip()
        if s and s not in seen and len(s) <= 80:
            seen.add(s)
            out.append(s)
        if len(out) >= 2:
            break
    return out


def meili_configured() -> bool:
    return bool(meili_url() and meili_key())


def quote_filter_value(raw: str) -> str:
    return '"' + str(raw).replace("\\", "\\\\").replace('"', '\\"') + '"'


def tenant_filter(
    school_id: str,
    membership_id: str,
    *,
    include_school: bool = False,
) -> str:
    """Server-side tenant clause. Never take a filter string from the client.

    Personal (default): this school + this member + ``scope = member``.
    School checkbox: this school AND (``scope = school`` OR own member rows).
    """
    school = str(school_id or "").strip()
    member = str(membership_id or "").strip()
    if not _ID_SAFE.match(school) or not _ID_SAFE.match(member):
        raise ValueError("invalid tenant keys")
    school_q = quote_filter_value(school)
    member_q = quote_filter_value(member)
    if include_school:
        return (
            f"school_id = {school_q} AND "
            f'(scope = "school" OR (scope = "member" AND membership_id = {member_q}))'
        )
    return f"school_id = {school_q} AND membership_id = {member_q} AND scope = \"member\""


def _headers() -> dict[str, str]:
    key = meili_key()
    out = {"Content-Type": "application/json"}
    if key:
        out["Authorization"] = f"Bearer {key}"
    return out


def is_material(*, kind: str | None, title: str | None) -> bool:
    k = str(kind or "").strip().lower()
    name = str(title or "").strip().lower()
    if k in SKIP_KINDS:
        return False
    if k in MATERIAL_KINDS:
        return True
    return any(name.endswith(ext) for ext in MATERIAL_EXTS)


def _suffix_of(title: str) -> str:
    name = title or "file"
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def extract_index_text(
    *,
    title: str,
    kind: str,
    content: str | None,
    raw: bytes | None,
    stored_text: str | None = None,
) -> str:
    """Ledger UTF-8, Docling for pdf/docx, office_extract for xlsx/pptx/txt. No self-built parser.

    ``stored_text`` is a same-task ``kb_text`` sibling. Reindex uses ocr=False so
    scans would otherwise collapse to an empty layer and wipe the live index.
    """
    name = title or "file"
    suffix = _suffix_of(name)
    kept = (stored_text or "").strip()
    if suffix in TABLE_EXTRACT_EXT:
        data = raw
        if data is None and content and suffix != ".xlsx":
            data = content.encode("utf-8")
        if data:
            parsed = extract_office_text(filename=name, data=data)
            if parsed:
                return parsed[:MAX_TEXT]
        return (content or "")[:MAX_TEXT]
    if content and suffix not in PARSE_EXT:
        return content[:MAX_TEXT]
    if suffix in PARSE_EXT and raw:
        parsed = parse_office_bytes(filename=name, data=raw) or ""
        if kept and len(kept) > len(parsed.strip()):
            return kept[:MAX_TEXT]
        if parsed:
            return parsed[:MAX_TEXT]
        return (content or kept)[:MAX_TEXT]
    if suffix in PARSE_EXT and kept:
        return kept[:MAX_TEXT]
    if suffix in OFFICE_EXTRACT_EXT and raw:
        parsed = extract_office_text(filename=name, data=raw)
        if parsed:
            return parsed[:MAX_TEXT]
    return (content or kept)[:MAX_TEXT]


def extract_office_text(*, filename: str, data: bytes) -> str:
    """Thin call into app.office_extract (xlsx/pptx/txt). Not a self-built parser."""
    try:
        from app.office_extract import extract_office
    except Exception:  # noqa: BLE001
        import sys
        from pathlib import Path

        api = Path(__file__).resolve().parents[2] / "api"
        if str(api) not in sys.path:
            sys.path.insert(0, str(api))
        try:
            from app.office_extract import extract_office
        except Exception as exc:  # noqa: BLE001
            logger.warning("office_extract unavailable: %s", type(exc).__name__)
            return ""
    try:
        out = extract_office(filename, data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("office_extract failed: %s", type(exc).__name__)
        return ""
    if not isinstance(out, dict) or out.get("status") != "ok":
        return ""
    return str(out.get("text") or "").strip()


def parse_office_bytes(*, filename: str, data: bytes) -> str:
    """Thin call into packages/field-kb-ingest (Docling / RapidOCR)."""
    import sys
    from pathlib import Path

    pkg = Path("/app/packages/field-kb-ingest")
    if not pkg.exists():
        pkg = Path(__file__).resolve().parents[3] / "packages" / "field-kb-ingest"
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))
    try:
        from ingest import ingest_bytes
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - import surface
        logger.warning("field-kb-ingest unavailable: %s", type(exc).__name__)
        return ""
    try:
        # Projection / rebuild path: text layers only. OCR is an explicit
        # /v1/kb/ingest decision, never a side effect of reindex or upload.
        result = ingest_bytes(filename=filename, data=data, title=filename, ocr=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("field-kb-ingest failed: %s", type(exc).__name__)
        return ""
    if not result.get("ok"):
        return ""
    # Prefer full markdown so page breaks (\\x0c) survive for the chunker.
    md = str(result.get("markdown") or "").strip()
    if md:
        return md[:MAX_TEXT]
    parts = [str(row.get("excerpt") or "") for row in (result.get("slices") or [])]
    return "\n".join(p for p in parts if p).strip()[:MAX_TEXT]


def render_pdf_page_pngs(data: bytes, *, max_pages: int = 32) -> list[bytes]:
    """Thin call into field-kb-ingest pypdfium2 raster. Not a Pico PDF kernel."""
    import sys
    from pathlib import Path

    pkg = Path("/app/packages/field-kb-ingest")
    if not pkg.exists():
        pkg = Path(__file__).resolve().parents[3] / "packages" / "field-kb-ingest"
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))
    try:
        from ingest import render_pdf_page_pngs as _render
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf page render unavailable: %s", type(exc).__name__)
        return []
    try:
        return list(_render(data, max_pages=max_pages) or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf page render failed: %s", type(exc).__name__)
        return []


def is_noise_title(title: str) -> bool:
    name = (title or "").strip()
    if name in NOISE_TITLES:
        return True
    return any(name.startswith(n) for n in NOISE_TITLES)


def is_lab_school(school_id: str) -> bool:
    """True for unit-test / probe tenants that must not occupy the live index."""
    sid = (school_id or "").strip()
    if not sid:
        return False
    if sid in LAB_SCHOOLS:
        return True
    return sid.startswith(LAB_SCHOOL_PREFIXES)


def lab_index_blocked(school_id: str) -> bool:
    """Production must not ingest/project lab tenants. Development tests still use school-a."""
    if not is_lab_school(school_id):
        return False
    env = (os.environ.get("PICO_ENV") or "").strip().lower()
    return env in {"production", "prod"}


def is_title_only_stub(*, title: str, text: str) -> bool:
    """Legacy OLE that never extracted — index was just the filename."""
    suffix = _suffix_of(title)
    if suffix not in TITLE_ONLY_EXTS:
        return False
    body = (text or "").strip()
    heading = (title or "").strip()
    return len(body) <= max(len(heading), 24)


def document_from_artifact(
    *,
    artifact_id: str,
    title: str,
    text: str,
    school_id: str,
    membership_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """One-row fallback (tests / tiny docs). Live projection uses chunks."""
    return {
        "chunk_id": chunk_doc_id(artifact_id, 0),
        "artifact_id": artifact_id,
        "material_id": artifact_id,
        "title": (title or "")[:512],
        "heading": (title or "")[:120],
        "page": None,
        "text": (text or "")[:MAX_TEXT],
        "parent_text": (text or "")[:2000],
        "seq": 0,
        "scope": "member",
        "school_id": school_id,
        "membership_id": membership_id,
        "created_at": created_at or "",
    }


def documents_from_text(
    *,
    artifact_id: str,
    title: str,
    text: str,
    school_id: str,
    membership_id: str,
    created_at: str | None = None,
    scope: str = "member",
) -> list[dict[str, Any]]:
    from pico_orchestrator.kb_chunker import chunk_text

    chunks = chunk_text(text, title=title)
    if not chunks:
        if not (text or title):
            return []
        return [
            document_from_artifact(
                artifact_id=artifact_id,
                title=title,
                text=text or title,
                school_id=school_id,
                membership_id=membership_id,
                created_at=created_at,
            )
        ]
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        out.append(
            {
                "chunk_id": chunk_doc_id(artifact_id, chunk.seq),
                "artifact_id": artifact_id,
                "material_id": artifact_id,
                "title": (title or "")[:512],
                "heading": (chunk.heading or title or "")[:120],
                "page": chunk.page,
                "text": chunk.text,
                "parent_text": chunk.parent_text,
                "seq": chunk.seq,
                "scope": scope,
                "school_id": school_id,
                "membership_id": membership_id,
                "created_at": created_at or "",
            }
        )
    return out


class MeiliIndex:
    def __init__(self, client: HttpClient | None = None) -> None:
        self._http = client or HttpxClient()

    def _call(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        timeout: float = 8.0,
    ) -> tuple[int, Any]:
        url = f"{meili_url()}{path}"
        return self._http.request(
            method, url, json=payload, headers=_headers(), timeout=timeout
        )

    def ping(self) -> bool:
        if not meili_configured():
            return False
        try:
            status, _body = self._call("GET", "/health", timeout=2.0)
            return status == 200
        except Exception:  # noqa: BLE001
            return False

    def live_embedder_armed(self) -> bool:
        """True only when Meili index actually has a ``default`` REST embedder."""
        return bool(self.live_embedder_url())

    def live_embedder_url(self) -> str:
        try:
            status, body = self._call("GET", f"/indexes/{INDEX}/settings/embedders", timeout=3.0)
        except Exception:  # noqa: BLE001
            return ""
        if status >= 400 or not isinstance(body, dict):
            return ""
        default = body.get("default")
        if not isinstance(default, dict):
            return ""
        return str(default.get("url") or "")

    def embedder_is_new_api(self) -> bool:
        spec = new_api_embedder_spec()
        if not spec:
            return False
        url = self.live_embedder_url()
        if not url or any(marker in url.lower() for marker in _VENDOR_EMBED_MARKERS):
            return False
        return url == str(spec.get("url") or "")

    def _primary_key(self) -> str | None:
        try:
            status, body = self._call("GET", f"/indexes/{INDEX}")
        except Exception:  # noqa: BLE001
            return None
        if status == 404:
            return None
        if status >= 400 or not isinstance(body, dict):
            return ""
        return str(body.get("primaryKey") or "")

    def ensure(self, *, force: bool = False) -> None:
        spec = new_api_embedder_spec()
        cache_key = f"{meili_url()}|{INDEX}|chunk-v2|{spec.get('url') if spec else 'off'}"
        if not force and _ENSURE_CACHE.get(cache_key):
            return
        pk = self._primary_key()
        if pk is None:
            self._accepted(
                "POST",
                "/indexes",
                {"uid": INDEX, "primaryKey": PRIMARY_KEY},
            )
            _ENSURE_CACHE.pop(cache_key, None)
        elif pk != PRIMARY_KEY:
            logger.warning("meili index pk %s → %s, recreating", pk, PRIMARY_KEY)
            self._accepted("DELETE", f"/indexes/{INDEX}")
            self._accepted(
                "POST",
                "/indexes",
                {"uid": INDEX, "primaryKey": PRIMARY_KEY},
            )
            _ENSURE_CACHE.pop(cache_key, None)
        want_embedders = {"default": spec} if spec else None
        # Skip PATCH when index already matches (stops reindex flooding settingsUpdate).
        if not force and self._settings_match(want_embedders):
            _ENSURE_CACHE[cache_key] = True
            return
        # Searchable-only fix must not resend embedders: that re-embeds the whole
        # index and burns a dead query-embed channel.
        if (
            not force
            and self._embedder_url_match(want_embedders)
            and not self._searchable_match()
        ):
            self._accepted(
                "PATCH",
                f"/indexes/{INDEX}/settings",
                {"searchableAttributes": SEARCHABLE, "displayedAttributes": DISPLAYED},
                timeout=20.0,
                wait_s=45.0,
            )
            _ENSURE_CACHE[cache_key] = True
            return
        settings: dict[str, Any] = {
            "filterableAttributes": FILTERABLE,
            "searchableAttributes": SEARCHABLE,
            "displayedAttributes": DISPLAYED,
            "embedders": {"default": spec} if spec else {"default": None},
        }
        self._accepted("PATCH", f"/indexes/{INDEX}/settings", settings, timeout=20.0, wait_s=90.0)
        if (spec and self.embedder_is_new_api()) or (not spec and not self.live_embedder_armed()):
            _ENSURE_CACHE[cache_key] = True
        else:
            _ENSURE_CACHE.pop(cache_key, None)

    def _settings_body(self) -> dict[str, Any] | None:
        try:
            status, body = self._call("GET", f"/indexes/{INDEX}/settings", timeout=3.0)
        except Exception:  # noqa: BLE001
            return None
        if status >= 400 or not isinstance(body, dict):
            return None
        return body

    def _searchable_match(self, body: dict[str, Any] | None = None) -> bool:
        live = body if body is not None else self._settings_body()
        if not live:
            return False
        return list(live.get("searchableAttributes") or []) == list(SEARCHABLE)

    def _embedder_url_match(self, want_embedders: dict[str, Any] | None) -> bool:
        live = self._settings_body()
        if not live:
            return False
        if set(live.get("filterableAttributes") or []) != set(FILTERABLE):
            return False
        emb = live.get("embedders") if isinstance(live.get("embedders"), dict) else {}
        default = emb.get("default") if isinstance(emb, dict) else None
        if want_embedders:
            if not isinstance(default, dict):
                return False
            want_default = want_embedders.get("default") or {}
            if str(default.get("url") or "") != str(want_default.get("url") or ""):
                return False
            if str(default.get("documentTemplate") or "") != str(
                want_default.get("documentTemplate") or ""
            ):
                return False
            want_max = want_default.get("documentTemplateMaxBytes")
            if want_max is None:
                return True
            live_max = default.get("documentTemplateMaxBytes")
            if live_max is None:
                live_max = 400
            return int(live_max) == int(want_max)
        return not isinstance(default, dict)

    def _settings_match(self, want_embedders: dict[str, Any] | None) -> bool:
        live = self._settings_body()
        if not live:
            return False
        return self._embedder_url_match(want_embedders) and self._searchable_match(live)

    def _accepted(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        timeout: float = 8.0,
        wait_s: float = 45.0,
    ) -> Any:
        """POST/PATCH/DELETE that must land. 202 without a succeeded task is fake-green."""
        status, body = self._call(method, path, payload, timeout=timeout)
        if status >= 400:
            raise RuntimeError(f"meili {method} {path} http {status}")
        if isinstance(body, dict) and body.get("taskUid") is not None:
            self._wait_task(int(body["taskUid"]), timeout_s=wait_s)
        return body

    def _wait_task(self, task_uid: int, *, timeout_s: float = 45.0) -> None:
        import time

        deadline = time.monotonic() + max(1.0, timeout_s)
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status, body = self._call("GET", f"/tasks/{task_uid}", timeout=3.0)
            if status >= 400 or not isinstance(body, dict):
                raise RuntimeError(f"meili task {task_uid} http {status}")
            last = body
            state = str(body.get("status") or "")
            if state == "succeeded":
                return
            if state in {"failed", "canceled"}:
                err = body.get("error") if isinstance(body.get("error"), dict) else {}
                code = str(err.get("code") or state)
                raise RuntimeError(f"meili task {task_uid} {state}: {code}")
            time.sleep(0.2)
        raise RuntimeError(f"meili task {task_uid} timeout ({last.get('status') or 'unknown'})")

    def upsert(self, doc: dict[str, Any]) -> None:
        if not doc.get("chunk_id") and not doc.get("artifact_id"):
            return
        self.ensure()
        if not doc.get("chunk_id") and doc.get("artifact_id"):
            doc = {**doc, "chunk_id": chunk_doc_id(str(doc["artifact_id"]), 0)}
        self._accepted("POST", f"/indexes/{INDEX}/documents", [doc], timeout=20.0)

    def upsert_many(self, docs: list[dict[str, Any]]) -> None:
        rows = [d for d in docs if d.get("chunk_id")]
        if not rows:
            return
        self.ensure()
        self._accepted("POST", f"/indexes/{INDEX}/documents", rows, timeout=30.0, wait_s=60.0)

    def delete(self, artifact_id: str) -> None:
        aid = str(artifact_id or "").strip()
        if not aid:
            return
        self.ensure()
        self._accepted(
            "POST",
            f"/indexes/{INDEX}/documents/delete",
            {"filter": f"artifact_id = {quote_filter_value(aid)}"},
            timeout=20.0,
        )

    def search(
        self,
        query: str,
        *,
        school_id: str,
        membership_id: str,
        limit: int,
        include_school: bool = False,
    ) -> dict[str, Any]:
        clause = tenant_filter(school_id, membership_id, include_school=include_school)
        want = max(1, int(limit))
        spec = new_api_embedder_spec()
        # Only send hybrid when query embed works. Leftover document vectors + 1113
        # made Meili retry the embedder five times and still return keyword.
        use_hybrid = self.embedder_is_new_api() and embed_query_ok()
        queries = [query]
        for extra in expand_search_queries(query):
            if extra not in queries:
                queries.append(extra)
        fetch = kb_search_fetch() if (use_hybrid or spec or len(queries) > 1) else min(48, max(want * 8, want))
        hybrid_rows: list[Any] = []
        title_rows: list[Any] = []
        seen_hybrid: set[str] = set()
        seen_title: set[str] = set()
        for q in queries[:3]:
            body: dict[str, Any] = {
                "q": q,
                "filter": clause,
                "limit": fetch,
                "attributesToRetrieve": DISPLAYED,
                "attributesToHighlight": ["title", "heading", "text"],
                "highlightPreTag": "",
                "highlightPostTag": "",
            }
            if use_hybrid:
                body["hybrid"] = {
                    "semanticRatio": kb_hybrid_ratio(),
                    "embedder": "default",
                }
            status, payload = self._call("POST", f"/indexes/{INDEX}/search", body, timeout=12.0)
            if status >= 400:
                raise RuntimeError(f"meili search http {status}")
            raw = payload.get("hits") if isinstance(payload, dict) else None
            for row in raw if isinstance(raw, list) else []:
                if not isinstance(row, dict):
                    continue
                cid = str(row.get("chunk_id") or row.get("artifact_id") or "")
                if not cid or cid in seen_hybrid:
                    continue
                seen_hybrid.add(cid)
                hybrid_rows.append(row)
        unique_files = {
            str(row.get("artifact_id") or row.get("material_id") or "").strip()
            for row in hybrid_rows
        }
        unique_files.discard("")
        # Title-only hits sit at the tail of the chunk pool. After file-collapse
        # they never enter top-N when hybrid already filled N unique files, but
        # the extra Meili round-trip still costs p95. Only probe titles when
        # the returned file list would otherwise be short.
        if len(unique_files) < want:
            for q in queries[:3]:
                tstatus, tpayload = self._call(
                    "POST",
                    f"/indexes/{INDEX}/search",
                    {
                        "q": q,
                        "filter": clause,
                        "limit": TITLE_HIT_CAP,
                        "attributesToRetrieve": DISPLAYED,
                        "attributesToSearchOn": ["title"],
                    },
                    timeout=12.0,
                )
                traw = tpayload.get("hits") if isinstance(tpayload, dict) and tstatus < 400 else None
                for row in traw if isinstance(traw, list) else []:
                    if not isinstance(row, dict):
                        continue
                    cid = str(row.get("chunk_id") or row.get("artifact_id") or "")
                    if not cid or cid in seen_title:
                        continue
                    seen_title.add(cid)
                    title_rows.append(row)
        pool = merge_hybrid_and_title_hits(
            hybrid_rows, title_rows, pool=kb_rerank_pool(), title_cap=TITLE_HIT_CAP
        )
        reranked = False
        rerank_skip = "off"
        if spec and pool and kb_rerank_enabled():
            texts = []
            for row in pool:
                head = " ".join(
                    str(x) for x in (row.get("title"), row.get("heading")) if x
                )
                texts.append((head + "\n" + str(row.get("text") or ""))[:2000])
            order = rerank_documents(query, texts)
            if order:
                pool = _apply_rerank_order(pool, order)
                reranked = True
                rerank_skip = ""
            else:
                rerank_skip = "flat"
        hits = take_passage_hits(pool, want)
        return {
            "hits": hits,
            "hybrid": use_hybrid,
            "reranked": reranked,
            "rerank_skip": rerank_skip,
            "expanded": max(0, len(queries) - 1),
            "filter": clause,
            "include_school": include_school,
        }

    def count(
        self,
        *,
        school_id: str,
        artifact_id: str,
        scope: str = "school",
    ) -> int:
        school = str(school_id or "").strip()
        aid = str(artifact_id or "").strip()
        sc = str(scope or "").strip()
        if not _ID_SAFE.match(school) or not aid or sc not in {"school", "member"}:
            return 0
        clause = (
            f"school_id = {quote_filter_value(school)} AND "
            f"artifact_id = {quote_filter_value(aid)} AND "
            f"scope = {quote_filter_value(sc)}"
        )
        status, payload = self._call(
            "POST",
            f"/indexes/{INDEX}/search",
            {"q": "", "filter": clause, "limit": 1},
            timeout=8.0,
        )
        if status >= 400 or not isinstance(payload, dict):
            raise RuntimeError(f"meili count http {status}")
        for key in ("estimatedTotalHits", "totalHits"):
            if payload.get(key) is not None:
                return int(payload[key])
        hits = payload.get("hits")
        return len(hits) if isinstance(hits, list) else 0


def upsert_material(doc: dict[str, Any], *, client: HttpClient | None = None) -> bool:
    if not meili_configured():
        return False
    try:
        MeiliIndex(client).upsert(doc)
        return True
    except Exception as exc:  # noqa: BLE001 — projection must not block ledger writes
        logger.warning("meili upsert failed: %s", type(exc).__name__)
        return False


def upsert_documents(
    docs: list[dict[str, Any]],
    *,
    client: HttpClient | None = None,
    replace_artifact: bool = True,
) -> bool:
    if not meili_configured() or not docs:
        return False
    try:
        idx = MeiliIndex(client)
        aid = str(docs[0].get("artifact_id") or "").strip()
        if replace_artifact and aid:
            idx.delete(aid)
        idx.upsert_many(docs)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("meili upsert_many failed: %s", type(exc).__name__)
        return False


def delete_material(artifact_id: str, *, client: HttpClient | None = None) -> None:
    if not meili_configured():
        return
    try:
        MeiliIndex(client).delete(artifact_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("meili delete failed: %s", type(exc).__name__)


def search_materials(
    query: str,
    *,
    school_id: str,
    membership_id: str,
    limit: int,
    include_school: bool = False,
    client: HttpClient | None = None,
) -> dict[str, Any]:
    """Search with server-injected tenant filter. Raises if Meili is down."""
    idx = MeiliIndex(client)
    if not meili_configured() or not idx.ping():
        raise RuntimeError("meili unavailable")
    try:
        idx.ensure()
    except Exception as exc:  # noqa: BLE001 — search still works on leftover keyword
        logger.warning("meili ensure before search failed: %s", type(exc).__name__)
    return idx.search(
        query,
        school_id=school_id,
        membership_id=membership_id,
        limit=limit,
        include_school=include_school,
    )


def count_material(
    artifact_id: str,
    *,
    school_id: str,
    scope: str = "school",
    client: HttpClient | None = None,
) -> int:
    idx = MeiliIndex(client)
    if not meili_configured() or not idx.ping():
        raise RuntimeError("meili unavailable")
    return idx.count(school_id=school_id, artifact_id=artifact_id, scope=scope)


def _hit_chunk_id(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("chunk_id") or row.get("artifact_id") or "")


def _hit_artifact_id(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("artifact_id") or row.get("material_id") or "").strip()


def title_only_hits(
    hybrid: list[Any],
    title: list[Any],
    *,
    cap: int = TITLE_HIT_CAP,
) -> list[Any]:
    """First title chunk per file that hybrid never retrieved. Not extra chunks of a hit file."""
    hy_aids = {_hit_artifact_id(row) for row in hybrid if _hit_artifact_id(row)}
    out: list[Any] = []
    seen: set[str] = set()
    for row in title:
        aid = _hit_artifact_id(row)
        if not aid or aid in hy_aids or aid in seen:
            continue
        seen.add(aid)
        out.append(row)
        if len(out) >= max(0, int(cap)):
            break
    return out


def merge_hybrid_and_title_hits(
    hybrid: list[Any],
    title: list[Any],
    *,
    pool: int,
    title_cap: int = TITLE_HIT_CAP,
) -> list[Any]:
    """Hybrid rank first. Title-only files take leftover tail slots.

    Prepending title chunks (live #1024) made collapse return a header
    and let other titles occupy the top five files. Title reserve is
    only for files hybrid missed, and only after hybrid order.
    """
    want = max(1, int(pool))
    reserved = title_only_hits(hybrid, title, cap=min(int(title_cap), want))
    budget = max(1, want - len(reserved)) if reserved else want
    out: list[Any] = []
    seen: set[str] = set()
    for row in hybrid:
        cid = _hit_chunk_id(row)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(row)
        if len(out) >= budget:
            break
    for row in reserved:
        cid = _hit_chunk_id(row)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(row)
        if len(out) >= want:
            break
    return out[:want]


def take_passage_hits(hits: list[Any], limit: int) -> list[dict[str, Any]]:
    """Top passages. Same file may occupy more than one slot."""
    want = max(1, int(limit))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in hits:
        if not isinstance(row, dict):
            continue
        cid = _hit_chunk_id(row)
        if cid:
            if cid in seen:
                continue
            seen.add(cid)
        out.append(row)
        if len(out) >= want:
            break
    return out


def collapse_hits_by_artifact(hits: list[Any], limit: int) -> list[dict[str, Any]]:
    """One chunk per ledger file. Kept for tests; live search returns passages."""
    want = max(1, int(limit))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in hits:
        if not isinstance(row, dict):
            continue
        aid = str(row.get("artifact_id") or row.get("material_id") or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        out.append(row)
        if len(out) >= want:
            break
    return out


def material_chunk_docs(
    principal: Any,
    *,
    artifact_id: str,
    title: str,
    kind: str,
    content: str | bytes | None,
    created_at: str | None = None,
    stored_text: str | None = None,
) -> list[dict[str, Any]]:
    if not is_material(kind=kind, title=title):
        return []
    if is_noise_title(title):
        return []
    text = ""
    raw: bytes | None = None
    if isinstance(content, bytes):
        raw = content
    elif isinstance(content, str):
        text = content
    text = extract_index_text(
        title=title,
        kind=kind,
        content=text or None,
        raw=raw,
        stored_text=stored_text,
    )
    suffix = _suffix_of(title)
    needs_body = suffix in PARSE_EXT or suffix in OFFICE_EXTRACT_EXT
    if needs_body and not str(text or "").strip():
        return []
    if not text and not title:
        return []
    if is_title_only_stub(title=title, text=text or ""):
        return []
    return documents_from_text(
        artifact_id=artifact_id,
        title=title,
        text=text or title,
        school_id=str(getattr(principal, "school_id", "") or ""),
        membership_id=str(getattr(principal, "membership_id", "") or ""),
        created_at=created_at,
    )


def project_material_artifact(
    principal: Any,
    *,
    artifact_id: str,
    title: str,
    kind: str,
    content: str | bytes | None,
    created_at: str | None = None,
    client: HttpClient | None = None,
) -> bool:
    if lab_index_blocked(str(getattr(principal, "school_id", "") or "")):
        return False
    docs = material_chunk_docs(
        principal,
        artifact_id=artifact_id,
        title=title,
        kind=kind,
        content=content,
        created_at=created_at,
    )
    if not docs:
        return False
    return upsert_documents(docs, client=client)


def health_fields() -> dict[str, Any]:
    """Chunk mount. Hybrid only when the live Meili embedder URL is New API."""
    configured = meili_configured()
    reachable = False
    idx: MeiliIndex | None = None
    if configured:
        try:
            idx = MeiliIndex()
            reachable = idx.ping()
        except Exception:  # noqa: BLE001
            reachable = False
            idx = None
    embedder = False
    provider = ""
    key_present = False
    query_ok = False
    if idx is not None and reachable:
        try:
            check = getattr(idx, "embedder_is_new_api", None)
            if callable(check) and check():
                query_ok = embed_query_ok()
                embedder = query_ok
                provider = "new-api"
                key_present = bool(new_api_key())
        except Exception:  # noqa: BLE001
            embedder = False
    if embedder:
        mode = "hybrid"
    elif configured and reachable:
        mode = "keyword"
    elif configured:
        mode = "down"
    else:
        mode = "off"
    return {
        "meili_configured": configured,
        "meili_reachable": reachable,
        "meili_embedder": embedder,
        "meili_embedder_provider": provider,
        "meili_embedder_key_present": key_present,
        "meili_embedder_query_ok": query_ok,
        "kb_mode": mode,
    }
