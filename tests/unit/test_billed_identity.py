from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import (
    LEGACY_PROXY_MEMBERSHIP_ID,
    Principal,
    billed_identity_ok,
    require_billed_identity,
)
from app.settings import Settings


def _p(**kwargs: object) -> Principal:
    return Principal(
        school_id=str(kwargs.get("school_id", "school-a")),
        membership_id=str(kwargs.get("membership_id", "m1")),
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=0,
        raw=dict(kwargs.get("raw") or {}),  # type: ignore[arg-type]
    )


def test_edu_membership_ok() -> None:
    assert billed_identity_ok(_p(), production=True) is True


def test_legacy_proxy_user_blocked() -> None:
    assert (
        billed_identity_ok(
            _p(membership_id=LEGACY_PROXY_MEMBERSHIP_ID),
            production=True,
        )
        is False
    )


def test_production_proxy_requires_joint_school_header() -> None:
    bare = _p(raw={"proxy": True, "joint_header": False})
    joint = _p(raw={"proxy": True, "joint_header": True, "scoped_school": "school-a"})
    assert billed_identity_ok(bare, production=True) is False
    assert billed_identity_ok(joint, production=True) is True
    assert billed_identity_ok(bare, production=False) is True


def test_require_raises() -> None:
    settings = Settings(_env_file=None, pico_env="production")
    with pytest.raises(HTTPException) as exc:
        require_billed_identity(
            _p(membership_id=LEGACY_PROXY_MEMBERSHIP_ID),
            settings,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "auth.edu_membership_required"


def test_production_proxy_without_school_membership_raises() -> None:
    settings = Settings(_env_file=None, pico_env="production")
    with pytest.raises(HTTPException) as exc:
        require_billed_identity(
            _p(raw={"proxy": True, "joint_header": False}),
            settings,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "auth.edu_membership_required"
