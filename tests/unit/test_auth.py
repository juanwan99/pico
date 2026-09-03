from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import SCHOOL_RUN_SCOPE, decode_token, issue_test_token
from app.settings import Settings


def test_issue_and_decode_claims_shape() -> None:
    s = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_jwt_ttl_seconds=600,
    )
    token = issue_test_token(
        school_id="school-a",
        membership_id="m-1",
        scopes=["ai:run"],
        settings=s,
    )
    p = decode_token(token, s)
    assert p.school_id == "school-a"
    assert p.membership_id == "m-1"
    assert p.scopes == ["ai:run"]
    assert p.iss == "pico-test-issuer"
    assert p.aud == "pico-api"
    assert p.exp > 0
    assert p.bill_to == "member"


def test_school_run_scope_tags_bill_to_school() -> None:
    s = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_jwt_ttl_seconds=600,
    )
    token = issue_test_token(
        school_id="school-a",
        membership_id="m-1",
        scopes=["ai:run", SCHOOL_RUN_SCOPE],
        settings=s,
    )
    p = decode_token(token, s)
    assert SCHOOL_RUN_SCOPE in p.scopes
    assert p.bill_to == "school"


def test_payer_for_accepts_simple_namespace() -> None:
    from types import SimpleNamespace

    from app.auth import payer_for

    fake = SimpleNamespace(school_id="s", membership_id="m", scopes=["ai:run"])
    assert payer_for(fake) == "member"
    school = SimpleNamespace(scopes=["ai:run", "ai:school-run"])
    assert payer_for(school) == "school"
