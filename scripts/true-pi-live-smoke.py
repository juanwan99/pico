"""Live smoke for true Pi RPC (S1 L1–L5). No secrets printed.

Usage:
  set -a; source /path/to/deepseek.env; set +a
  PYTHONPATH=services/api:services/orchestrator \\
    python3 scripts/true-pi-live-smoke.py [--out docs/evidence/pi-true-kernel-p2/live-smoke]

Requires: pi on PATH (@earendil-works/pi-coding-agent@0.84.4), DEEPSEEK_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


@dataclass
class Principal:
    school_id: str = "live-school"
    membership_id: str = "live-member"
    scopes: list[str] | None = None


@dataclass
class MemStore:
    items: list[dict[str, Any]] = field(default_factory=list)

    async def write(self, principal: Any, *, title: str, content: str | bytes, kind: str) -> dict[str, Any]:
        art = {
            "id": f"art-{uuid.uuid4().hex[:10]}",
            "title": title,
            "kind": kind,
            "bytes": len(content) if isinstance(content, (bytes, str)) else 0,
            "school_id": getattr(principal, "school_id", ""),
            "membership_id": getattr(principal, "membership_id", ""),
        }
        self.items.append(art)
        return art

    async def read(self, principal: Any, *, artifact_id: str | None, title: str | None) -> dict[str, Any] | None:
        for it in self.items:
            if artifact_id and it["id"] == artifact_id:
                return it
            if title and it["title"] == title:
                return it
        return None

    async def list(self, principal: Any, *, limit: int) -> list[dict[str, Any]]:
        return list(self.items)[:limit]


async def _run_case(
    name: str,
    *,
    prompt: str,
    min_artifacts: int,
    max_seconds: int,
    cancel_after: float | None = None,
) -> dict[str, Any]:
    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.true_pi.config import RUNTIME_LABEL, true_pi_available
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    events: list[tuple[str, dict[str, Any]]] = []
    store = MemStore()
    t0 = time.monotonic()
    cancel_at = (t0 + cancel_after) if cancel_after else None

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        # Redact anything that looks like a key
        safe = {k: v for k, v in payload.items() if "key" not in k.lower() and "token" not in k.lower()}
        events.append((kind, safe))

    async def is_cancelled() -> bool:
        if cancel_at is None:
            return False
        return time.monotonic() >= cancel_at

    if not true_pi_available():
        return {"id": name, "ok": False, "error": "pi binary missing"}

    result = await run_true_pi_agent(
        prompt=prompt,
        principal=Principal(),
        emit=emit,
        is_cancelled=is_cancelled,
        caps=RunCaps(
            min_artifacts=min_artifacts,
            max_seconds=max_seconds,
            max_steps=16,
            allowed_tools=None,
        ),
        artifact_store=store,
        run_id=f"live-{name}-{uuid.uuid4().hex[:8]}",
    )
    kinds = [k for k, _ in events]
    tool_calls = [p.get("tool") for k, p in events if k == "tool.call"]
    return {
        "id": name,
        "ok": True,  # filled by checker
        "status": result.status,
        "error": result.error,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "runtime_label": RUNTIME_LABEL,
        "artifact_count": len(store.items),
        "artifact_titles": [a["title"] for a in store.items],
        "event_kinds": sorted(set(kinds)),
        "tool_calls": tool_calls,
        "has_tool_events": "tool.call" in kinds and "tool.result" in kinds,
        "unknown_storm": sum(1 for k in kinds if k.startswith("unknown")),
    }


def _judge(case: dict[str, Any], expect: str) -> dict[str, Any]:
    """expect: succeed_write | fail_min | cancel_or_timeout"""
    out = dict(case)
    if not case.get("ok") and case.get("error") == "pi binary missing":
        out["pass"] = False
        out["reason"] = "pi binary missing"
        return out
    st = case.get("status")
    if expect == "succeed_write":
        ok = (
            st == "succeeded"
            and int(case.get("artifact_count") or 0) >= 1
            and case.get("has_tool_events")
        )
        out["pass"] = bool(ok)
        out["reason"] = "ok" if ok else f"status={st} arts={case.get('artifact_count')} tools={case.get('has_tool_events')}"
    elif expect == "fail_min":
        ok = st == "failed"
        out["pass"] = bool(ok)
        out["reason"] = "ok" if ok else f"expected failed got {st}"
    elif expect == "cancel_or_timeout":
        ok = st in {"cancelled", "failed"}
        out["pass"] = bool(ok)
        out["reason"] = "ok" if ok else f"expected cancel/fail got {st}"
    else:
        out["pass"] = False
        out["reason"] = f"unknown expect {expect}"
    return out


async def main_async(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    from pico_orchestrator.true_pi.config import pinned_package, true_pi_available

    report: dict[str, Any] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pi_available": true_pi_available(),
        "package_pin": pinned_package(),
        "cases": [],
    }

    # L1 open domain write
    c1 = await _run_case(
        "L1",
        prompt=(
            "请用 workspace_write_file 写入一个可下载 Markdown 文件，"
            "标题 live-l1-notes.md，内容写一行：true-pi-live-L1-ok。"
            "不要只聊天。"
        ),
        min_artifacts=1,
        max_seconds=180,
    )
    report["cases"].append(_judge(c1, "succeed_write"))

    # L2 HTML
    c2 = await _run_case(
        "L2",
        prompt=(
            "请用 generate_html_document 生成一个简单 HTML 人页，"
            "title=live-l2.html，body 含可见文字 Hello Live Pi。"
            "可选 verify_html_document。"
        ),
        min_artifacts=1,
        max_seconds=180,
    )
    report["cases"].append(_judge(c2, "succeed_write"))

    # L3 timeout (short budget, impossible long task without settle quickly)
    c3 = await _run_case(
        "L3",
        prompt="请缓慢思考并反复调用工具，尽量做满很多步（测试超时）。",
        min_artifacts=0,
        max_seconds=8,
        cancel_after=None,
    )
    # If model finishes early, also try cancel
    if c3.get("status") == "succeeded":
        c3b = await _run_case(
            "L3-cancel",
            prompt="请开始一个很长的多步任务。",
            min_artifacts=0,
            max_seconds=60,
            cancel_after=1.5,
        )
        report["cases"].append(_judge(c3b, "cancel_or_timeout"))
    else:
        report["cases"].append(_judge(c3, "cancel_or_timeout"))

    # L4 false green
    c4 = await _run_case(
        "L4",
        prompt=(
            "请分别交付两个独立文件 a.md 和 b.md。"
            "（本用例强制 min_artifacts=2；若你只聊天会失败——请真正写文件。"
            " 若测试要假绿防护，模型若只聊天应 failed。）"
        ),
        min_artifacts=2,
        max_seconds=120,
    )
    # Pass if failed with 0 arts OR succeeded with >=2 arts (both honest)
    j4 = dict(c4)
    arts = int(c4.get("artifact_count") or 0)
    if c4.get("status") == "failed" and arts < 2:
        j4["pass"] = True
        j4["reason"] = "false-green blocked"
    elif c4.get("status") == "succeeded" and arts >= 2:
        j4["pass"] = True
        j4["reason"] = "delivered >=2 files"
    else:
        j4["pass"] = False
        j4["reason"] = f"status={c4.get('status')} arts={arts}"
    report["cases"].append(j4)

    # L5 mapping storm: no unknown event kinds in L1
    l1 = report["cases"][0]
    l5_ok = l1.get("pass") and not l1.get("unknown_storm")
    report["cases"].append(
        {
            "id": "L5",
            "pass": bool(l5_ok),
            "reason": "map_event ok" if l5_ok else "L1 failed or unknown storm",
            "event_kinds": l1.get("event_kinds"),
        }
    )

    all_pass = all(c.get("pass") for c in report["cases"])
    report["LIVE_SMOKE"] = "PASS" if all_pass else "FAIL"
    path = out_dir / "live-smoke-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = out_dir / "README.md"
    lines = [
        "# Live smoke · true Pi P2",
        "",
        f"- at: {report['at']}",
        f"- LIVE_SMOKE: **{report['LIVE_SMOKE']}**",
        f"- pi_available: {report['pi_available']}",
        f"- pin: `{report['package_pin']}`",
        "",
        "| ID | pass | reason |",
        "|----|------|--------|",
    ]
    for c in report["cases"]:
        lines.append(
            f"| {c.get('id')} | {c.get('pass')} | {c.get('reason') or c.get('status') or ''} |"
        )
    lines.append("")
    lines.append("Raw: `live-smoke-report.json`（无密钥）")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"LIVE_SMOKE": report["LIVE_SMOKE"], "path": str(path)}, ensure_ascii=False))
    return 0 if all_pass else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default=str(ROOT / "docs" / "evidence" / "pi-true-kernel-p2" / "live-smoke"),
    )
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(Path(args.out))))


if __name__ == "__main__":
    main()
