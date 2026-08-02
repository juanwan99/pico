
"""Joint canary key routing — reverse school isolation."""

from __future__ import annotations

from pico_orchestrator.runtime import principal_in_canary


def test_canary_requires_matching_school_and_membership() -> None:
    allow = {("school-a", "member-1")}
    assert principal_in_canary(
        school_id="school-a",
        membership_id="member-1",
        canary_principals=allow,
    )
    # same membership, different school → blocked
    assert not principal_in_canary(
        school_id="school-b",
        membership_id="member-1",
        canary_principals=allow,
    )
    # bare membership entry must not match (strings without school)
    assert not principal_in_canary(
        school_id="school-a",
        membership_id="member-1",
        canary_principals={"member-1"},
    )


def test_canary_accepts_joint_string_entries() -> None:
    assert principal_in_canary(
        school_id="s1",
        membership_id="m1",
        canary_principals=["s1:m1", "s2:m2"],
    )
    assert not principal_in_canary(
        school_id="s1",
        membership_id="m2",
        canary_principals=["s1:m1", "s2:m2"],
    )
