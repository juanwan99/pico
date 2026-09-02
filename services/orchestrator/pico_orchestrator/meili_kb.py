"""Meilisearch projection of membership materials. Ledger is the only source of truth."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Protocol
from urllib.parse import quote

logger = logging.getLogger(__name__)

INDEX = "pico_materials"
PRIMARY_KEY = "artifact_id"
FILTERABLE = ["school_id", "membership_id"]
SEARCHABLE = ["title", "text"]
DISPLAYED = ["artifact_id", "title", "text", "school_id", "membership_id", "created_at"]
MAX_TEXT = 20_000
SEMANTIC_RATIO = 0.5
# Prefer SiliconFlow bge-m3 when key present; else Zhipu embedding-3 (same REST
# shape Meili expects). Never invent a local vector kernel. Images stay Zhipu
# glm-image only — SF key here is embeddings-only.
SF_EMBED_MODEL = "BAAI/bge-m3"
SF_EMBED_URL = "https://api.siliconflow.cn/v1/embeddings"
ZHIPU_EMBED_MODEL = "embedding-3"
ZHIPU_EMBED_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
ZHIPU_EMBED_DIMS = 1024
# Back-compat aliases (tests / older imports).
EMBED_MODEL = SF_EMBED_MODEL
EMBED_URL = SF_EMBED_URL

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
OFFICE_EXTRACT_EXT = frozenset({".xlsx", ".pptx", ".txt"})
MATERIAL_EXTS = frozenset({".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".json"})
_ID_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
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


def siliconflow_embed_key() -> str:
    return (os.environ.get("SILICONFLOW_API_KEY") or "").strip()


def zhipu_embed_key() -> str:
    return (os.environ.get("ZHIPU_API_KEY") or "").strip()


def embedder_provider() -> str | None:
    """Which external embed REST Meili will call. SF preferred; Zhipu fallback."""
    if siliconflow_embed_key():
        return "siliconflow"
    if zhipu_embed_key():
        return "zhipu"
    return None


def embedding_api_key() -> str:
    """Nonempty when hybrid can arm. Prefer SF; else Zhipu (prod has Zhipu)."""
    return siliconflow_embed_key() or zhipu_embed_key()


def meili_configured() -> bool:
    return bool(meili_url() and meili_key())


def quote_filter_value(raw: str) -> str:
    return '"' + str(raw).replace("\\", "\\\\").replace('"', '\\"') + '"'


def tenant_filter(school_id: str, membership_id: str) -> str:
    """Server-side tenant clause. Never take a filter string from the client."""
    school = str(school_id or "").strip()
    member = str(membership_id or "").strip()
    if not _ID_SAFE.match(school) or not _ID_SAFE.match(member):
        raise ValueError("invalid tenant keys")
    return f"school_id = {quote_filter_value(school)} AND membership_id = {quote_filter_value(member)}"


def _headers() -> dict[str, str]:
    key = meili_key()
    out = {"Content-Type": "application/json"}
    if key:
        out["Authorization"] = f"Bearer {key}"
    return out


def _embedder_settings() -> dict[str, Any] | None:
    """Meili REST embedder config, or None → keyword-only search."""
    provider = embedder_provider()
    if provider == "siliconflow":
        return {
            "default": {
                "source": "rest",
                "url": SF_EMBED_URL,
                "apiKey": siliconflow_embed_key(),
                "documentTemplate": "{{doc.title}}\n{{doc.text}}",
                "request": {"model": SF_EMBED_MODEL, "input": ["{{text}}"]},
                "response": {"data": [{"embedding": "{{embedding}}"}]},
            }
        }
    if provider == "zhipu":
        return {
            "default": {
                "source": "rest",
                "url": ZHIPU_EMBED_URL,
                "apiKey": zhipu_embed_key(),
                "documentTemplate": "{{doc.title}}\n{{doc.text}}",
                "request": {
                    "model": ZHIPU_EMBED_MODEL,
                    "input": ["{{text}}"],
                    "dimensions": ZHIPU_EMBED_DIMS,
                },
                "response": {"data": [{"embedding": "{{embedding}}"}]},
            }
        }
    return None


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


def extract_index_text(*, title: str, kind: str, content: str | None, raw: bytes | None) -> str:
    """Ledger UTF-8, Docling for pdf/docx, office_extract for xlsx/pptx/txt. No self-built parser."""
    name = title or "file"
    suffix = _suffix_of(name)
    if content and suffix not in PARSE_EXT:
        return content[:MAX_TEXT]
    if suffix in PARSE_EXT and raw:
        parsed = parse_office_bytes(filename=name, data=raw)
        if parsed:
            return parsed[:MAX_TEXT]
        return (content or "")[:MAX_TEXT]
    if suffix in OFFICE_EXTRACT_EXT and raw:
        parsed = extract_office_text(filename=name, data=raw)
        if parsed:
            return parsed[:MAX_TEXT]
    return (content or "")[:MAX_TEXT]


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
        result = ingest_bytes(filename=filename, data=data, title=filename)
    except Exception as exc:  # noqa: BLE001
        logger.warning("field-kb-ingest failed: %s", type(exc).__name__)
        return ""
    if not result.get("ok"):
        return ""
    parts = [str(row.get("excerpt") or "") for row in (result.get("slices") or [])]
    return "\n".join(p for p in parts if p).strip()


def render_pdf_page_pngs(data: bytes, *, max_pages: int = 8) -> list[bytes]:
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


def document_from_artifact(
    *,
    artifact_id: str,
    title: str,
    text: str,
    school_id: str,
    membership_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "title": (title or "")[:512],
        "text": (text or "")[:MAX_TEXT],
        "school_id": school_id,
        "membership_id": membership_id,
        "created_at": created_at or "",
    }


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
        try:
            status, body = self._call("GET", f"/indexes/{INDEX}/settings/embedders", timeout=3.0)
        except Exception:  # noqa: BLE001
            return False
        if status >= 400 or not isinstance(body, dict):
            return False
        default = body.get("default")
        return isinstance(default, dict) and bool(default.get("source") or default.get("url"))

    def ensure(self, *, force: bool = False) -> None:
        cache_key = f"{meili_url()}|{INDEX}|{embedder_provider() or 'none'}"
        if not force and _ENSURE_CACHE.get(cache_key):
            return
        status, _ = self._call("GET", f"/indexes/{INDEX}")
        if status == 404:
            self._call(
                "POST",
                "/indexes",
                {"uid": INDEX, "primaryKey": PRIMARY_KEY},
            )
            _ENSURE_CACHE.pop(cache_key, None)
        want_embedders = _embedder_settings()
        # Skip PATCH when index already matches (stops reindex flooding settingsUpdate).
        if not force and self._settings_match(want_embedders):
            _ENSURE_CACHE[cache_key] = True
            return
        settings: dict[str, Any] = {
            "filterableAttributes": FILTERABLE,
            "searchableAttributes": SEARCHABLE,
            "displayedAttributes": DISPLAYED,
        }
        if want_embedders:
            settings["embedders"] = want_embedders
        patch_status, patch_body = self._call(
            "PATCH", f"/indexes/{INDEX}/settings", settings, timeout=20.0
        )
        if patch_status < 400 and isinstance(patch_body, dict) and patch_body.get("taskUid") is not None:
            self._wait_task(int(patch_body["taskUid"]), timeout_s=45.0)
        if want_embedders:
            # Only cache success when Meili really armed the embedder.
            if self.live_embedder_armed():
                _ENSURE_CACHE[cache_key] = True
            else:
                _ENSURE_CACHE.pop(cache_key, None)
        else:
            _ENSURE_CACHE[cache_key] = True

    def _settings_match(self, want_embedders: dict[str, Any] | None) -> bool:
        try:
            status, body = self._call("GET", f"/indexes/{INDEX}/settings", timeout=3.0)
        except Exception:  # noqa: BLE001
            return False
        if status >= 400 or not isinstance(body, dict):
            return False
        if list(body.get("filterableAttributes") or []) != list(FILTERABLE):
            return False
        if want_embedders:
            live = body.get("embedders") if isinstance(body.get("embedders"), dict) else {}
            default = live.get("default") if isinstance(live, dict) else None
            if not isinstance(default, dict):
                return False
            want_default = want_embedders.get("default") or {}
            return str(default.get("url") or "") == str(want_default.get("url") or "")
        live = body.get("embedders") if isinstance(body.get("embedders"), dict) else {}
        return not live

    def _wait_task(self, task_uid: int, *, timeout_s: float = 45.0) -> None:
        import time

        deadline = time.monotonic() + max(1.0, timeout_s)
        while time.monotonic() < deadline:
            try:
                status, body = self._call("GET", f"/tasks/{task_uid}", timeout=3.0)
            except Exception:  # noqa: BLE001
                return
            if status >= 400 or not isinstance(body, dict):
                return
            state = str(body.get("status") or "")
            if state in {"succeeded", "failed", "canceled"}:
                if state != "succeeded":
                    logger.warning("meili settings task %s: %s", task_uid, state)
                return
            time.sleep(0.4)

    def upsert(self, doc: dict[str, Any]) -> None:
        if not doc.get("artifact_id"):
            return
        self.ensure()
        self._call("POST", f"/indexes/{INDEX}/documents", [doc], timeout=20.0)

    def delete(self, artifact_id: str) -> None:
        aid = str(artifact_id or "").strip()
        if not aid:
            return
        self._call("DELETE", f"/indexes/{INDEX}/documents/{quote(aid, safe='')}")

    def search(
        self,
        query: str,
        *,
        school_id: str,
        membership_id: str,
        limit: int,
    ) -> dict[str, Any]:
        clause = tenant_filter(school_id, membership_id)
        body: dict[str, Any] = {
            "q": query,
            "filter": clause,
            "limit": limit,
            "attributesToRetrieve": DISPLAYED,
            "attributesToHighlight": ["title", "text"],
            "highlightPreTag": "",
            "highlightPostTag": "",
        }
        want_hybrid = bool(_embedder_settings()) and self.live_embedder_armed()
        if want_hybrid:
            body["hybrid"] = {"semanticRatio": SEMANTIC_RATIO, "embedder": "default"}
        status, payload = self._call("POST", f"/indexes/{INDEX}/search", body, timeout=12.0)
        # Embedder key present but index not armed yet → honest keyword fallback.
        if status >= 400 and body.get("hybrid"):
            body.pop("hybrid", None)
            status, payload = self._call("POST", f"/indexes/{INDEX}/search", body, timeout=12.0)
        if status >= 400:
            raise RuntimeError(f"meili search http {status}")
        hits = payload.get("hits") if isinstance(payload, dict) else None
        return {
            "hits": hits if isinstance(hits, list) else [],
            "hybrid": bool(body.get("hybrid")),
            "filter": clause,
        }


def upsert_material(doc: dict[str, Any], *, client: HttpClient | None = None) -> bool:
    if not meili_configured():
        return False
    try:
        MeiliIndex(client).upsert(doc)
        return True
    except Exception as exc:  # noqa: BLE001 — projection must not block ledger writes
        logger.warning("meili upsert failed: %s", type(exc).__name__)
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
    client: HttpClient | None = None,
) -> dict[str, Any]:
    """Search with server-injected tenant filter. Raises if Meili is down."""
    idx = MeiliIndex(client)
    if not meili_configured() or not idx.ping():
        raise RuntimeError("meili unavailable")
    return idx.search(query, school_id=school_id, membership_id=membership_id, limit=limit)


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
    if not is_material(kind=kind, title=title):
        return False
    text = ""
    raw: bytes | None = None
    if isinstance(content, bytes):
        raw = content
    elif isinstance(content, str):
        text = content
    text = extract_index_text(title=title, kind=kind, content=text or None, raw=raw)
    suffix = _suffix_of(title)
    needs_body = suffix in PARSE_EXT or suffix in OFFICE_EXTRACT_EXT
    if needs_body and not str(text or "").strip():
        # Empty Docling / office_extract: do not index title-only (no fake green).
        return False
    if not text and not title:
        return False
    doc = document_from_artifact(
        artifact_id=artifact_id,
        title=title,
        text=text or title,
        school_id=str(getattr(principal, "school_id", "") or ""),
        membership_id=str(getattr(principal, "membership_id", "") or ""),
        created_at=created_at,
    )
    return upsert_material(doc, client=client)


def health_fields() -> dict[str, Any]:
    """Honest Meili tier. hybrid only when index embedder is live; never key-only fake."""
    configured = meili_configured()
    reachable = False
    live_embedder = False
    if configured:
        try:
            idx = MeiliIndex()
            reachable = idx.ping()
            if reachable:
                live_embedder = idx.live_embedder_armed()
        except Exception:  # noqa: BLE001
            reachable = False
            live_embedder = False
    provider = embedder_provider() if live_embedder else None
    # Key present but index not armed → keyword, not hybrid (no fake green).
    if configured and reachable and live_embedder:
        mode = "hybrid"
    elif configured and reachable:
        mode = "keyword"
    else:
        mode = "scan"
    return {
        "meili_configured": configured,
        "meili_reachable": reachable,
        "meili_embedder": live_embedder,
        "meili_embedder_provider": provider or "",
        "meili_embedder_key_present": bool(embedder_provider()),
        "kb_mode": mode,
    }
