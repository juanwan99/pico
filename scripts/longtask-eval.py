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

Coding cases (LC*) name the files to deliver (``expect.files``) and a hidden
checker (``expect.check``, testdata/longtask-eval/checks/). The checker runs the
delivered code in a throwaway container: workspace image, gVisor, no network.
A coding case passes only when every file landed and the checker passes.
Re-score saved files without a model: ``--check-dir DIR --cases LC1``.

Hard cases (LH*, ``--suite hard``) are graded the same way; they exist because
LT/LC saturated (13/13 on two models) and stopped telling models apart.

Load test (#1135): ``--parallel 20 --repeat 3 --spread 5`` runs every case 3×,
20 at once, each job its own synthetic member spread over 5 schools. Each
result records ``queued_max`` (most runs ever ahead of it in the runner's line;
-1 = never queued).

Extra-long cases (LX*, ``--suite xlong``, #1139) are built to overflow one context
window so Pi's official compaction has to fire mid-task; each result records
``compactions`` / ``compaction_failed`` and the turns they fired in. ``--suite all``
leaves them out (cost). A case may reuse another (``"base": "LX2"``) and add long
pasted text to some turns (``"pastes"``, #1152). ``expect.check.per_turn`` hands the
checker every turn's delivery under /w/out/turns/R01… so rules are checked turn by turn.
LX3 (#1151) is the office one: a Word letter, an Excel analysis and a PPT, revised
over fourteen turns, workbooks recalculated with LibreOffice before grading.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "testdata" / "longtask-eval"
CHECKS_DIR = CASES_DIR / "checks"
PRODUCED_KINDS = {"xlsx", "docx", "pptx", "html"}
SUITES = {"office": "LT", "coding": "LC", "hard": "LH", "xlong": "LX"}
DEFAULT_SUITES = ("office", "coding", "hard")


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
    queued_max: int = -1
    compactions: int = 0
    compaction_failed: int = 0
    compaction_turns: list[int] = field(default_factory=list)
    membership: str = ""
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

    def follow(self, conversation_id: str, timeout_s: float) -> float:
        """Stream dropped (pico-api restart, #1133): poll like the UI until no run is active."""
        started = time.perf_counter()
        while time.perf_counter() - started < timeout_s:
            time.sleep(10)
            try:
                active = [
                    t
                    for t in self.tasks(conversation_id)
                    if str((t.get("latest_run") or {}).get("status") or "") in {"queued", "preparing", "running"}
                ]
            except (httpx.TransportError, httpx.HTTPStatusError):
                continue  # API still coming back
            if not active:
                return time.perf_counter() - started
        raise httpx.ReadTimeout("run still active after stream drop")

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


def _resolve_base(case: dict[str, Any]) -> dict[str, Any]:
    """``base`` copies another case's turns and grading; ``pastes`` adds text to some turns."""
    if not case.get("base"):
        return case
    base = json.loads((CASES_DIR / f"{case['base']}.json").read_text(encoding="utf-8"))
    merged = {**base, **{k: v for k, v in case.items() if k not in ("base", "pastes")}}
    turns = [dict(t) for t in base["turns"]]
    for idx, paste in (case.get("pastes") or {}).items():
        turns[int(idx) - 1]["paste"] = paste
    merged["turns"] = turns
    return merged


def load_cases(suite: str = "all") -> list[dict[str, Any]]:
    prefixes = [SUITES[s] for s in DEFAULT_SUITES] if suite == "all" else [SUITES[suite]]
    cases = []
    for prefix in prefixes:
        for path in sorted(CASES_DIR.glob(f"{prefix}*.json")):
            cases.append(_resolve_base(json.loads(path.read_text(encoding="utf-8"))))
    return cases


def turn_prompt(turn: dict[str, Any]) -> str:
    """The turn's ask, then any pasted material after it (a teacher pasting a chat export)."""
    paste = turn.get("paste")
    if not paste:
        return str(turn["prompt"])
    sys.path.insert(0, str(CHECKS_DIR))
    import lx_chat

    text = lx_chat.chat(
        int(paste["seed"]),
        int(paste["chars"]),
        str(paste.get("start") or ""),
        cast=str(paste.get("cast") or "lx2"),
        extra=tuple(paste.get("extra") or ()),
    )
    return f"{turn['prompt']}\n\n{paste['lead']}\n\n{text}"


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


SUBJECTS6 = ["语文", "数学", "英语", "物理", "化学", "生物"]


def _grade_book() -> bytes:
    """LH2: 6 classes x 45 students x 6 subjects, 期中 + 期末, with real-sheet traps.

    Seeded, so the checker regenerates the same values. Traps: class names with
    stray spaces, 期末 rows shuffled, the same name in two classes, a student
    gone after 期中, 缺考 / 作废 / blank cells, IDs typed as text.
    """
    import random

    from openpyxl import Workbook

    rng = random.Random(2026)
    surnames = "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾"
    given = "伟芳娜敏静磊洋勇艳杰涛明超霞平刚桂英华玉兰红军辉鹏飞燕丽强"
    classes = [f"八年级{i}班" for i in range(1, 7)]
    ability = {c: rng.uniform(-6, 6) for c in classes}
    drift = {(c, s): rng.uniform(-5, 5) for c in classes for s in SUBJECTS6}
    students = []
    for ci, cls in enumerate(classes):
        for k in range(45):
            sid = f"2025{ci + 1}{k + 1:02d}"
            name = rng.choice(surnames) + rng.choice(given) + (rng.choice(given) if rng.random() < 0.6 else "")
            students.append((sid, name, cls, rng.gauss(72 + ability[cls], 9)))
    students[7] = (students[7][0], "王磊", students[7][2], students[7][3])
    students[100] = (students[100][0], "王磊", students[100][2], students[100][3])

    def mark(base: float, bump: float) -> float | str | None:
        r = rng.random()
        if r < 0.012:
            return "缺考"
        if r < 0.016:
            return None
        v = max(0.0, min(100.0, base + bump + rng.gauss(0, 7)))
        return round(v * 2) / 2

    wb = Workbook()
    header = ["班级", "学号", "姓名", *SUBJECTS6]
    mid = wb.active
    mid.title = "期中"
    mid.append(header)
    final_rows = []
    for i, (sid, name, cls, base) in enumerate(students):
        shown = cls + (" " if i % 17 == 3 else "")
        mid.append([shown, sid, name, *[mark(base, 0) for _ in SUBJECTS6]])
        if i == 150:
            continue
        row = [cls, sid, name, *[mark(base, drift[(cls, s)]) for s in SUBJECTS6]]
        if i % 53 == 11:
            row[3 + rng.randrange(6)] = "作废"
        if i % 23 == 5:
            row[0] = " " + cls
        final_rows.append(row)
    rng.shuffle(final_rows)
    fin = wb.create_sheet("期末")
    fin.append(header)
    for row in final_rows:
        fin.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _lx_records() -> bytes:
    """LX1: the checker rebuilds truth from the same module, so it lives in checks/."""
    sys.path.insert(0, str(CHECKS_DIR))
    import lx_corpus

    return lx_corpus.corpus_zip()


def _lx3(name: str):
    """LX3 attachments come from the checker's own truth module (#1151)."""

    def build() -> bytes:
        sys.path.insert(0, str(CHECKS_DIR))
        import lx3_data

        return {
            "final": lx3_data.final_book,
            "mid": lx3_data.mid_book,
            "notice": lx3_data.notice_docx,
            "fix1": lambda: lx3_data.fix_docx(1),
            "fix2": lambda: lx3_data.fix_docx(2),
        }[name]()

    return build


GENERATORS = {
    "triple_workbook": _triple_workbook,
    "grade_book": _grade_book,
    "lx_records": _lx_records,
    **{f"lx3_{n}": _lx3(n) for n in ("final", "mid", "notice", "fix1", "fix2")},
}


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
    if "runner refused" in low or "runner queue" in low:
        return "runner_busy"
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


def _run_events(
    pico: Pico, conversation_id: str, res: CaseResult | None = None, turn_of: dict[str, int] | None = None
) -> tuple[int, int, str, str, int]:
    tool_calls = 0
    steps = 0
    status = "?"
    error = ""
    queued_max = -1
    for task in pico.tasks(conversation_id):
        turn = (turn_of or {}).get(str(task.get("id") or ""))
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
            if res is not None and kind == "compaction.end":
                res.compactions += 1
                if turn:
                    res.compaction_turns.append(turn)
            if res is not None and kind == "compaction.failed":
                res.compaction_failed += 1
            if kind == "run.queued":
                ahead = (e.get("payload") or {}).get("ahead")
                if isinstance(ahead, int):
                    queued_max = max(queued_max, ahead)
    return tool_calls, steps, status, error, queued_max


def _zip_dir(rel: str) -> bytes:
    """Deterministic zip of a fixture project; entries sit under its folder name."""
    root = CASES_DIR / rel
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(f"{root.name}/{path.relative_to(root).as_posix()}", (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return buf.getvalue()


def _attachment_bytes(spec: dict[str, Any]) -> bytes:
    if spec.get("generate"):
        fn = GENERATORS[str(spec["generate"])]
        return fn()
    if spec.get("zip_dir"):
        return _zip_dir(str(spec["zip_dir"]))
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
    if expect.get("files") or expect.get("check"):
        return n + bool(expect.get("files")) + int((expect.get("check") or {}).get("max") or 0)
    return min(5, n)


def pass_bar(expect: dict[str, Any]) -> int:
    """3 points, or every check when a case has fewer than 3 (else it can never pass)."""
    return min(3, max_points(expect))


# Uploads land as edu_office / file / excerpts; the reply summary is doc.
# Workspace deliveries carry their extension as kind (py, zip, csv, html…).
NOT_DELIVERED_KINDS = {"edu_office", "edu_excerpt", "kb_text", "file", "doc"}


def _latest_by_title(arts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Delivered files only, newest per title."""
    out: dict[str, dict[str, Any]] = {}
    for a in sorted(arts, key=lambda a: str(a.get("created_at") or "")):
        title = os.path.basename(str(a.get("title") or ""))
        if title and str(a.get("kind") or "").lower() not in NOT_DELIVERED_KINDS:
            out[title] = a
    return out


def _unzip_into(raw: bytes, dest: Path) -> None:
    """Unpack a delivered zip; entries escaping ``dest`` are skipped."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for info in zf.infolist():
            name = info.filename
            if not info.flag_bits & 0x800:
                # Info-ZIP in the box writes UTF-8 names without the UTF-8 bit;
                # zipfile then reads them as cp437 mojibake (#1139 LX2).
                try:
                    name = name.encode("cp437").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            target = (dest / name).resolve()
            if info.is_dir() or not str(target).startswith(str(root) + os.sep):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))


def run_checker(
    case: dict[str, Any], out_dir: Path, res: CaseResult, image: str, runtime: str
) -> tuple[int, bool]:
    """Run the case's hidden checker on delivered files in a no-network container."""
    spec = case["expect"]["check"]
    with tempfile.TemporaryDirectory(prefix="lt-check-") as tmp:
        w = Path(tmp)
        shutil.copytree(out_dir, w / "out")
        for zpath in list((w / "out").rglob("*.zip")):
            try:
                _unzip_into(zpath.read_bytes(), zpath.with_suffix(""))
            except zipfile.BadZipFile:
                res.notes.append(f"bad zip {zpath.name}")
        (w / "in").mkdir()
        for turn in case.get("turns") or []:
            for att in turn.get("attachments") or []:
                (w / "in" / att["name"]).write_bytes(_attachment_bytes(att))
        shutil.copytree(CHECKS_DIR, w / "check")
        for path in w.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        w.chmod(0o755)
        cmd = [
            "docker", "run", "--rm", "--network", "none", "--runtime", runtime,
            "--memory", "1g", "--cpus", "1", "--pids-limit", "256", "--shm-size", "256m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-v", f"{w}:/w:ro", "-w", "/tmp", "--entrypoint", "",
            image, "timeout", "300", "python3", f"/w/check/{spec['script']}",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=420, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            res.notes.append(f"check: {type(exc).__name__}")
            return 0, False
    lines = (proc.stdout or "").strip().splitlines()
    try:
        verdict = json.loads(lines[-1])
    except (ValueError, IndexError):
        res.notes.append(f"check crashed rc={proc.returncode}: {' '.join((proc.stderr or '').split())[-200:]}")
        return 0, False
    res.notes += [f"check: {n}" for n in verdict.get("notes") or []]
    return int(verdict.get("points") or 0), bool(verdict.get("pass"))


def score_code(
    case: dict[str, Any],
    files: dict[str, bytes],
    res: CaseResult,
    image: str,
    runtime: str,
    turn_files: list[dict[str, bytes]] | None = None,
) -> None:
    """Coding case: required files landed + hidden checker passes."""
    expect = case.get("expect") or {}
    want = [str(f) for f in expect.get("files") or []]
    missing = [f for f in want if f not in files]
    points = 0
    if want:
        if missing:
            res.notes.append("missing files: " + ",".join(missing))
        else:
            points += 1
    passed = True
    if expect.get("check"):
        with tempfile.TemporaryDirectory(prefix="lt-out-") as tmp:
            for name, raw in files.items():
                (Path(tmp) / name).write_bytes(raw)
            for n, delivered in enumerate(turn_files or [], 1):
                tdir = Path(tmp) / "turns" / f"R{n:02d}"
                tdir.mkdir(parents=True)
                for name, raw in delivered.items():
                    (tdir / name).write_bytes(raw)
            got, passed = run_checker(case, Path(tmp), res, image, runtime)
        points += got
    res.auto_score = points
    res.max_score = max_points(expect)
    res.ok = not missing and passed


def score_case(
    case: dict[str, Any],
    arts: list[dict[str, Any]],
    pico: Pico,
    res: CaseResult,
    image: str = "",
    runtime: str = "",
    turn_arts: list[list[dict[str, Any]]] | None = None,
) -> None:
    expect = case.get("expect") or {}
    if expect.get("files") or expect.get("check"):
        latest = _latest_by_title(arts)
        res.artifacts = len(latest)
        res.artifact_kinds = sorted({str(a.get("kind") or "").lower() for a in latest.values() if a.get("kind")})
        files = {title: pico.download(a["id"]) for title, a in latest.items() if a.get("id")}
        turn_files = None
        if (expect.get("check") or {}).get("per_turn"):
            turn_files = [
                {title: pico.download(a["id"]) for title, a in _latest_by_title(new).items() if a.get("id")}
                for new in turn_arts or []
            ]
        score_code(case, files, res, image, runtime, turn_files)
        return
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


def run_case(pico: Pico, case: dict[str, Any], stamp: str, image: str = "", runtime: str = "") -> CaseResult:
    cid = f"longtask-{case['id'].lower()}-{stamp}"
    res = CaseResult(case=case["id"], title=case.get("title") or "", score_points=list(case.get("score_points") or []))
    timeout = float(case.get("timeout_s") or pico.timeout_s)
    seen_tasks: set[str] = set()
    seen_arts: set[str] = set()
    turn_of: dict[str, int] = {}
    turn_arts: list[list[dict[str, Any]]] = []
    try:
        for n, turn in enumerate(case.get("turns") or [], 1):
            for att in turn.get("attachments") or []:
                pico.upload(cid, att["name"], _attachment_bytes(att))
            t0 = time.perf_counter()
            try:
                _, wall = pico.chat(cid, turn_prompt(turn), timeout_s=timeout)
            except httpx.TimeoutException:
                raise
            except httpx.TransportError:
                pico.follow(cid, timeout)
                wall = time.perf_counter() - t0
                res.notes.append("stream dropped, followed run")
            res.wall_s += wall
            for task in pico.tasks(cid):
                tid = str(task.get("id") or "")
                if tid and tid not in seen_tasks:
                    seen_tasks.add(tid)
                    turn_of[tid] = n
            now = pico.artifacts(cid)
            turn_arts.append([a for a in now if str(a.get("id")) not in seen_arts])
            seen_arts |= {str(a.get("id")) for a in now}
        arts = pico.artifacts(cid)
        res.tool_calls, res.agent_steps, status, error, res.queued_max = _run_events(pico, cid, res, turn_of)
        res.fail_reason = _classify_fail(status, error)
        score_case(case, arts, pico, res, image, runtime, turn_arts)
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
        "| 例 | 标题 | ok | 自动分 | 失败原因 | 假绿 | 耗时 s | 工具 | 步 | 压缩 | 产物 | 备注 |",
        "|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        notes = "; ".join(r.notes)[:180]
        lines.append(
            f"| {r.case} | {r.title} | {'✅' if r.ok else '❌'} | {r.auto_score}/{r.max_score or 5} | "
            f"{r.fail_reason or '—'} | {'是' if r.fake_green else '—'} | {r.wall_s:.1f} | "
            f"{r.tool_calls} | {r.agent_steps} | "
            f"{r.compactions}{f'（败 {r.compaction_failed}）' if r.compaction_failed else ''}"
            f"{' @R' + '/R'.join(map(str, sorted(r.compaction_turns))) if r.compaction_turns else ''} | "
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
    ap.add_argument("--cases", default="", help="comma ids, default every case in --suite")
    ap.add_argument(
        "--suite", choices=["all", *SUITES], default="all", help="LT office, LC coding, LH hard, LX extra-long (not in all)"
    )
    ap.add_argument("--check-image", default="pico-workspace:v1", help="image coding checkers run in")
    ap.add_argument("--check-runtime", default="runsc", help="docker runtime for coding checkers")
    ap.add_argument(
        "--check-dir", default="", help="score these files as one LC case's delivery, no model"
    )
    ap.add_argument("--timeout", type=float, default=0.0, help="override per-case timeout_s")
    ap.add_argument("--json", default="", help="write JSON report here")
    ap.add_argument("--list", action="store_true", help="list cases and exit")
    ap.add_argument("--parallel", type=int, default=1, help="jobs at once (load test, #1135)")
    ap.add_argument("--repeat", type=int, default=1, help="run every case this many times")
    ap.add_argument(
        "--spread", type=int, default=0, help="one synthetic member per job, over N synthetic schools"
    )
    args = ap.parse_args()
    cases = load_cases(args.suite)
    if args.list:
        for c in cases:
            print(f"{c['id']}\t{c.get('timeout_s')}\t{c.get('title')}")
        return 0
    wanted = {x.strip().upper() for x in args.cases.split(",") if x.strip()}
    if wanted:
        cases = [c for c in cases if c["id"].upper() in wanted]
        missing = wanted - {c["id"].upper() for c in cases}
        if missing:
            print("unknown cases: " + ",".join(sorted(missing)), file=sys.stderr)
            return 2
    if args.check_dir:
        if len(cases) != 1:
            print("--check-dir needs exactly one --cases id", file=sys.stderr)
            return 2
        src = Path(args.check_dir)
        files = {p.name: p.read_bytes() for p in src.iterdir() if p.is_file()}
        res = CaseResult(case=cases[0]["id"], title=cases[0].get("title") or "")
        score_code(cases[0], files, res, args.check_image, args.check_runtime)
        print(json.dumps(res.__dict__, ensure_ascii=False, indent=2))
        return 0 if res.ok else 1
    if not args.key:
        print("PICO_OPENAI_PROXY_KEY / --key required", file=sys.stderr)
        return 2
    stamp = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    jobs = [case for _ in range(max(1, args.repeat)) for case in cases]
    tag = uuid.uuid4().hex[:6]

    def one_job(i: int, case: dict[str, Any]) -> CaseResult:
        membership = (
            f"load{tag}-s{i % args.spread}:load{tag}-m{i}" if args.spread > 0 else args.membership
        )
        pico = Pico(args.base, args.key, membership, args.model, args.timeout or 1800.0)
        if args.timeout:
            case = {**case, "timeout_s": args.timeout}
        try:
            print(f"START {case.get('id')}#{i} timeout_s={case.get('timeout_s')}", flush=True)
            one = run_case(pico, case, f"{stamp}-{i}", args.check_image, args.check_runtime)
            print(
                f"DONE {one.case}#{i} ok={one.ok} score={one.auto_score} wall_s={one.wall_s:.1f} "
                f"queued_max={one.queued_max} fail={one.fail_reason or '-'}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            one = CaseResult(
                case=case.get("id") or "?",
                title=case.get("title") or "",
                ok=False,
                fail_reason="other",
                notes=[f"exception: {type(exc).__name__}: {exc}"],
                score_points=list(case.get("score_points") or []),
            )
            print(f"DONE {one.case}#{i} ok=False exception={type(exc).__name__}", flush=True)
        one.membership = membership
        return one

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        results = list(pool.map(lambda pair: one_job(*pair), enumerate(jobs)))
    report = {
        "base": args.base,
        "model": args.model,
        "membership": args.membership,
        "stamp": stamp,
        "parallel": args.parallel,
        "jobs": len(jobs),
        "queued_jobs": sum(1 for r in results if r.queued_max >= 0),
        "runner_busy": sum(1 for r in results if r.fail_reason == "runner_busy"),
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
