"""Proxy auth chain: joint school:membership header scoping (B3 reverse)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import Principal, prompt_membership_conflicts_header, scope_proxy_principal


def _proxy_principal() -> Principal:
    return Principal(
        school_id="school-a",
        membership_id="nextchat-user",
        scopes=["ai:run", "ai:read", "ai:confirm"],
        iss="pico",
        aud="pico-api",
        exp=9999999999,
        raw={"proxy": True},
    )


def test_bare_membership_keeps_proxy_school() -> None:
    p = scope_proxy_principal(_proxy_principal(), "member-canary")
    assert p.school_id == "school-a"
    assert p.membership_id == "member-canary"
    assert p.raw.get("joint_header") is False


def test_joint_header_binds_school_and_membership() -> None:
    p = scope_proxy_principal(_proxy_principal(), "other-school:member-canary")
    assert p.school_id == "other-school"
    assert p.membership_id == "member-canary"
    assert p.raw.get("joint_header") is True


def test_joint_header_reverse_differs_from_canary_school() -> None:
    """Same membership, different school — principal school is foreign."""
    canary_mid = "m1"
    reverse = scope_proxy_principal(_proxy_principal(), f"school-b:{canary_mid}")
    canary_like = scope_proxy_principal(_proxy_principal(), canary_mid)
    assert reverse.membership_id == canary_like.membership_id == canary_mid
    assert reverse.school_id != canary_like.school_id


def test_invalid_joint_header_rejected() -> None:
    with pytest.raises(HTTPException) as ei:
        scope_proxy_principal(_proxy_principal(), "bad school:m1")
    assert ei.value.status_code == 400


def test_legacy_lc_marker_does_not_conflict_with_joint_header() -> None:
    assert (
        prompt_membership_conflicts_header(
            "6a89177627f74adf4b5487b4",
            "627bcf3a-a9a8-4047-afcc-3d4878e2a7af:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        )
        is False
    )


def test_forged_bare_marker_still_conflicts_with_bare_header() -> None:
    assert prompt_membership_conflicts_header("forged", "real-member") is True


def test_forged_joint_marker_conflicts_with_joint_header() -> None:
    assert (
        prompt_membership_conflicts_header("school-b:other", "school-a:member-a") is True
    )
