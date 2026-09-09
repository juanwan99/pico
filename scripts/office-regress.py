#!/usr/bin/env python3
"""Real-model office regression (#959 · PLAN-OFFICE-COMPUTER-V2 §5).

Not CI. Run on the ECS (or any host that can reach pico-api loopback) after
prod-update, with a synthetic tenant. Opens the produced bytes and asserts
content — status flags and file counts are not accepted as proof.

  PICO_OPENAI_PROXY_KEY=… python3 scripts/office-regress.py \
      --base http://127.0.0.1:18765 --membership regress-school:regress-member

Prints a JSON report and a markdown table (paste into the Issue). Exit 1 on any
blocking failure. Records three numbers per case: tool calls, wall seconds,
artifacts produced.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

DEFAULT_TIMEOUT_S = 420.0
FIXTURES = Path(__file__).resolve().parent.parent / "testdata" / "office-regress"


@dataclass
class CaseResult:
    case: str
    ok: bool = False
    tool_calls: int = 0
    wall_s: float = 0.0
    artifacts: int = 0
    notes: list[str] = field(default_factory=list)
    artifact_sha: dict[str, str] = field(default_factory=dict)


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

    def chat(self, conversation_id: str, text: str, *, on_first_delta=None) -> tuple[str, float]:
        """Stream a turn; return (assistant_text, wall_s)."""
        body = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "user", "content": text}],
        }
        started = time.perf_counter()
        out: list[str] = []
        first = True
        with self.client.stream(
            "POST",
            f"{self.base}/v1/chat/completions",
            headers={**self.headers, "X-Conversation-Id": conversation_id, "Accept": "text/event-stream"},
            json=body,
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
                        if first and on_first_delta:
                            first = False
                            on_first_delta()
        return "".join(out), time.perf_counter() - started

    def tasks(self, conversation_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(
            f"{self.base}/v1/tasks", headers=self.headers, params={"conversation_id": conversation_id}
        )
        resp.raise_for_status()
        return list(resp.json().get("tasks") or [])

    def runs(self, task_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(f"{self.base}/v1/tasks/{task_id}/runs", headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return list(data.get("runs") or data or [])

    def events(self, run_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(f"{self.base}/v1/runs/{run_id}/events", headers=self.headers)
        resp.raise_for_status()
        return list(resp.json().get("events") or [])

    def run(self, run_id: str) -> dict[str, Any]:
        resp = self.client.get(f"{self.base}/v1/runs/{run_id}", headers=self.headers)
        resp.raise_for_status()
        return dict(resp.json().get("run") or {})

    def cancel_active(self, task_id: str) -> dict[str, Any]:
        resp = self.client.post(f"{self.base}/v1/tasks/{task_id}/cancel-active", headers=self.headers)
        return resp.json() if resp.content else {"status_code": resp.status_code}

    def artifacts(self, conversation_id: str) -> list[dict[str, Any]]:
        resp = self.client.get(
            f"{self.base}/v1/artifacts", headers=self.headers, params={"conversation_id": conversation_id}
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


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()[:16]


def _tool_calls(pico: Pico, conversation_id: str) -> tuple[int, str]:
    total = 0
    status = "?"
    for task in pico.tasks(conversation_id):
        latest = task.get("latest_run") or {}
        if latest.get("id"):
            status = str(latest.get("status") or status)
            total += sum(1 for e in pico.events(latest["id"]) if str(e.get("kind") or e.get("type") or "") == "tool.call")
    return total, status


PRODUCED_KINDS = {"xlsx", "docx", "pptx", "html"}


def _produced(arts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Model-written files only. Uploads land as edu_office / edu_excerpt / kb_text.
    Same title as the original is the product rule (同名替换), so filter by kind."""
    return [a for a in arts if str(a.get("kind") or "").lower() in PRODUCED_KINDS]


def _latest_by_suffix(arts: list[dict[str, Any]], suffix: str) -> dict[str, Any] | None:
    matches = [a for a in arts if str(a.get("title") or "").lower().endswith(suffix)]
    if not matches:
        return None
    return max(matches, key=lambda a: str(a.get("created_at") or ""))


# --- fixtures -----------------------------------------------------------------


def make_gradebook() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "成绩"
    ws.append(["姓名", "平时", "期末", "总分"])
    for name, a, b in [("甲", 88, 92), ("乙", 75, 80), ("丙", 91, 85), ("丁", 60, 72), ("戊", 83, 79), ("己", 95, 97)]:
        ws.append([name, a, b, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ROSTER_ROWS = [
    ("张一", "2401", "A"), ("李二", "2402", "A"), ("王三", "2403", "B"), ("赵四", "2404", "C"),
    ("孙五", "2405", "A"), ("周六", "2406", "B"), ("吴七", "2407", "C"), ("郑八", "2408", "A"),
    ("冯九", "2409", "B"), ("陈十", "2410", "A"),
]


def make_roster() -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["姓名", "学号", "组别"])
    w.writerows(ROSTER_ROWS)
    return buf.getvalue().encode("utf-8")


def roster_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for _, _, g in ROSTER_ROWS:
        out[g] = out.get(g, 0) + 1
    return out


# --- cases --------------------------------------------------------------------


def case_t1(pico: Pico, stamp: str) -> CaseResult:
    from openpyxl import load_workbook

    res = CaseResult(case="T1a/T1b")
    cid = f"regress-t1-{stamp}"
    pico.upload(cid, "gradebook.xlsx", make_gradebook())
    # Name the column, not just the range: a bare "D2:D7" once made the model stop and
    # ask whether D was 期末 or 总分 (correct behaviour, but a false negative here).
    _, wall = pico.chat(
        cid,
        "gradebook.xlsx 在附件里。表头是 姓名/平时/期末/总分。"
        "把总分列 D2:D7 写成期末40%加平时60%的公式，保存为 xlsx。",
    )
    res.wall_s += wall
    produced = _produced(pico.artifacts(cid))
    res.artifacts = len(produced)
    latest = _latest_by_suffix(produced, ".xlsx")
    if not latest:
        res.notes.append("T1a: no new xlsx artifact")
        res.tool_calls, _ = _tool_calls(pico, cid)
        return res
    raw = pico.download(latest["id"])
    res.artifact_sha[latest["title"]] = _sha(raw)
    ws = load_workbook(io.BytesIO(raw)).active
    ok_a = True
    for r in range(2, 8):
        v = ws[f"D{r}"].value
        if not (isinstance(v, str) and v.startswith("=") and f"B{r}" in v and f"C{r}" in v):
            ok_a = False
            res.notes.append(f"T1a: D{r}={v!r} is not a B/C formula")
    if ws["A2"].value != "甲" or ws["B2"].value != 88 or ws["C2"].value != 92:
        ok_a = False
        res.notes.append("T1a: original A/B/C values changed")
    # T1b — second round, same conversation
    _, wall2 = pico.chat(cid, "把标题改成「三年二班成绩」，D 列公式别丢。")
    res.wall_s += wall2
    produced2 = _produced(pico.artifacts(cid))
    res.artifacts = len(produced2)
    latest2 = _latest_by_suffix(produced2, ".xlsx")
    ok_b = False
    if latest2:
        raw2 = pico.download(latest2["id"])
        res.artifact_sha[latest2["title"] + "#2"] = _sha(raw2)
        wb2 = load_workbook(io.BytesIO(raw2))
        blob = json.dumps([[str(c.value) for c in row] for ws2 in wb2.worksheets for row in ws2.iter_rows(max_row=3)], ensure_ascii=False)
        titled = "三年二班" in blob or any("三年二班" in (s.title or "") for s in wb2.worksheets) or "三年二班" in str(latest2.get("title"))
        d2 = wb2.active["D2"].value
        keeps = isinstance(d2, str) and d2.startswith("=")
        ok_b = titled and keeps
        if not titled:
            res.notes.append("T1b: title 三年二班 not found")
        if not keeps:
            res.notes.append(f"T1b: D2={d2!r} formula lost")
    else:
        res.notes.append("T1b: no second xlsx")
    res.tool_calls, _ = _tool_calls(pico, cid)
    res.ok = ok_a and ok_b
    return res


def case_t2(pico: Pico, stamp: str) -> CaseResult:
    from docx import Document
    from openpyxl import load_workbook

    res = CaseResult(case="T2")
    cid = f"regress-t2-{stamp}"
    pico.upload(cid, "roster.csv", make_roster())
    _, wall = pico.chat(
        cid,
        "roster.csv 在附件里。用这个 CSV 做两份东西：1) 按组别汇总人数的 xlsx；2) 一页说明 Word，点名各组人数。不要网页。",
    )
    res.wall_s = wall
    produced = _produced(pico.artifacts(cid))
    res.artifacts = len(produced)
    expect = roster_counts()
    xlsx = _latest_by_suffix(produced, ".xlsx")
    docx = _latest_by_suffix(produced, ".docx")
    ok = True
    if not xlsx:
        ok = False
        res.notes.append("T2: no xlsx")
    else:
        raw = pico.download(xlsx["id"])
        res.artifact_sha[xlsx["title"]] = _sha(raw)
        cells: dict[str, int] = {}
        for ws in load_workbook(io.BytesIO(raw), data_only=False).worksheets:
            for row in ws.iter_rows(values_only=True):
                vals = [v for v in row if v is not None]
                for i, v in enumerate(vals):
                    if isinstance(v, str) and v.strip() in expect and i + 1 < len(vals):
                        nxt = vals[i + 1]
                        try:
                            cells[v.strip()] = int(nxt)
                        except (TypeError, ValueError):
                            pass
        for g, n in expect.items():
            if cells.get(g) != n:
                ok = False
                res.notes.append(f"T2 xlsx: group {g} expected {n} got {cells.get(g)}")
    if not docx:
        ok = False
        res.notes.append("T2: no docx")
    else:
        raw = pico.download(docx["id"])
        res.artifact_sha[docx["title"]] = _sha(raw)
        d = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in d.paragraphs)
        for t in d.tables:
            for row in t.rows:
                text += "\n" + " ".join(c.text for c in row.cells)
        for g, n in expect.items():
            if g not in text or str(n) not in text:
                ok = False
                res.notes.append(f"T2 docx: group {g}/{n} not named")
    if any(str(a.get("title") or "").lower().endswith(".html") for a in produced):
        res.notes.append("T2: an HTML was produced although 不要网页 (observation)")
    res.tool_calls, _ = _tool_calls(pico, cid)
    res.ok = ok
    return res


def case_t3(pico: Pico, stamp: str) -> CaseResult:
    import re

    from pptx import Presentation

    res = CaseResult(case="T3-files")
    cid = f"regress-t3-{stamp}"
    _, wall = pico.chat(cid, "做一页离线可开的 HTML 介绍潮汐，再做一个 3 页的 PPT 提纲。")
    res.wall_s = wall
    arts = _produced(pico.artifacts(cid))
    res.artifacts = len(arts)
    html = _latest_by_suffix(arts, ".html")
    pptx = _latest_by_suffix(arts, ".pptx")
    ok = True
    if not html:
        ok = False
        res.notes.append("T3: no html")
    else:
        raw = pico.download(html["id"]).decode("utf-8", errors="replace")
        res.artifact_sha[html["title"]] = _sha(raw.encode("utf-8"))
        if re.search(r"""(src|href)=["']https?://""", raw, re.IGNORECASE):
            ok = False
            res.notes.append("T3: html has http(s) external asset")
    if not pptx:
        ok = False
        res.notes.append("T3: no pptx")
    else:
        raw = pico.download(pptx["id"])
        res.artifact_sha[pptx["title"]] = _sha(raw)
        prs = Presentation(io.BytesIO(raw))
        if len(prs.slides) < 3:
            ok = False
            res.notes.append(f"T3: pptx has {len(prs.slides)} slides (<3)")
        titles = []
        for s in prs.slides:
            t = getattr(s.shapes, "title", None)
            titles.append((t.text if t is not None and t.has_text_frame else "").strip())
        if not any(titles):
            texts = [sh.text_frame.text for s in prs.slides for sh in s.shapes if getattr(sh, "has_text_frame", False)]
            if not any(t.strip() for t in texts):
                ok = False
                res.notes.append("T3: pptx has no visible text")
    res.tool_calls, _ = _tool_calls(pico, cid)
    res.ok = ok
    return res


def case_t4(pico: Pico, stamp: str) -> CaseResult:
    res = CaseResult(case="T4-cancel")
    cid = f"regress-t4-{stamp}"
    pico.upload(cid, "gradebook.xlsx", make_gradebook())
    before = len(_produced(pico.artifacts(cid)))
    cancelled: dict[str, Any] = {}

    def stop_soon() -> None:
        time.sleep(3.0)
        for _ in range(20):
            tasks = pico.tasks(cid)
            if tasks:
                cancelled["resp"] = pico.cancel_active(tasks[0]["id"])
                cancelled["task_id"] = tasks[0]["id"]
                return
            time.sleep(0.5)

    t = threading.Thread(target=stop_soon, daemon=True)
    started = time.perf_counter()
    t.start()
    try:
        pico.chat(
            cid,
            "gradebook.xlsx 在附件里。表头是 姓名/平时/期末/总分。"
            "把总分列 D2:D7 写成期末40%加平时60%的公式，再把每个人的评语写成一段话，保存为 xlsx。",
        )
    except httpx.HTTPError as exc:
        res.notes.append(f"T4: stream ended with {type(exc).__name__} (acceptable on cancel)")
    t.join(timeout=30)
    res.wall_s = time.perf_counter() - started
    time.sleep(2.0)
    after = _produced(pico.artifacts(cid))
    res.artifacts = len(after) - before
    status = "?"
    if cancelled.get("task_id"):
        for run in pico.runs(cancelled["task_id"]):
            status = str(run.get("status") or status)
    res.notes.append(f"T4: run status={status} cancel={json.dumps(cancelled.get('resp'), ensure_ascii=False)[:120]}")
    res.tool_calls, _ = _tool_calls(pico, cid)
    res.ok = status in {"cancelled", "cancelling"} and res.artifacts == 0
    if res.artifacts:
        res.notes.append(f"T4: {res.artifacts} artifact(s) landed after Stop")
    return res


CASES = {"t1": case_t1, "t2": case_t2, "t3": case_t3, "t4": case_t4}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=os.environ.get("PICO_BASE") or "http://127.0.0.1:18765")
    ap.add_argument("--key", default=os.environ.get("PICO_OPENAI_PROXY_KEY") or "")
    ap.add_argument("--membership", default=os.environ.get("PICO_REGRESS_MEMBERSHIP") or "regress-school:regress-member")
    ap.add_argument("--model", default=os.environ.get("PICO_REGRESS_MODEL") or "pico-fast")
    ap.add_argument("--cases", default="t1,t2,t3,t4")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--json", default="", help="write JSON report here")
    args = ap.parse_args()
    if not args.key:
        print("PICO_OPENAI_PROXY_KEY / --key required", file=sys.stderr)
        return 2
    pico = Pico(args.base, args.key, args.membership, args.model, args.timeout)
    stamp = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    results: list[CaseResult] = []
    for name in [c.strip().lower() for c in args.cases.split(",") if c.strip()]:
        fn = CASES.get(name)
        if not fn:
            print(f"unknown case {name}", file=sys.stderr)
            return 2
        try:
            results.append(fn(pico, stamp))
        except Exception as exc:  # noqa: BLE001 — report, do not hide
            results.append(CaseResult(case=name.upper(), ok=False, notes=[f"exception: {type(exc).__name__}: {exc}"]))
    report = {
        "base": args.base,
        "model": args.model,
        "membership": args.membership,
        "stamp": stamp,
        "results": [r.__dict__ for r in results],
        "pass": all(r.ok for r in results),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("| case | ok | tool calls | wall s | artifacts | notes |")
    print("|---|---|---:|---:|---:|---|")
    for r in results:
        print(f"| {r.case} | {'✅' if r.ok else '❌'} | {r.tool_calls} | {r.wall_s:.1f} | {r.artifacts} | {'; '.join(r.notes)[:200]} |")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
