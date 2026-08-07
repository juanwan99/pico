"""Repeatable smoke for every controlled Pico skill.

Default mode is CI-friendly and validates the committed LibreChat deployment
skill files plus Pico policy snapshots. Pass --api to exercise a running Pico
API and prove Run snapshots + S7 proposal creation end to end.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

snapshot_for_skill = importlib.import_module(
    "pico_orchestrator.skill_policy"
).snapshot_for_skill
declared_tools_for_skill = importlib.import_module(
    "pico_orchestrator.skill_policy"
).declared_tools_for_skill
build_default_gateway = importlib.import_module(
    "pico_orchestrator.tools_builtin"
).build_default_gateway


SKILLS = [
    {
        "id": "skill-chat",
        "name": "skill.chat",
        "declared_tools": [],
        "chat_only": True,
        "risk": "low",
        "prompt": "只用一句话回答：chat ok",
    },
    {
        "id": "skill-read",
        "name": "skill.read",
        "declared_tools": [
            "workspace_read_file",
            "workspace_list_files",
            "fake_edu_list_classes",
        ],
        "risk": "read",
        "prompt": "列出可读取的班级信息，用一句话概括",
    },
    {
        "id": "skill-write-s7",
        "name": "skill.write_s7",
        "declared_tools": ["pico_propose_change"],
        "risk": "write_s7",
        "prompt": "提出一个把一班名称改为星辰一班的变更申请",
    },
    {
        "id": "skill-summarize",
        "name": "skill.summarize",
        "declared_tools": [
            "workspace_read_file",
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ],
        "risk": "low",
        "prompt": "总结这段内容：课程目标明确，明天完成复核。",
    },
    {
        "id": "skill-lesson-outline",
        "name": "skill.lesson_outline",
        "declared_tools": [
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ],
        "risk": "low",
        "prompt": "为一节光合作用课程起草大纲。",
    },
    {
        "id": "skill-quiz-draft",
        "name": "skill.quiz_draft",
        "declared_tools": [
            "workspace_read_file",
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ],
        "risk": "low",
        "prompt": "根据水的三态起草三道测验题。",
    },
    {
        "id": "skill-translate",
        "name": "skill.translate",
        "declared_tools": [
            "workspace_read_file",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ],
        "risk": "low",
        "prompt": "把“欢迎来到课堂”翻译成英文。",
    },
    {
        "id": "skill-meeting-notes",
        "name": "skill.meeting_notes",
        "declared_tools": [
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ],
        "risk": "low",
        "prompt": "整理会议：决定周五发布，李老师负责复核。",
    },
    {
        "id": "skill-kb-ask",
        "name": "skill.kb_ask",
        "declared_tools": [
            "kb_search",
            "workspace_list_files",
            "workspace_read_file",
        ],
        "risk": "read",
        "prompt": "根据已挂载材料回答：会议时间是什么？",
    },
]


def deployment_skill_text(skill_id: str) -> str:
    path = ROOT / "apps" / "librechat" / "skill" / skill_id / "SKILL.md"
    return path.read_text(encoding="utf-8")


def deployment_allowed_tools(text: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == "allowed-tools: []":
            return []
        if line == "allowed-tools:":
            tools: list[str] = []
            for item in lines[index + 1 :]:
                if item.startswith("  - "):
                    tools.append(item.removeprefix("  - ").strip())
                    continue
                break
            return tools
    raise AssertionError("deployment skill has no allowed-tools frontmatter")


def assert_policy_and_frontmatter() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    global_tools = set(build_default_gateway().tools)
    bound_count = 0
    for skill in SKILLS:
        text = deployment_skill_text(skill["id"])
        if f"name: {skill['id']}" not in text:
            raise AssertionError(f"{skill['id']} deployment frontmatter name mismatch")
        if "displayTitle:" in text:
            raise AssertionError(f"{skill['id']} uses unsupported deployment displayTitle")
        if deployment_allowed_tools(text) != skill["declared_tools"]:
            raise AssertionError(f"{skill['id']} deployment tools mismatch")
        if declared_tools_for_skill(skill["name"]) != skill["declared_tools"]:
            raise AssertionError(f"{skill['id']} policy binding mismatch")
        if skill.get("chat_only") and "chat-only" not in text.lower():
            raise AssertionError(f"{skill['id']} is not explicitly marked chat-only")
        bound_count += bool(skill["declared_tools"])

        snap = snapshot_for_skill(skill["name"])
        if not snap:
            raise AssertionError(f"{skill['name']} did not resolve to a snapshot")
        if snap["id"] != skill["id"]:
            raise AssertionError(f"{skill['name']} resolved to {snap['id']}")
        active_tools = [
            tool for tool in skill["declared_tools"] if tool in global_tools
        ]
        if snap["tools"] != active_tools:
            raise AssertionError(f"{skill['id']} tools {snap['tools']} != {active_tools}")
        if snap["risk"] != skill["risk"]:
            raise AssertionError(f"{skill['id']} risk {snap['risk']} != {skill['risk']}")
        if len(snap.get("prompt_hash", "")) != 64:
            raise AssertionError(f"{skill['id']} prompt_hash is not sha256-sized")
        rows.append(
            {
                "id": snap["id"],
                "name": snap["name"],
                "declared_tools": skill["declared_tools"],
                "tools": snap["tools"],
                "risk": snap["risk"],
                "requires_s7": snap["requires_s7"],
            }
        )
    if bound_count < 5:
        raise AssertionError(f"only {bound_count} skills bind tools; need at least 5")
    return rows


def call_api(
    api: str,
    headers: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: int = 120,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(api + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode() or "{}"
        return resp.status, json.loads(raw)


def run_api_smoke(api: str, membership_id: str) -> list[dict[str, Any]]:
    headers = {
        "Authorization": "Bearer pico-dev",
        "Content-Type": "application/json",
        "X-Pico-Membership-Id": membership_id,
    }
    stamp = str(int(time.time()))
    global_tools = set(build_default_gateway().tools)
    rows: list[dict[str, Any]] = []
    for skill in SKILLS:
        conversation_id = f"n3-skill-{skill['id']}-{stamp}"
        prompt = f"【Pico-Convo:{conversation_id}】\n【Pico-Skill:{skill['name']}】\n{skill['prompt']}"
        body = {
            "model": "pico-agent",
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
        }
        call_api(api, headers, "POST", "/v1/chat/completions", body, timeout=180)
        _, tasks = call_api(
            api,
            headers,
            "GET",
            "/v1/tasks?" + urllib.parse.urlencode({"conversation_id": conversation_id}),
            timeout=30,
        )
        task = (tasks.get("tasks") or [{}])[0]
        _, runs = call_api(api, headers, "GET", f"/v1/tasks/{task['id']}/runs", timeout=30)
        run = (runs.get("runs") or [{}])[0]
        snap = (run.get("token_usage") or {}).get("skill_snapshot") or {}
        row = {
            "id": skill["id"],
            "conversation_id": conversation_id,
            "task_id": task.get("id"),
            "run_id": run.get("id"),
            "status": run.get("status"),
            "snapshot_id": snap.get("id"),
            "tools": snap.get("tools"),
            "risk": snap.get("risk"),
            "requires_s7": snap.get("requires_s7"),
        }
        if snap.get("id") != skill["id"]:
            raise AssertionError(f"{skill['id']} snapshot mismatch: {snap}")
        active_tools = [
            tool for tool in skill["declared_tools"] if tool in global_tools
        ]
        if snap.get("tools") != active_tools:
            raise AssertionError(f"{skill['id']} live tools mismatch: {snap}")
        if skill["id"] == "skill-write-s7":
            _, changes = call_api(
                api,
                headers,
                "GET",
                "/v1/changes?"
                + urllib.parse.urlencode({"task_id": task["id"], "status": "proposed"}),
                timeout=30,
            )
            row["changes"] = len(changes.get("changes") or [])
            if row["changes"] < 1:
                raise AssertionError("skill-write-s7 did not create a proposed change")
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", help="Optional running Pico API, e.g. http://127.0.0.1:18765")
    parser.add_argument("--membership-id", default="n3-skill-smoke")
    args = parser.parse_args()

    rows = {"policy": assert_policy_and_frontmatter()}
    if args.api:
        rows["api"] = run_api_smoke(args.api.rstrip("/"), args.membership_id)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
