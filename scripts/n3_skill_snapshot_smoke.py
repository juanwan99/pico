"""N3 repeatable smoke for the three thin Pico skills.

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


SKILLS = [
    {
        "id": "skill-chat",
        "name": "skill.chat",
        "tools": [],
        "risk": "low",
        "prompt": "只用一句话回答：chat ok",
    },
    {
        "id": "skill-read",
        "name": "skill.read",
        "tools": ["fake_edu_list_classes"],
        "risk": "read",
        "prompt": "列出可读取的班级信息，用一句话概括",
    },
    {
        "id": "skill-write-s7",
        "name": "skill.write_s7",
        "tools": ["pico_propose_change"],
        "risk": "write_s7",
        "prompt": "提出一个把一班名称改为星辰一班的变更申请",
    },
]


def deployment_skill_text(skill_id: str) -> str:
    path = ROOT / "apps" / "librechat" / "skill" / skill_id / "SKILL.md"
    return path.read_text(encoding="utf-8")


def assert_policy_and_frontmatter() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for skill in SKILLS:
        text = deployment_skill_text(skill["id"])
        if f"name: {skill['id']}" not in text:
            raise AssertionError(f"{skill['id']} deployment frontmatter name mismatch")
        if "displayTitle:" in text:
            raise AssertionError(f"{skill['id']} uses unsupported deployment displayTitle")

        snap = snapshot_for_skill(skill["name"])
        if not snap:
            raise AssertionError(f"{skill['name']} did not resolve to a snapshot")
        if snap["id"] != skill["id"]:
            raise AssertionError(f"{skill['name']} resolved to {snap['id']}")
        if snap["tools"] != skill["tools"]:
            raise AssertionError(f"{skill['id']} tools {snap['tools']} != {skill['tools']}")
        if snap["risk"] != skill["risk"]:
            raise AssertionError(f"{skill['id']} risk {snap['risk']} != {skill['risk']}")
        if len(snap.get("prompt_hash", "")) != 64:
            raise AssertionError(f"{skill['id']} prompt_hash is not sha256-sized")
        rows.append(
            {
                "id": snap["id"],
                "name": snap["name"],
                "tools": snap["tools"],
                "risk": snap["risk"],
                "requires_s7": snap["requires_s7"],
            }
        )
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
        if snap.get("tools") != skill["tools"]:
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
