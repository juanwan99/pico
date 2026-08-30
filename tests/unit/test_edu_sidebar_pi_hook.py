"""Edu sidebar enters Pi via small hook — openai_compat.py is not edited."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def test_settings_import_does_not_explode() -> None:
    from app.settings import Settings

    assert Settings is not None


def test_boot_patches_openai_compat_sidebar_route() -> None:
    from app import openai_compat as oc
    from pico_orchestrator.delivery_policy import no_guess_plan

    assert oc._edu_sidebar_pi_installed is True
    assert oc._sidebar_chat_only(edu_sidebar=True, json_only=False) is False
    assert oc._sidebar_chat_only(edu_sidebar=True, json_only=True) is True
    assert oc._sidebar_chat_only(edu_sidebar=False, json_only=False) is False
    # Workbench tool lists stay untouched outside a sidebar request.
    assert oc._normalize_allowed_tools(None) is None
    assert oc._normalize_allowed_tools(["generate_html_document"]) == [
        "generate_html_document"
    ]

    from app.edu_sidebar_pi import EDU_SIDEBAR_PI

    token = EDU_SIDEBAR_PI.set(True)
    try:
        skill, plan = oc._resolve_skill_for_prompt("请写一份方案包", {"id": "hung"})
        assert skill is None
        assert plan.force_agent is False
        assert plan.min_artifacts == 0
        assert oc._normalize_allowed_tools(None) == []
        assert oc._normalize_allowed_tools(["generate_html_document", "web_search"]) == [
            "web_search"
        ]
    finally:
        EDU_SIDEBAR_PI.reset(token)

    dummy = no_guess_plan()
    assert dummy.force_agent is False

    routed = [
        getattr(route, "endpoint", None)
        for route in oc.router.routes
        if getattr(getattr(route, "endpoint", None), "__name__", "") == "chat_completions"
    ]
    assert routed
    assert routed[0] is oc.chat_completions
    assert inspect.iscoroutinefunction(oc.chat_completions)


def test_install_is_idempotent() -> None:
    from app import openai_compat as oc
    from app.edu_sidebar_pi import install_edu_sidebar_pi

    first = oc.chat_completions
    install_edu_sidebar_pi(oc)
    install_edu_sidebar_pi(oc)
    assert oc.chat_completions is first


def test_hint_caps_only_on_edu_marker() -> None:
    from dataclasses import dataclass

    from app.edu_sidebar_pi import _hint_caps
    from pico_orchestrator.edu_sidebar import SIDEBAR_WORKBENCH_HINT

    @dataclass
    class Caps:
        system_prompt: str = ""

    plain = Caps(system_prompt="你是 Pico")
    assert _hint_caps(plain) is plain
    edu = Caps(system_prompt="附属，不是用户要求\n{}")
    hinted = _hint_caps(edu)
    assert SIDEBAR_WORKBENCH_HINT in hinted.system_prompt
    assert _hint_caps(hinted).system_prompt == hinted.system_prompt
