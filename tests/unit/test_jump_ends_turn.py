"""edu-core#5227: a sidebar turn that only goes to a page ends with the jump.

Runs the real pico-gateway-tools.ts under Node (type stripping) against a
stand-in ExtensionAPI and gateway, like test_lazy_page_hands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_lazy_page_hands import _HOOKS, BRIDGE, _node_strips_types

# Steps: ["start"]; ["end", toolName]; ["say", content] = assistant message_end,
# prints the content Pi keeps; ["call", toolName, args] = execute, prints terminate.
_RUN = """
import { register } from "node:module";
register(process.argv[2]);
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true, result: { proposed: true } }) });
const mod = await import(process.argv[3]);
const handlers = {}; const tools = {};
const pi = {
  on: (e, h) => (handlers[e] ??= []).push(h),
  registerTool: (t) => { tools[t.name] = t; },
  getAllTools: () => Object.keys(tools).map((name) => ({ name })),
  getActiveTools: () => Object.keys(tools),
  setActiveTools: () => {},
};
mod.default(pi);
const fire = async (e, ev) => { let out; for (const h of handlers[e] ?? []) out = (await h(ev, { sessionManager: { getBranch: () => [] } })) ?? out; return out; };
const out = [];
for (const [kind, ...rest] of JSON.parse(process.argv[4])) {
  if (kind === "start") await fire("before_agent_start", {});
  else if (kind === "end") await fire("tool_execution_end", { toolName: rest[0], isError: false, result: {} });
  else if (kind === "say") {
    const r = await fire("message_end", { message: { role: "assistant", content: rest[0] } });
    out.push(r ? r.message.content : null);
  } else out.push(!!(await tools[rest[0]].execute("c1", rest[1])).terminate);
}
console.log(JSON.stringify(out));
"""


def _run(tmp_path: Path, steps: list[list[object]]) -> list[object]:
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
            "PICO_TRUE_PI_TOOL_URL": "http://127.0.0.1:1",
            "PICO_TRUE_PI_TOOL_TOKEN": "t",
        },
        check=True,
    )
    return json.loads(run.stdout.strip().splitlines()[-1])


def _jump(label: str = "打开校历", **params: object) -> dict[str, object]:
    return {
        "affordance_id": "nav:go",
        "label": label,
        "params": {"tab": "school-affairs", **params},
    }


def _call(args: dict[str, object]) -> dict[str, object]:
    return {"type": "toolCall", "id": "c1", "name": "propose_page_mutation", "arguments": args}


needs_node = pytest.mark.skipif(
    not _node_strips_types(), reason="needs node >= 22.18 (type stripping)"
)


@needs_node
def test_a_bare_jump_says_one_line_and_ends(tmp_path: Path) -> None:
    said, ends = _run(
        tmp_path, [["start"], ["say", [_call(_jump())]], ["call", "propose_page_mutation", _jump()]]
    )
    assert said[0] == {"type": "text", "text": "好的，这就打开校历。"}
    assert said[1]["type"] == "toolCall"
    assert ends is True


@needs_node
def test_own_words_kept_and_label_gets_a_verb(tmp_path: Path) -> None:
    words = [{"type": "text", "text": "校历在校务公开里。"}, _call(_jump())]
    kept, bare = _run(
        tmp_path, [["start"], ["say", words], ["say", [_call(_jump("校务公开 · 作息"))]]]
    )
    assert kept is None
    assert bare[0]["text"] == "好的，这就去校务公开 · 作息。"


@needs_node
def test_data_read_or_button_keeps_the_answer_round(tmp_path: Path) -> None:
    read = _run(
        tmp_path,
        [
            ["start"],
            ["end", "edu_query"],
            ["say", [_call(_jump())]],
            ["call", "propose_page_mutation", _jump()],
        ],
    )
    assert read == [None, False]
    button = _run(
        tmp_path,
        [
            ["start"],
            ["say", [_call(_jump(jump=False))]],
            ["call", "propose_page_mutation", _jump(jump=False)],
        ],
    )
    assert button == [None, False]
    mixed = [_call(_jump()), {"type": "toolCall", "id": "c2", "name": "edu_query", "arguments": {}}]
    assert _run(tmp_path, [["start"], ["say", mixed]]) == [None]


@needs_node
def test_next_run_starts_clean_and_catalog_lookups_do_not_count(tmp_path: Path) -> None:
    ends = _run(
        tmp_path,
        [
            ["start"],
            ["end", "edu_query"],
            ["start"],
            ["end", "edu_catalog_find"],
            ["end", "edu_query_list"],
            ["call", "propose_page_mutation", _jump()],
        ],
    )
    assert ends == [True]
