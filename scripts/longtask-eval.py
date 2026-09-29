#!/usr/bin/env python3
"""Long-task acceptance harness (#1091 · T-LONGTASK-0).

Not CI. Same production path as scripts/office-regress.py: ECS loopback,
proxy key, synthetic tenant. Cases live in testdata/longtask-eval/.

  PICO_OPENAI_PROXY_KEY=… python3 scripts/longtask-eval.py \
      --base http://127.0.0.1:18765 --membership regress-school:regress-member

Prints JSON + a markdown table (paste into the Issue). Exit 1 if any case
exceptions-out before scoring. Auto-score is 0–5 from file/content checks; a case
passes at 3 points, or at every check when it has fewer than 3;
human score_points are listed for the planner, not auto-filled.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "testdata" / "longtask-eval"
PRODUCED_KINDS = {"xlsx", "docx", "pptx", "html"}


@dataclass
class CaseResult:
    case: str
    title: str = ""
    ok: bool = False
    auto_score: int = 0
    max_score: int = 0
    # run.status succeeded yet nothing landed: the fake green #1091 measured.
    fake_green: bool = False
    tool_calls: int = 0
    agent_steps: int = 0
    wall_s: float = 0.0
    artifacts: int = 0
    fail_reason: str = ""
    notes: list[str] = field(default_factory=list)
    score_points: list[dict[str, str]] = field(default_factory=list)
    artifact_kinds: list[str] = field(default_factory=list)


class Pico:
    def __init__(self, base: str, key: str, membership: str, model: str, timeout_s: float) -> None:
        self.base = base.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {key}",
            "X-Pico-Membership-Id": membership,
        }
        self.model = model
        self.timeout_s = timeout_s
        self.client = httpx.Client(timeout=httpx.Timeout(timeout_s, connect=10.0), trust_env=False)

    def upload(self, conversation_id: str, name: str, data: bytes) -> dict[str, Any]:
        resp = self.client.post(
            f"{self.base}/v1/files",
            headers={**self.headers, "X-Conversation-Id": conversation_id},
            files={"file": (name, data)},
        )
        resp.raise_for_status()
        return resp.json()

    def chat(self, conversation_id: str, text: str, timeout_s: float | None = None) -> tuple[str, float]:
        body = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "user", "content": text}],
        }
        started = time.perf_counter()
        out: list[str] = []
        t = timeout_s if timeout_s is not None else self.timeout_s
        with self.client.stream(
            "POST",
            f"{self.base}/v1/chat/completions",
            headers={
                **self.headers,
                "X-Conversation-Id": conversation_id,
                "Accept": "text/event-stream",
            },
            json=body,
            timeout=httpx.Timeout(t, connect=10.0),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                except ValueError:
                    continue
                for choice in obj.get("choices") or []:
                    delta = (choice.get("delta") or {}).get("content")
                    if delta:
                        out.append(str(delta))
        return "".join(out), time.perf_counter() - started

    def tasks(self, conversation_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(
            f"{self.base}/v1/tasks",
            headers=self.headers,
            params={"conversation_id": conversation_id},
        )
        resp.raise_for_status()
        return list(resp.json().get("tasks") or [])

    def events(self, run_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(f"{self.base}/v1/runs/{run_id}/events", headers=self.headers)
        resp.raise_for_status()
        return list(resp.json().get("events") or [])

    def run(self, run_id: str) -> dict[str, Any]:
        resp = self.client.get(f"{self.base}/v1/runs/{run_id}", headers=self.headers)
        resp.raise_for_status()
        return dict(resp.json().get("run") or {})

    def artifacts(self, conversation_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(
            f"{self.base}/v1/artifacts",
            headers=self.headers,
            params={"conversation_id": conversation_id},
        )
        resp.raise_for_status()
        return list(resp.json().get("artifacts") or [])

    def download(self, artifact_id: str) -> bytes:
        resp = self.client.get(
            f"{self.base}/v1/artifacts/{artifact_id}/content",
            headers=self.headers,
            params={"download": "true"},
        )
        resp.raise_for_status()
        return resp.content


def load_cases() -> list[dict[str, Any]]:
    cases = []
    for path in sorted(CASES_DIR.glob("LT*.json")):
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def _triple_workbook() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    s1 = wb.active
    s1.title = "成绩"
    s1.append(["姓名", "组别", "语文", "数学", "英语"])
    for row in [
        ("甲", "A", 85, 70, 90),
        ("乙", "B", 78, 82, 84),
        ("丙", "A", 88, 74, 79),
        ("丁", "C", 70, 68, 81),
        ("戊", "B", 82, 77, 88),
        ("己", "A", 90, 85, 92),
    ]:
        s1.append(row)
    s2 = wb.create_sheet("出勤")
    s2.append(["组别", "应到", "实到"])
    s2.append(["A", 3, 3])
    s2.append(["B", 2, 2])
    s2.append(["C", 1, 1])
    s3 = wb.create_sheet("问卷")
    s3.append(["选项", "人数"])
    s3.append(["听得懂", 22])
    s3.append(["有时跟不上", 5])
    s3.append(["完全跟不上", 1])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


GENERATORS = {"triple_workbook": _triple_workbook}


def _produced(arts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in arts if str(a.get("kind") or "").lower() in PRODUCED_KINDS]


def _latest_kind(arts: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    matches = [a for a in arts if str(a.get("kind") or "").lower() == kind]
    if not matches:
        matches = [
            a
            for a in arts
            if str(a.get("title") or "").lower().endswith("." + kind)
        ]
    if not matches:
        return None
    return max(matches, key=lambda a: str(a.get("created_at") or ""))


def _pptx_slide_count(raw: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return sum(
            1
            for name in zf.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )


def _pptx_has_chart(raw: bytes) -> bool:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return any("chart" in name.lower() for name in zf.namelist())


def _xlsx_has_chart(raw: bytes) -> bool:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return any("chart" in name.lower() for name in zf.namelist())


def _xlsx_has_formula(raw: bytes) -> bool:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(raw), data_only=False)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith("="):
                    return True
    return False


def _docx_blob(raw: bytes) -> tuple[str, int]:
    from docx import Document

    d = Document(io.BytesIO(raw))
    paras = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            paras.append(" ".join(c.text for c in row.cells))
    text = "\n".join(paras)
    n = sum(1 for p in paras if p.strip())
    return text, n


def _html_blob(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _classify_fail(status: str, error: str) -> str:
    low = (error or "").lower()
    st = (status or "").lower()
    if st in {"succeeded", "ok", ""}:
        return ""
    if any(n in low for n in ("terminated", "owner was lost", "restart")):
        return "deploy_killed"
    if any(n in low for n in ("max_seconds", "durable_max", "run timeout after")):
        return "wall_clock"
    if any(n in low for n in ("sandbox.", "office.", "no_output", "not allowlisted", "tool.")):
        return "tool_error"
    if any(
        n in low
        for n in (
            "524",
            "503",
            "overloaded",
            "timeout",
            "超时",
            "do_request_failed",
            "empty model",
            "模型不可用",
        )
    ):
        return "upstream_model"
    if st == "failed":
        return "other"
    return st or "other"


def _run_events(pico: Pico, conversation_id: str) -> tuple[int, int, str, str]:
    tool_calls = 0
    steps = 0
    status = "?"
    error = ""
    for task in pico.tasks(conversation_id):
        latest = task.get("latest_run") or {}
        rid = latest.get("id")
        if not rid:
            continue
        status = str(latest.get("status") or status)
        try:
            row = pico.run(rid)
            status = str(row.get("status") or status)
            error = str(row.get("error") or error)
        except Exception as exc:  # noqa: BLE001 — keep counting events
            error = error or f"{type(exc).__name__}"
        for e in pico.events(rid):
            kind = str(e.get("kind") or e.get("type") or "")
            if kind == "tool.call":
                tool_calls += 1
            if kind == "agent.step":
                steps += 1
    return tool_calls, steps, status, error


def _attachment_bytes(spec: dict[str, Any]) -> bytes:
    if spec.get("generate"):
        fn = GENERATORS[str(spec["generate"])]
        return fn()
    rel = spec["file"]
    return (CASES_DIR / rel).read_bytes()


def max_points(expect: dict[str, Any]) -> int:
    """Most points score_case can award for this case (same checks, same cap)."""
    kinds = [str(k).lower() for k in expect.get("kinds") or []]
    n = len(kinds)
    n += "docx" in kinds and bool(expect.get("min_paragraphs"))
    n += "pptx" in kinds and bool(expect.get("min_slides"))
    if "xlsx" in kinds:
        n += bool(expect.get("xlsx_has_chart")) + bool(expect.get("xlsx_has_formula"))
    if "html" in kinds:
        n += bool(expect.get("forbid_http_assets")) + bool(expect.get("min_heading_like"))
    n += bool(expect.get("must_contain"))
    return min(5, n)


def pass_bar(expect: dict[str, Any]) -> int:
    """3 points, or every check when a case has fewer than 3 (else it can never pass)."""
    return min(3, max_points(expect))


def score_case(case: dict[str, Any], arts: list[dict[str, Any]], pico: Pico, res: CaseResult) -> None:
    expect = case.get("expect") or {}
    produced = _produced(arts)
    res.artifacts = len(produced)
    res.artifact_kinds = sorted({str(a.get("kind") or "").lower() for a in produced if a.get("kind")})
    points = 0
    kinds = [str(k).lower() for k in expect.get("kinds") or []]
    blobs: dict[str, str] = {}
    raws: dict[str, bytes] = {}
    for kind in kinds:
        item = _latest_kind(produced, kind)
        if not item:
            res.notes.append(f"missing kind {kind}")
            continue
        raw = pico.download(item["id"])
        raws[kind] = raw
        points += 1
        if kind == "docx":
            text, npara = _docx_blob(raw)
            blobs[kind] = text
            min_p = int(expect.get("min_paragraphs") or 0)
            if min_p and npara < min_p:
                res.notes.append(f"docx paragraphs {npara} < {min_p}")
            elif min_p:
                points += 1
        elif kind == "pptx":
            n = _pptx_slide_count(raw)
            blobs[kind] = f"slides={n}"
            min_s = int(expect.get("min_slides") or 0)
            if min_s and n < min_s:
                res.notes.append(f"pptx slides {n} < {min_s}")
            elif min_s:
                points += 1
        elif kind == "xlsx":
            blobs[kind] = "xlsx"
            if expect.get("xlsx_has_chart"):
                if _xlsx_has_chart(raw):
                    points += 1
                else:
                    res.notes.append("xlsx has no chart")
            if expect.get("xlsx_has_formula"):
                try:
                    if _xlsx_has_formula(raw):
                        points += 1
                    else:
                        res.notes.append("xlsx has no formula")
                except Exception as exc:  # noqa: BLE001
                    res.notes.append(f"xlsx formula check: {type(exc).__name__}")
        elif kind == "html":
            text = _html_blob(raw)
            blobs[kind] = text
            if expect.get("forbid_http_assets") and re.search(
                r"""(src|href)=["']https?://""", text, re.IGNORECASE
            ):
                res.notes.append("html has http(s) asset")
            else:
                if expect.get("forbid_http_assets"):
                    points += 1
            min_h = int(expect.get("min_heading_like") or 0)
            if min_h:
                nh = len(re.findall(r"<h[1-6]\b", text, re.IGNORECASE)) + text.count("# ")
                if nh < min_h:
                    res.notes.append(f"html sections {nh} < {min_h}")
                else:
                    points += 1
    combined = "\n".join(blobs.values())
    needles = list(expect.get("must_contain") or [])
    if needles:
        missing = [n for n in needles if n not in combined]
        if missing:
            res.notes.append("missing text: " + ",".join(missing[:6]))
        else:
            points += 1
    res.auto_score = max(0, min(5, points))
    res.max_score = max_points(expect)
    res.ok = res.auto_score >= pass_bar(expect) and not any(k for k in kinds if k not in res.artifact_kinds)
    if kinds and any(k not in res.artifact_kinds for k in kinds):
        res.ok = False


def flag_fake_green(res: CaseResult, status: str) -> None:
    """A run that says succeeded with nothing landed never counts as a pass."""
    if status == "succeeded" and res.artifacts <= 0:
        res.fake_green = True
        res.ok = False
        res.notes.append("run succeeded, 0 artifacts")


def run_case(pico: Pico, case: dict[str, Any], stamp: str) -> CaseResult:
    cid = f"longtask-{case['id'].lower()}-{stamp}"
    res = CaseResult(case=case["id"], title=case.get("title") or "", score_points=list(case.get("score_points") or []))
    timeout = float(case.get("timeout_s") or pico.timeout_s)
    try:
        for turn in case.get("turns") or []:
            for att in turn.get("attachments") or []:
                pico.upload(cid, att["name"], _attachment_bytes(att))
            _, wall = pico.chat(cid, turn["prompt"], timeout_s=timeout)
            res.wall_s += wall
        arts = pico.artifacts(cid)
        res.tool_calls, res.agent_steps, status, error = _run_events(pico, cid)
        res.fail_reason = _classify_fail(status, error)
        score_case(case, arts, pico, res)
        if status == "failed" and not res.fail_reason:
            res.fail_reason = "other"
        flag_fake_green(res, status)
        if status == "failed":
            res.ok = False
            if not res.notes:
                res.notes.append(f"run status={status}")
    except httpx.TimeoutException:
        res.ok = False
        res.fail_reason = "wall_clock"
        res.notes.append("client timeout")
    except httpx.HTTPStatusError as exc:
        res.ok = False
        res.fail_reason = "other"
        res.notes.append(f"HTTP {exc.response.status_code}")
    return res


def render_markdown(results: list[CaseResult]) -> str:
    lines = [
        "| 例 | 标题 | ok | 自动分 | 失败原因 | 假绿 | 耗时 s | 工具 | 步 | 产物 | 备注 |",
        "|---|---|---|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for r in results:
        notes = "; ".join(r.notes)[:180]
        lines.append(
            f"| {r.case} | {r.title} | {'✅' if r.ok else '❌'} | {r.auto_score}/{r.max_score or 5} | "
            f"{r.fail_reason or '—'} | {'是' if r.fake_green else '—'} | {r.wall_s:.1f} | "
            f"{r.tool_calls} | {r.agent_steps} | "
            f"{r.artifacts} | {notes or '—'} |"
        )
    n = len(results)
    ok_n = sum(1 for r in results if r.ok)
    lines.append("")
    fake_n = sum(1 for r in results if r.fake_green)
    lines.append(f"成功率：{ok_n}/{n}" + (f" ({ok_n / n * 100:.0f}%)" if n else "") + f" · 假绿：{fake_n}")
    lines.append("")
    lines.append("人读评分要点（0–5，规划窗填）：")
    for r in results:
        pts = "；".join(p.get("text") or "" for p in r.score_points)
        lines.append(f"- {r.case}：{pts}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--base", default=os.environ.get("PICO_BASE") or "http://127.0.0.1:18765")
    ap.add_argument("--key", default=os.environ.get("PICO_OPENAI_PROXY_KEY") or "")
    ap.add_argument(
        "--membership",
        default=os.environ.get("PICO_REGRESS_MEMBERSHIP") or "regress-school:regress-member",
    )
    ap.add_argument("--model", default=os.environ.get("PICO_REGRESS_MODEL") or "pico-fast")
    ap.add_argument("--cases", default="", help="comma ids, default all LT*.json")
    ap.add_argument("--timeout", type=float, default=0.0, help="override per-case timeout_s")
    ap.add_argument("--json", default="", help="write JSON report here")
    ap.add_argument("--list", action="store_true", help="list cases and exit")
    args = ap.parse_args()
    cases = load_cases()
    if args.list:
        for c in cases:
            print(f"{c['id']}\t{c.get('timeout_s')}\t{c.get('title')}")
        return 0
    if not args.key:
        print("PICO_OPENAI_PROXY_KEY / --key required", file=sys.stderr)
        return 2
    wanted = {x.strip().upper() for x in args.cases.split(",") if x.strip()}
    if wanted:
        cases = [c for c in cases if c["id"].upper() in wanted]
        missing = wanted - {c["id"].upper() for c in cases}
        if missing:
            print("unknown cases: " + ",".join(sorted(missing)), file=sys.stderr)
            return 2
    pico = Pico(args.base, args.key, args.membership, args.model, args.timeout or 1800.0)
    stamp = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    results: list[CaseResult] = []
    for case in cases:
        if args.timeout:
            case = {**case, "timeout_s": args.timeout}
        try:
            print(f"START {case.get('id')} timeout_s={case.get('timeout_s')}", flush=True)
            one = run_case(pico, case, stamp)
            results.append(one)
            print(
                f"DONE {one.case} ok={one.ok} score={one.auto_score} "
                f"wall_s={one.wall_s:.1f} fail={one.fail_reason or '-'}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            fail = CaseResult(
                case=case.get("id") or "?",
                title=case.get("title") or "",
                ok=False,
                fail_reason="other",
                notes=[f"exception: {type(exc).__name__}: {exc}"],
                score_points=list(case.get("score_points") or []),
            )
            results.append(fail)
            print(f"DONE {fail.case} ok=False exception={type(exc).__name__}", flush=True)
    report = {
        "base": args.base,
        "model": args.model,
        "membership": args.membership,
        "stamp": stamp,
        "results": [r.__dict__ for r in results],
        "pass": all(r.ok for r in results),
        "success": f"{sum(1 for r in results if r.ok)}/{len(results)}",
    }
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print(render_markdown(results))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
