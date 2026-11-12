"""First-turn size gate (edu-core#5337 · #5285 P1-4).

What Pi gets before the teacher's words: the system text plus every visible
tool's description and parameters in ``pico-gateway-tools.ts``. Two entries:
the workbench (box mode, full CORE) and the edu sidebar (school hands + the
page hand). Each may grow at most 10% over the bytes recorded here; a PR that
really needs more raises the number in this file, so the growth shows in diff.

Tool bytes are the TS source of the description and parameters arguments, not
the JSON Pi serialises — stable, and it moves with every word added.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import resolve_visible_tools
from pico_orchestrator.edu_sidebar import EDU_SIDEBAR_DEFAULT_TOOLS, with_sidebar_workbench_hint
from pico_orchestrator.page_mutations import SIDEBAR_PAGE_HANDS_HINT
from pico_orchestrator.page_mutations import TOOL_NAME as PAGE_TOOL
from pico_orchestrator.true_pi.runner import BOX_HIDDEN_TOOLS, WORKSPACE_SYSTEM
from pico_orchestrator.true_pi.runtime import pico_system_text

TS = ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts"

# Bytes at 2026-11-11 (pico main 097a3916). Gate = ×1.10.
RECORDED = {"workbench": 15_977, "sidebar": 5_655}
GROWTH = 1.10


def _call_args(src: str, start: int) -> list[str]:
    """Top-level arguments of the call whose ``(`` ends at ``start``."""
    args: list[str] = []
    cur: list[str] = []
    depth, i, quote = 1, start, ""
    while depth:
        ch = src[i]
        if quote:
            cur.append(ch)
            if ch == "\\":
                cur.append(src[i + 1])
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'`":
            quote = ch
            cur.append(ch)
        elif ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            if depth:
                cur.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    args.append("".join(cur).strip())
    return args


def ts_tool_bytes() -> dict[str, int]:
    src = TS.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    marker = "registerTool("
    at = src.find(marker)
    while at >= 0:
        args = _call_args(src, at + len(marker))
        # registerTool(pi, "name", description, parameters, ...) — skip the definition.
        if len(args) >= 4 and args[0] == "pi" and args[1].startswith('"'):
            out[json.loads(args[1])] = len((args[2] + args[3]).encode("utf-8"))
        at = src.find(marker, at + len(marker))
    return out


def entry_bytes() -> dict[str, int]:
    tools = ts_tool_bytes()

    def size(system: str, names: list[str]) -> int:
        missing = [n for n in names if n not in tools]
        assert not missing, f"visible tools not registered in {TS.name}: {missing}"
        return len(system.encode("utf-8")) + sum(tools[n] for n in names)

    workbench = [n for n in resolve_visible_tools(None) if n not in BOX_HIDDEN_TOOLS]
    sidebar = [*EDU_SIDEBAR_DEFAULT_TOOLS, PAGE_TOOL]
    return {
        "workbench": size(f"{pico_system_text()}\n\n{WORKSPACE_SYSTEM}", workbench),
        "sidebar": size(f"{with_sidebar_workbench_hint('')}\n{SIDEBAR_PAGE_HANDS_HINT}", sidebar),
    }


def test_ts_parser_sees_every_registered_tool() -> None:
    tools = ts_tool_bytes()
    assert len(tools) == TS.read_text(encoding="utf-8").count("registerTool(\n    pi,")
    assert all(size > 50 for size in tools.values())


def test_first_turn_stays_within_ten_percent() -> None:
    got = entry_bytes()
    over = {
        name: f"{got[name]} > {int(RECORDED[name] * GROWTH)} (recorded {RECORDED[name]})"
        for name in RECORDED
        if got[name] > RECORDED[name] * GROWTH
    }
    assert not over, f"first turn grew >10%: {over} — trim, or raise RECORDED in this PR"
