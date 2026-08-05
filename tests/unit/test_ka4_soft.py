"""KA-4 HARD: no runner module; default path is Kimi-only; fail-closed otherwise."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.settings import Settings
from pico_orchestrator.runtime import should_use_kimi_agent


def test_runner_module_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    runner = root / "services" / "orchestrator" / "pico_orchestrator" / "runner.py"
    assert not runner.is_file(), "runner.py must be deleted (KA-4 HARD plan A)"
    types = root / "services" / "orchestrator" / "pico_orchestrator" / "run_types.py"
    assert types.is_file()


def test_prod_default_settings_route_to_kimi_not_loop() -> None:
    s = Settings(
        _env_file=None,
        pico_kimi_agent_runtime=True,
        pico_kimi_agent_canary_membership_ids="",
        pico_legacy_agent_loop_emergency=False,
    )
    assert s.kimi_agent_scope == "all"
    assert s.kimi_agent_default_all is True
    assert should_use_kimi_agent(
        use_kimi_agent=s.pico_kimi_agent_runtime,
        school_id="school-a",
        membership_id="any-teacher",
        canary_principals=s.kimi_agent_canary_principal_set,
        kimi_agent_allow_all=s.kimi_agent_default_all,
        legacy_agent_loop_emergency=s.pico_legacy_agent_loop_emergency,
    )


@pytest.mark.parametrize(
    "runtime,canary,emergency,expect_kimi",
    [
        (True, "", False, True),  # prod-default
        (True, "*", False, True),
        (False, "", False, False),  # RUNTIME=0 → no path (fail-closed at runtime)
        (True, "", True, True),  # emergency no-op; still Kimi when allow_all
        (True, "bare-only", False, False),  # invalid non-empty fail-closed
    ],
)
def test_ka4_hard_reachability_matrix(
    runtime: bool, canary: str, emergency: bool, expect_kimi: bool
) -> None:
    s = Settings(
        _env_file=None,
        pico_kimi_agent_runtime=runtime,
        pico_kimi_agent_canary_membership_ids=canary,
        pico_legacy_agent_loop_emergency=emergency,
    )
    got = should_use_kimi_agent(
        use_kimi_agent=s.pico_kimi_agent_runtime,
        school_id="school-a",
        membership_id="member-x",
        canary_principals=s.kimi_agent_canary_principal_set,
        kimi_agent_allow_all=s.kimi_agent_default_all,
        legacy_agent_loop_emergency=s.pico_legacy_agent_loop_emergency,
    )
    assert got is expect_kimi


def test_defaults_without_env_do_not_silently_enable_kimi() -> None:
    s = Settings(_env_file=None)
    assert s.pico_kimi_agent_runtime is False
    assert s.kimi_agent_scope == "off"
    assert (
        should_use_kimi_agent(
            use_kimi_agent=s.pico_kimi_agent_runtime,
            school_id="school-a",
            membership_id="member-x",
            canary_principals=s.kimi_agent_canary_principal_set,
            kimi_agent_allow_all=s.kimi_agent_default_all,
            legacy_agent_loop_emergency=s.pico_legacy_agent_loop_emergency,
        )
        is False
    )


def test_emergency_does_not_force_scope_off_when_runtime_on() -> None:
    s = Settings(
        _env_file=None,
        pico_kimi_agent_runtime=True,
        pico_kimi_agent_canary_membership_ids="",
        pico_legacy_agent_loop_emergency=True,
    )
    # emergency no longer overrides default-all / scope
    assert s.kimi_agent_default_all is True
    assert s.kimi_agent_scope == "all"
