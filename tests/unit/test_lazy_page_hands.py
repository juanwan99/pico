"""pico#1342: page hands stay off the model's tool list until a page is open;
the school catalog rides with the edu sidebar, not the workbench.

The bridge test runs the real pico-gateway-tools.ts under Node (type stripping)
against a stand-in ExtensionAPI that keeps the active list the way Pi does.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    PAGE_HAND_TOOLS,
    resolve_visible_tools,
    visible_tools_env,
)
from pico_orchestrator.edu_agent_tools import EDU_AGENT_TOOLS
from pico_orchestrator.edu_sidebar import edu_sidebar_tool_ceiling

BRIDGE = ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts"

_HOOKS = """
export async function resolve(spec, ctx, next) {
  if (spec === "@earendil-works/pi-ai") {
    return { url: "data:text/javascript,export const Type=new Proxy({},{get:()=>()=>({})});", shortCircuit: true };
  }
  return next(spec, ctx);
}
"""

# Steps: ["start", branch] = before_agent_start with that session branch;
# ["end", toolName, isError, details] = tool_execution_end. Prints the active list after each.
_RUN = """
import { register } from "node:module";
register(process.argv[2]);
const mod = await import(process.argv[3]);
const steps = JSON.parse(process.argv[4]);
const handlers = {}; const tools = []; let active = [];
const pi = {
  on: (e, h) => (handlers[e] ??= []).push(h),
  registerTool: (t) => { tools.push(t.name); active.push(t.name); },
  getAllTools: () => tools.map((name) => ({ name })),
  getActiveTools: () => [...active],
  setActiveTools: (names) => { active = names.filter((n) => tools.includes(n)); },
};
mod.default(pi);
const out = [];
for (const s of steps) {
  const [kind, ...rest] = s;
  if (kind === "start") {
    const ctx = { sessionManager: { getBranch: () => rest[0] } };
    for (const h of handlers.before_agent_start ?? []) await h({}, ctx);
  } else {
    const ev = { toolName: rest[0], isError: rest[1], result: { details: rest[2] } };
    for (const h of handlers.tool_execution_end ?? []) await h(ev, {});
  }
  out.push([...active]);
}
console.log(JSON.stringify(out));
"""


def _node_strips_types() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    run = subprocess.run([node, "--version"], capture_output=True, text=True, check=True)
    major, minor = (int(x) for x in run.stdout.strip().lstrip("v").split(".")[:2])
    return (major, minor) >= (22, 18)


def _bridge(tmp_path: Path, steps: list[list[object]], visible: str = "") -> list[list[str]]:
    (tmp_path / "hooks.mjs").write_text(_HOOKS)
    (tmp_path / "run.mjs").write_text(_RUN)
    run = subprocess.run(
        [
            "node",
            str(tmp_path / "run.mjs"),
            (tmp_path / "hooks.mjs").as_uri(),
            BRIDGE.as_uri(),
            json.dumps(steps),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin:" + str(Path(shutil.which("node") or "node").parent),
            "PICO_TRUE_PI_VISIBLE_TOOLS": visible,
        },
        check=True,
    )
    return json.loads(run.stdout.strip().splitlines()[-1])


def _hands(names: list[str]) -> set[str]:
    return {n for n in names if n in PAGE_HAND_TOOLS}


def test_page_hands_are_the_browser_tools_but_open() -> None:
    assert len(PAGE_HAND_TOOLS) == 15
    assert "sandbox_browser_open" not in PAGE_HAND_TOOLS
    assert (
        "sandbox_browser_click" in PAGE_HAND_TOOLS
        and "sandbox_browser_screenshot" in PAGE_HAND_TOOLS
    )


def test_catalog_rides_with_the_sidebar_not_the_workbench() -> None:
    workbench = visible_tools_env(resolve_visible_tools(None)).split(",")
    assert not set(EDU_AGENT_TOOLS) & set(workbench)
    sidebar = resolve_visible_tools(edu_sidebar_tool_ceiling(None))
    assert set(EDU_AGENT_TOOLS) <= set(sidebar)
    # Same workbench hands beside a school page, nothing less.
    assert set(CORE_VISIBLE_TOOLS) <= set(sidebar)


@pytest.mark.skipif(not _node_strips_types(), reason="needs node >= 22.18 (type stripping)")
def test_hands_held_until_a_page_opens(tmp_path: Path) -> None:
    visible = visible_tools_env(resolve_visible_tools(None))
    start, failed, opened, next_prompt = _bridge(
        tmp_path,
        [
            ["start", []],
            [
                "end",
                "sandbox_browser_open",
                False,
                {"error": "页面打不开", "code": "browser.open_failed"},
            ],
            ["end", "sandbox_browser_open", False, {"url": "https://example.edu/login"}],
            ["start", []],
        ],
        visible,
    )
    assert "sandbox_browser_open" in start and not _hands(start)
    assert "web_search" in start and "sandbox_office_lib" in start
    # The gateway reports its failures as a normal result: still no page.
    assert not _hands(failed)
    assert _hands(opened) == set(PAGE_HAND_TOOLS)
    assert _hands(next_prompt) == set(PAGE_HAND_TOOLS)


@pytest.mark.skipif(not _node_strips_types(), reason="needs node >= 22.18 (type stripping)")
def test_a_page_opened_in_an_earlier_run_keeps_the_hands(tmp_path: Path) -> None:
    visible = visible_tools_env(resolve_visible_tools(None))

    def result(details: dict[str, object], is_error: bool = False) -> dict[str, object]:
        msg = {
            "role": "toolResult",
            "toolName": "sandbox_browser_open",
            "isError": is_error,
            "details": details,
        }
        return {"type": "message", "message": msg}

    (earlier,) = _bridge(tmp_path, [["start", [result({"url": "https://example.edu"})]]], visible)
    assert _hands(earlier) == set(PAGE_HAND_TOOLS)
    (failed,) = _bridge(
        tmp_path, [["start", [result({"error": "x"}), result({}, is_error=True)]]], visible
    )
    assert not _hands(failed)


@pytest.mark.skipif(not _node_strips_types(), reason="needs node >= 22.18 (type stripping)")
def test_a_skill_without_hands_gets_none_after_open(tmp_path: Path) -> None:
    start, opened = _bridge(
        tmp_path,
        [["start", []], ["end", "sandbox_browser_open", False, {"url": "u"}]],
        "web_search,sandbox_browser_open",
    )
    assert start == opened == ["web_search", "sandbox_browser_open"]
