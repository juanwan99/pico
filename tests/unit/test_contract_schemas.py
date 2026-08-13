"""Phase 2: contract files frozen + JSON Schemas loadable."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "packages" / "contracts" / "schemas"
DOCS = ROOT / "docs" / "contracts"


def test_frozen_docs_exist_and_marked():
    for name in (
        "delegated-auth.md",
        "tools.md",
        "ai-facts.md",
        "change-handoff.md",
    ):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "STATUS: FROZEN" in text, name
        if name == "tools.md":
            # #507: allowlisted web_search / web_fetch (no blanket Web ban)
            assert "VERSION: 1.1" in text, name
        else:
            assert "VERSION: 1.0" in text, name


def test_json_schemas_parse():
    files = list(SCHEMAS.glob("*.json"))
    assert len(files) >= 4
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("$schema")
        assert data.get("title")


def test_claims_schema_requires_tenant_fields():
    schema = json.loads((SCHEMAS / "delegated-claims.schema.json").read_text())
    req = set(schema["required"])
    assert {"iss", "aud", "exp", "school_id", "membership_id", "scopes"} <= req
    assert schema["properties"]["aud"].get("const") == "pico-api"


def test_change_handoff_schema_matches_frozen_envelope():
    schema = json.loads((SCHEMAS / "change-handoff.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "pico_change_id",
        "school_id",
        "membership_id",
        "title",
        "summary",
        "payload",
        "confirmed_at",
        "confirmed_by",
    }


def test_tool_name_pattern_forbids_dots():
    schema = json.loads((SCHEMAS / "tool-invoke.schema.json").read_text())
    pattern = schema["properties"]["name"]["pattern"]
    import re

    assert re.match(pattern, "fake_edu_list_classes")
    assert not re.match(pattern, "fake_edu.list_classes")
