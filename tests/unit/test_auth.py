from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import decode_token, issue_test_token
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
