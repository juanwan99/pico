"""Wire edu-core sidebar onto true Pi without editing openai_compat.py.

MCP cannot ship that 78KB file intact. This hook is the thin adapter:
json_only stays one-shot chat; the 附属 marker enters Pi with a tool ceiling.
Never force_agent. Never inherit office CORE writes. File read stays.
Never land Artifact.
"""

from __future__ import annotations

import functools
from contextvars import ContextVar
from dataclasses import replace
from typing import Any


def _sidebar_helpers():
    from pico_orchestrator.edu_sidebar import (
        edu_sidebar_tool_ceiling,
        is_json_only_propose,
        sidebar_chat_only,
        with_sidebar_workbench_hint,
    )

    return (
        edu_sidebar_tool_ceiling,
        is_json_only_propose,
        sidebar_chat_only,
        with_sidebar_workbench_hint,
    )

# True only for this request's handler body (skill/tool ceiling). Stream
# closures already captured those results; do not read this in the SSE task.
EDU_SIDEBAR_PI: ContextVar[bool] = ContextVar("edu_sidebar_pi", default=False)

_INSTALLED = False


def _hint_caps(caps: Any) -> Any:
    if caps is None:
        return caps
    system = getattr(caps, "system_prompt", None) or ""
    mark = "附属，不是用户要求"
    if mark not in system:
        return caps
    hinted = _sidebar_helpers()[3](system)
    if hinted == system:
        return caps
    return replace(caps, system_prompt=hinted)


def _rewire_router(oc: Any, wrapped: Any) -> None:
    router = getattr(oc, "router", None)
    if router is None:
        return
    for route in getattr(router, "routes", []) or []:
        endpoint = getattr(route, "endpoint", None)
        if getattr(endpoint, "__name__", "") != "chat_completions":
            continue
        route.endpoint = wrapped
        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            dependant.call = wrapped


def install_edu_sidebar_pi(oc: Any) -> None:
    """Idempotent. Patch openai_compat + FastAPI route + Pi runtime caps."""
    global _INSTALLED
    if getattr(oc, "_edu_sidebar_pi_installed", False):
        return

    ceiling, is_json_only_propose, sidebar_chat_only, _unused_hint = _sidebar_helpers()
    del _unused_hint
    oc._sidebar_chat_only = sidebar_chat_only

    orig_resolve = oc._resolve_skill_for_prompt

    def resolve_skill_for_prompt(*args: Any, **kwargs: Any) -> Any:
        if EDU_SIDEBAR_PI.get():
            from pico_orchestrator.delivery_policy import no_guess_plan

            return None, no_guess_plan()
        return orig_resolve(*args, **kwargs)

    oc._resolve_skill_for_prompt = resolve_skill_for_prompt

    orig_norm = oc._normalize_allowed_tools

    def normalize_allowed_tools(raw: Any) -> list[str] | None:
        out = orig_norm(raw)
        if EDU_SIDEBAR_PI.get():
            return ceiling(out)
        return out

    oc._normalize_allowed_tools = normalize_allowed_tools

    orig_cc = oc.chat_completions

    @functools.wraps(orig_cc)
    async def chat_completions(*args: Any, **kwargs: Any) -> Any:
        body = kwargs.get("body")
        if body is None and args:
            body = args[0]
        x_pico_output = kwargs.get("x_pico_output")
        enter = False
        if body is not None:
            messages = getattr(body, "messages", None)
            client_system = oc._client_system_from_messages(messages)
            edu = oc._is_edu_sidebar_system(client_system)
            raw = oc._last_user_prompt(messages or [])
            json_only = is_json_only_propose(raw, output_header=x_pico_output)
            enter = bool(edu and not json_only)
        token = EDU_SIDEBAR_PI.set(enter)
        try:
            if enter:
                _ensure_runtime_hint()
            return await orig_cc(*args, **kwargs)
        finally:
            EDU_SIDEBAR_PI.reset(token)

    oc.chat_completions = chat_completions
    _rewire_router(oc, chat_completions)

    oc._edu_sidebar_pi_installed = True
    _INSTALLED = True


def _ensure_runtime_hint() -> None:
    """Patch Pi runtime only when a request actually runs. Do not import at boot."""
    import pico_orchestrator.runtime as rt

    if getattr(rt, "_edu_sidebar_pi_hint", False):
        return
    orig_run = rt.run_agent_runtime

    @functools.wraps(orig_run)
    async def run_agent_runtime(*args: Any, **kwargs: Any) -> Any:
        if "caps" in kwargs:
            kwargs["caps"] = _hint_caps(kwargs["caps"])
        return await orig_run(*args, **kwargs)

    rt.run_agent_runtime = run_agent_runtime
    rt._edu_sidebar_pi_hint = True


def boot_edu_sidebar_pi() -> None:
    from app import openai_compat as oc

    install_edu_sidebar_pi(oc)
