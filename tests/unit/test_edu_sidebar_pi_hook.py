"""Edu sidebar Pi hook. chat_completions must not locally import session_factory."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def test_chat_completions_does_not_shadow_session_factory() -> None:
    """Edu sidebar skips the named-school block. A local import of
    session_factory inside chat_completions makes it an unbound cell;
    the Pi SSE path then raises NameError and the rail stays on 正在想.
    """
    import ast

    tree = ast.parse(
        (ROOT / "services" / "api" / "app" / "openai_compat.py").read_text(encoding="utf-8")
    )
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "chat_completions"
    )
    shadowed = [
        child.lineno
        for child in ast.walk(fn)
        if isinstance(child, ast.ImportFrom)
        and (child.module or "") == "app.db"
        and any(alias.name == "session_factory" for alias in child.names)
    ]
    assert shadowed == []


def test_app_init_does_not_import_orchestrator() -> None:
    text = (ROOT / "services" / "api" / "app" / "__init__.py").read_text(encoding="utf-8")
    assert "from pico_orchestrator" not in text
    assert "import pico_orchestrator" not in text
    assert "boot_edu_sidebar_pi" not in text


def test_app_package_imports_without_orchestrator_on_path() -> None:
    import subprocess

    src = (
        "import app\n"
        "assert 'pico_orchestrator' not in __import__('sys').modules\n"
        "print('ok')\n"
    )
    env_path = str(ROOT / "services" / "api")
    out = subprocess.check_output(
        [sys.executable, "-c", src],
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": env_path},
        cwd=str(ROOT),
        text=True,
    )
    assert "ok" in out


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
    from pico_orchestrator.edu_sidebar import EDU_SIDEBAR_DEFAULT_TOOLS

    token = EDU_SIDEBAR_PI.set(True)
    try:
        skill, plan = oc._resolve_skill_for_prompt("请写一份方案包", {"id": "hung"})
        assert skill is None
        assert plan.force_agent is False
        assert plan.min_artifacts == 0
        assert oc._normalize_allowed_tools(None) == list(EDU_SIDEBAR_DEFAULT_TOOLS)
        assert oc._normalize_allowed_tools([]) == list(EDU_SIDEBAR_DEFAULT_TOOLS)
        assert oc._normalize_allowed_tools(["web_search", "web_fetch"]) == list(EDU_SIDEBAR_DEFAULT_TOOLS)
        assert "generate_html_document" not in EDU_SIDEBAR_DEFAULT_TOOLS
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


def test_hint_caps_says_no_hands_without_affordances() -> None:
    """#1175 PR-2: contract §2.5 — the prompt itself must say the page has no hand."""
    from dataclasses import dataclass

    from app.edu_sidebar_pi import _hint_caps
    from pico_orchestrator.page_mutations import SIDEBAR_NO_HANDS_HINT, SIDEBAR_PAGE_HANDS_HINT

    @dataclass
    class Caps:
        system_prompt: str = ""
        page_affordances: list | None = None

    bare = _hint_caps(Caps(system_prompt="附属，不是用户要求\n{}"))
    assert SIDEBAR_NO_HANDS_HINT in bare.system_prompt
    assert SIDEBAR_PAGE_HANDS_HINT not in bare.system_prompt
    assert _hint_caps(bare).system_prompt == bare.system_prompt  # idempotent

    hands = _hint_caps(
        Caps(system_prompt="附属，不是用户要求\n{}", page_affordances=[{"id": "cell:c1:mon:3"}])
    )
    assert SIDEBAR_PAGE_HANDS_HINT in hands.system_prompt
    assert SIDEBAR_NO_HANDS_HINT not in hands.system_prompt

    plain = Caps(system_prompt="你是 Pico")
    assert _hint_caps(plain) is plain


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


def test_sidebar_run_skips_the_box_so_pi_has_no_shell(monkeypatch) -> None:
    """edu-core#5324: the sidebar never gets a workspace box → Pi's own
    bash / read / write / edit stay off (legacy spawn is --no-builtin-tools,
    tests/security/test_workspace_isolation.py)."""
    from app.edu_sidebar_pi import _hint_caps
    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.true_pi.runtime import box_mode_for

    monkeypatch.setenv("PICO_RUNNER_URL", "http://runner")
    monkeypatch.delenv("PICO_RUNNER_MEMBERSHIPS", raising=False)
    workbench = RunCaps(system_prompt="你是 Pico")
    sidebar = _hint_caps(RunCaps(system_prompt="附属，不是用户要求\n{}"))
    assert _hint_caps(workbench).edu_sidebar is False
    assert sidebar.edu_sidebar is True
    assert box_mode_for(workbench, "s1", "m1") is True
    assert box_mode_for(sidebar, "s1", "m1") is False
    assert box_mode_for(workbench, "", "m1") is False
