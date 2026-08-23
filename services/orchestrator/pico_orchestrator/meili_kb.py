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
EMBED_MODEL = "BAAI/bge-m3"
EMBED_URL = "https://api.siliconflow.cn/v1/embeddings"

MATERIAL_KINDS = frozenset(
    {"file", "text", "md", "doc", "material", "kb_text", "edu_office", "edu_excerpt"}
)
SKIP_KINDS = frozenset({"html", "png", "image", "screenshot", "preview"})
PARSE_EXT = frozenset({".pdf", ".docx"})
_ID_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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
    key = siliconflow_embed_key()
    if not key:
        return None
    return {
        "default": {
            "source": "rest",
            "url": EMBED_URL,
            "apiKey": key,
            "documentTemplate": "{{doc.title}}\n{{doc.text}}",
            "request": {"model": EMBED_MODEL, "input": ["{{text}}"]},
            "response": {"data": [{"embedding": "{{embedding}}"}]},
        }
    }


def is_material(*, kind: str | None, title: str | None) -> bool:
    k = str(kind or "").strip().lower()
    name = str(title or "").strip().lower()
    if k in SKIP_KINDS:
        return False
    if k in MATERIAL_KINDS:
        return True
    return any(name.endswith(ext) for ext in (".md", ".txt", ".pdf", ".docx", ".csv", ".json"))


def extract_index_text(*, title: str, kind: str, content: str | None, raw: bytes | None) -> str:
    """UTF-8 ledger text, or field-kb-ingest for pdf/docx. Never a self-built parser."""
    name = title or "file"
    suffix = ""
    if "." in name:
        suffix = "." + name.rsplit(".", 1)[-1].lower()
    if content and suffix not in PARSE_EXT:
        return content[:MAX_TEXT]
    if suffix in PARSE_EXT and raw:
        parsed = parse_office_bytes(filename=name, data=raw)
        if parsed:
            return parsed[:MAX_TEXT]
    return (content or "")[:MAX_TEXT]


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

    def ensure(self) -> None:
        status, _ = self._call("GET", f"/indexes/{INDEX}")
        if status == 404:
            self._call(
                "POST",
                "/indexes",
                {"uid": INDEX, "primaryKey": PRIMARY_KEY},
            )
        settings: dict[str, Any] = {
            "filterableAttributes": FILTERABLE,
            "searchableAttributes": SEARCHABLE,
            "displayedAttributes": DISPLAYED,
        }
        embedders = _embedder_settings()
        if embedders:
            settings["embedders"] = embedders
        self._call("PATCH", f"/indexes/{INDEX}/settings", settings, timeout=20.0)

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
        if _embedder_settings():
            body["hybrid"] = {"semanticRatio": SEMANTIC_RATIO, "embedder": "default"}
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
    configured = meili_configured()
    reachable = False
    if configured:
        try:
            reachable = MeiliIndex().ping()
        except Exception:  # noqa: BLE001
            reachable = False
    return {
        "meili_configured": configured,
        "meili_reachable": reachable,
        "meili_embedder": bool(siliconflow_embed_key()),
        "kb_mode": (
            "hybrid" if (configured and siliconflow_embed_key()) else "keyword" if configured else "scan"
        ),
    }
