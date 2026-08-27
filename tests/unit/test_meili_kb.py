"""T-KB-CATCH: projection keys, tenant filter, degraded honesty, ingest-to-index."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pico_orchestrator.meili_kb import (
    MeiliIndex,
    document_from_artifact,
    extract_index_text,
    extract_office_text,
    health_fields,
    is_material,
    parse_office_bytes,
    project_material_artifact,
    quote_filter_value,
    search_materials,
    tenant_filter,
    upsert_material,
)


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.search_hits: list[dict[str, Any]] = []
        self.search_status = 200
        self.fail_search = False

    def request(
        self,
        method: str,
        url: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 8.0,
    ) -> tuple[int, Any]:
        self.calls.append((method, url, json))
        if url.endswith("/health"):
            return 200, {"status": "available"}
        if method == "GET" and url.endswith("/indexes/pico_materials"):
            return 200, {"uid": "pico_materials"}
        if method == "POST" and url.endswith("/search"):
            if self.fail_search:
                return 503, {"message": "down"}
            return self.search_status, {"hits": list(self.search_hits)}
        return 202, {"taskUid": 1}


def test_tenant_filter_is_server_side_and_quoted() -> None:
    clause = tenant_filter("school-a", "member-1")
    assert 'school_id = "school-a"' in clause
    assert 'membership_id = "member-1"' in clause
    assert "OR" not in clause
    sneaky = quote_filter_value('x" OR school_id = "other')
    assert "OR" in sneaky
    # Quotes inside the value are escaped, so it stays one string token.
    assert sneaky.startswith('"') and sneaky.endswith('"')
    with pytest.raises(ValueError):
        tenant_filter("school a", "m1")
    with pytest.raises(ValueError):
        tenant_filter("school-a", "")


def test_search_injects_principal_filter_not_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    http = FakeHttp()
    http.search_hits = [
        {"artifact_id": "a1", "title": "校历.md", "text": "三月开学", "school_id": "school-a"}
    ]
    out = search_materials(
        "开学",
        school_id="school-a",
        membership_id="m1",
        limit=8,
        client=http,
    )
    search_calls = [c for c in http.calls if c[0] == "POST" and str(c[1]).endswith("/search")]
    assert len(search_calls) == 1
    body = search_calls[0][2]
    assert body["filter"] == tenant_filter("school-a", "m1")
    assert "m-other" not in json.dumps(body)
    assert "hybrid" not in body
    assert out["hits"][0]["artifact_id"] == "a1"


def test_search_hybrid_only_when_embed_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-sf")
    http = FakeHttp()
    search_materials("近义", school_id="s1", membership_id="m1", limit=5, client=http)
    body = next(c[2] for c in http.calls if str(c[1]).endswith("/search"))
    assert body["hybrid"]["semanticRatio"] == 0.5
    assert body["hybrid"]["embedder"] == "default"


def test_search_hybrid_zhipu_when_no_siliconflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prod has Zhipu, not SF — hybrid must arm without inventing a vector kernel."""
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.setenv("ZHIPU_API_KEY", "zk-zhipu")
    http = FakeHttp()
    search_materials("近义", school_id="s1", membership_id="m1", limit=5, client=http)
    body = next(c[2] for c in http.calls if str(c[1]).endswith("/search"))
    assert body["hybrid"]["embedder"] == "default"

    MeiliIndex(http).ensure()
    patch = next(c[2] for c in http.calls if c[0] == "PATCH")
    emb = patch["embedders"]["default"]
    assert emb["url"] == "https://open.bigmodel.cn/api/paas/v4/embeddings"
    assert emb["apiKey"] == "zk-zhipu"
    assert emb["request"]["model"] == "embedding-3"
    assert emb["request"]["dimensions"] == 1024


def test_siliconflow_preferred_over_zhipu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-sf")
    monkeypatch.setenv("ZHIPU_API_KEY", "zk-zhipu")
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    http = FakeHttp()
    MeiliIndex(http).ensure()
    patch = next(c[2] for c in http.calls if c[0] == "PATCH")
    emb = patch["embedders"]["default"]
    assert "siliconflow" in emb["url"]
    assert emb["apiKey"] == "sk-sf"
    assert emb["request"]["model"] == "BAAI/bge-m3"


def test_search_raises_when_meili_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    http = FakeHttp()
    http.fail_search = True
    with pytest.raises(RuntimeError):
        search_materials("x", school_id="s1", membership_id="m1", limit=3, client=http)


def test_projection_document_keys() -> None:
    doc = document_from_artifact(
        artifact_id="art-9",
        title="通知.md",
        text="家长会周五",
        school_id="school-a",
        membership_id="m1",
        created_at="2026-08-23T00:00:00",
    )
    assert set(doc) >= {
        "artifact_id",
        "title",
        "text",
        "school_id",
        "membership_id",
        "created_at",
    }
    assert doc["artifact_id"] == "art-9"


def test_is_material_skips_html_keeps_docs() -> None:
    assert is_material(kind="html", title="页.html") is False
    assert is_material(kind="file", title="校历.md") is True
    assert is_material(kind="png", title="图.png") is False
    assert is_material(kind="bin", title="通知.pdf") is True
    assert is_material(kind="bin", title="课时.xlsx") is True
    assert is_material(kind="xlsx", title="课时.xlsx") is True
    assert is_material(kind="pptx", title="封面.pptx") is True


def test_extract_index_text_utf8_not_title_only() -> None:
    body = extract_index_text(
        title="通知.md",
        kind="file",
        content="正文：寒假从 1 月 20 日开始。",
        raw=None,
    )
    assert "1 月 20 日" in body
    assert body != "通知.md"


def test_parse_to_index_uses_field_kb_ingest_not_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    fake = types.ModuleType("ingest")

    def ingest_bytes(*, filename: str, data: bytes, title: str):
        assert filename.endswith((".pdf", ".docx"))
        assert data.startswith(b"%PDF") or data[:2] == b"PK"
        return {"ok": True, "slices": [{"excerpt": "抽出的正文：寒假从一月二十日开始。"}]}

    fake.ingest_bytes = ingest_bytes  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ingest", fake)
    text = parse_office_bytes(filename="家长通知.pdf", data=b"%PDF-1.4 body")
    assert "一月二十日" in text
    indexed = extract_index_text(
        title="家长通知.pdf",
        kind="edu_office",
        content=None,
        raw=b"%PDF-1.4 body",
    )
    assert "一月二十日" in indexed
    assert indexed != "家长通知.pdf"
    doc = document_from_artifact(
        artifact_id="art-pdf",
        title="家长通知.pdf",
        text=indexed,
        school_id="school-a",
        membership_id="m1",
    )
    assert "一月二十日" in doc["text"]
    assert doc["text"] != doc["title"]


def test_extract_index_text_office_extract_xlsx_pptx_txt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pico_orchestrator.meili_kb.extract_office_text",
        lambda *, filename, data: f"抽出:{filename}:{data.decode('utf-8', errors='ignore')[:20]}",
    )
    xlsx = extract_index_text(
        title="课时.xlsx",
        kind="edu_office",
        content=None,
        raw=b"PK-xlsx-unique-cell",
    )
    assert "课时.xlsx" in xlsx
    pptx = extract_index_text(
        title="封面.pptx",
        kind="edu_office",
        content=None,
        raw=b"PK-pptx-unique-slide",
    )
    assert "封面.pptx" in pptx
    txt = extract_index_text(
        title="备忘.txt",
        kind="file",
        content="已有正文：三月开学。",
        raw=b"ignored-when-content",
    )
    assert "三月开学" in txt


def test_extract_office_text_uses_stdlib_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    from pathlib import Path

    api = Path(__file__).resolve().parents[2] / "services" / "api"
    if str(api) not in sys.path:
        sys.path.insert(0, str(api))
    import app.office_extract as oe

    def fake(filename: str, data: bytes):
        assert filename.endswith(".xlsx")
        _ = data
        return {"status": "ok", "text": "高一1班,语文,5"}

    monkeypatch.setattr(oe, "extract_office", fake)
    text = extract_office_text(filename="课时.xlsx", data=b"PK")
    assert "语文" in text


def test_project_empty_pdf_is_not_fake_green(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    monkeypatch.setattr(
        "pico_orchestrator.meili_kb.parse_office_bytes",
        lambda **_k: "",
    )
    posted: list[Any] = []

    class _P:
        school_id = "school-a"
        membership_id = "m1"

    monkeypatch.setattr(
        "pico_orchestrator.meili_kb.upsert_material",
        lambda doc, client=None: posted.append(doc) or True,
    )
    ok = project_material_artifact(
        _P(),
        artifact_id="art-empty",
        title="空.pdf",
        kind="edu_office",
        content=b"%PDF-1.4",
    )
    assert ok is False
    assert posted == []


def test_upsert_posts_to_index(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    http = FakeHttp()
    doc = document_from_artifact(
        artifact_id="a",
        title="t.md",
        text="hello",
        school_id="s",
        membership_id="m",
    )
    assert upsert_material(doc, client=http) is True
    posted = [c for c in http.calls if c[0] == "POST" and str(c[1]).endswith("/documents")]
    assert posted
    assert posted[0][2][0]["artifact_id"] == "a"


def test_ensure_sets_filterable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    http = FakeHttp()
    MeiliIndex(http).ensure()
    patches = [c for c in http.calls if c[0] == "PATCH"]
    assert patches
    attrs = patches[0][2]["filterableAttributes"]
    assert "school_id" in attrs and "membership_id" in attrs


def test_health_fields_honest_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEILI_MASTER_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    scan = health_fields()
    assert scan["meili_configured"] is False
    assert scan["kb_mode"] == "scan"
    assert scan["meili_embedder_provider"] == ""

    monkeypatch.setenv("MEILI_MASTER_KEY", "k")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")

    class _Down:
        def ping(self) -> bool:
            return False

    monkeypatch.setattr("pico_orchestrator.meili_kb.MeiliIndex", lambda: _Down())
    down = health_fields()
    assert down["meili_configured"] is True
    assert down["meili_reachable"] is False
    assert down["kb_mode"] == "scan"
    assert down["meili_embedder"] is False

    class _Up:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr("pico_orchestrator.meili_kb.MeiliIndex", lambda: _Up())
    keyword = health_fields()
    assert keyword["meili_reachable"] is True
    assert keyword["kb_mode"] == "keyword"

    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-sf")
    hybrid = health_fields()
    assert hybrid["meili_embedder"] is True
    assert hybrid["kb_mode"] == "hybrid"
    assert hybrid["meili_embedder_provider"] == "siliconflow"

    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.setenv("ZHIPU_API_KEY", "zk")
    zhipu = health_fields()
    assert zhipu["meili_embedder"] is True
    assert zhipu["kb_mode"] == "hybrid"
    assert zhipu["meili_embedder_provider"] == "zhipu"

    monkeypatch.setattr("pico_orchestrator.meili_kb.MeiliIndex", lambda: _Down())
    no_fake = health_fields()
    assert no_fake["meili_embedder"] is True
    assert no_fake["kb_mode"] == "scan"
