#!/usr/bin/env python3
"""T1 two rounds + T2 against isolated pico-api (PICO_WORKENV=pi). Never live 18765."""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

T1_R1 = "把 D2:D7 写成期末40%加平时60%的公式，保存为 xlsx。"
T1_R2 = "把标题改成「三年二班成绩」，D 列公式别丢。"
T2 = "用这个 CSV 做两份东西：1) 按组别汇总人数的 xlsx；2) 一页说明 Word，点名各组人数。不要网页。"
T3 = (
    "做两份可打开的文件：page.html（断网也能开，不要 CDN）"
    "和 slides.pptx（至少 3 页，每页标题看得见）。"
)
CONVO_T1 = "t1-api"
CONVO_T2 = "t2-api"
CONVO_T3 = "t3-api"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
PPT_NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}


def _req(
    method: str,
    url: str,
    token: str | None,
    body: dict[str, Any] | None = None,
    timeout: float = 30,
) -> tuple[int, Any, bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            parsed: Any
            if (resp.headers.get("Content-Type") or "").startswith("application/json"):
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            else:
                parsed = {}
            return int(resp.status), parsed, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:400].decode("utf-8", errors="replace")}
        return int(exc.code), parsed, raw


def _token(base: str) -> str:
    code, tok, _ = _req(
        "POST",
        base + "/v1/dev/token",
        None,
        {"school_id": "school-poc", "membership_id": "member-poc"},
    )
    if code != 200:
        raise SystemExit(json.dumps({"error": "token", "code": code, "body": tok}))
    return str(tok.get("access_token") or "")


def _wait_run(base: str, token: str, run_id: str, deadline: float) -> dict[str, Any]:
    last: dict[str, Any] = {}
    while time.time() < deadline:
        _code, body, _ = _req("GET", f"{base}/v1/runs/{run_id}", token)
        run = body.get("run") if isinstance(body, dict) else None
        last = run if isinstance(run, dict) else {}
        if str(last.get("status") or "") in {"succeeded", "failed", "cancelled"}:
            return last
        time.sleep(1.0)
    return last


def _create(base: str, token: str, *, title: str, prompt: str, convo: str) -> dict[str, Any]:
    code, created, _ = _req(
        "POST",
        base + "/v1/tasks",
        token,
        {"title": title, "prompt": prompt, "conversation_id": convo},
    )
    if code != 200:
        raise SystemExit(json.dumps({"error": "create", "code": code, "body": created}))
    return created if isinstance(created, dict) else {}


def _task_arts(base: str, token: str, task_id: str) -> list[dict[str, Any]]:
    _code, body, _ = _req("GET", f"{base}/v1/tasks/{task_id}", token)
    rows = body.get("artifacts") if isinstance(body, dict) else []
    return rows if isinstance(rows, list) else []


def _download(base: str, token: str, artifact_id: str) -> bytes:
    _code, _parsed, raw = _req(
        "GET",
        f"{base}/v1/artifacts/{artifact_id}/content?download=true",
        token,
        timeout=60,
    )
    return raw


def _xlsx_d2_and_title(blob: bytes) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok_zip": False,
        "d2": None,
        "title": None,
        "shared": [],
        "sheets": [],
        "inline": [],
    }
    if blob[:2] != b"PK":
        return out
    out["ok_zip"] = True
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                texts = [t.text or "" for t in si.findall(".//m:t", NS)]
                shared.append("".join(texts))
            out["shared"] = shared
            if shared:
                out["title"] = shared[0]
        if "xl/workbook.xml" in names:
            wb = ET.fromstring(zf.read("xl/workbook.xml"))
            sheets = [
                str(s.get("name") or "")
                for s in wb.findall("m:sheets/m:sheet", NS)
                if s.get("name")
            ]
            out["sheets"] = sheets
            if sheets and not out["title"]:
                out["title"] = sheets[0]
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in names:
            sheets = [n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            sheet_name = sheets[0] if sheets else ""
        if not sheet_name:
            return out
        sheet = ET.fromstring(zf.read(sheet_name))
        inline: list[str] = []
        for c in sheet.findall(".//m:c", NS):
            ref = c.get("r") or ""
            is_el = c.find("m:is", NS)
            if is_el is not None:
                texts = [t.text or "" for t in is_el.findall(".//m:t", NS)]
                joined = "".join(texts)
                if joined:
                    inline.append(joined)
            if ref != "D2":
                continue
            f = c.find("m:f", NS)
            v = c.find("m:v", NS)
            if f is not None and (f.text or "").strip():
                out["d2"] = (f.text or "").strip()
            elif v is not None:
                out["d2"] = (v.text or "").strip()
        out["inline"] = inline
        if not out["title"] and inline:
            out["title"] = inline[0]
    return out


def _docx_text(blob: bytes) -> str:
    if blob[:2] != b"PK":
        return ""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        if "word/document.xml" not in zf.namelist():
            return ""
        root = ET.fromstring(zf.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "".join(t.text or "" for t in root.findall(".//w:t", ns))


def _run_one(
    base: str,
    token: str,
    *,
    title: str,
    prompt: str,
    convo: str,
    wall: float,
) -> dict[str, Any]:
    t0 = time.time()
    created = _create(base, token, title=title, prompt=prompt, convo=convo)
    run = created.get("run") or {}
    task = created.get("task") or {}
    run_id = str(run.get("id") or "")
    task_id = str(task.get("id") or "")
    final = _wait_run(base, token, run_id, time.time() + wall)
    arts = _task_arts(base, token, task_id)
    files: list[dict[str, Any]] = []
    for art in arts:
        aid = str(art.get("id") or "")
        name = str(art.get("title") or "")
        kind = str(art.get("kind") or "")
        blob = _download(base, token, aid) if aid else b""
        item: dict[str, Any] = {
            "id": aid,
            "title": name,
            "kind": kind,
            "n": len(blob),
            "head": blob[:4].hex(),
        }
        low = name.lower()
        if low.endswith(".xlsx") or kind == "xlsx":
            item["xlsx"] = _xlsx_d2_and_title(blob)
        if low.endswith(".docx") or kind == "docx":
            item["docx_text"] = _docx_text(blob)[:400]
        if low.endswith(".html") or low.endswith(".htm") or kind == "html":
            item["html"] = _html_offline(blob)
        if low.endswith(".pptx") or kind == "pptx":
            item["pptx"] = _pptx_slides(blob)
        files.append(item)
    return {
        "run_id": run_id,
        "task_id": task_id,
        "conversation_id": convo,
        "status": final.get("status"),
        "error": final.get("error"),
        "seconds": round(time.time() - t0, 1),
        "n_artifacts": len(arts),
        "files": files,
    }


def _t1_pass(r1: dict[str, Any], r2: dict[str, Any]) -> bool:
    if r1.get("status") != "succeeded" or r2.get("status") != "succeeded":
        return False
    x1 = next((f.get("xlsx") for f in r1.get("files") or [] if f.get("xlsx")), None)
    x2 = next((f.get("xlsx") for f in r2.get("files") or [] if f.get("xlsx")), None)
    if not isinstance(x1, dict) or not isinstance(x2, dict):
        return False
    d1 = str(x1.get("d2") or "")
    d2 = str(x2.get("d2") or "")
    formula_ok = ("B2" in d1 and "C2" in d1 and ("0.6" in d1 or "60" in d1)) or d1.startswith("=")
    formula2_ok = d2.startswith("=") or ("B2" in d2)
    title = " ".join(
        [
            str(x2.get("title") or ""),
            " ".join(x2.get("shared") or []),
            " ".join(x2.get("sheets") or []),
            " ".join(x2.get("inline") or []),
        ]
    )
    title_ok = "三年二班" in title
    return bool(formula_ok and formula2_ok and title_ok)


def _t2_pass(row: dict[str, Any]) -> bool:
    if row.get("status") != "succeeded":
        return False
    has_xlsx = any((f.get("kind") == "xlsx") or str(f.get("title") or "").endswith(".xlsx") for f in row.get("files") or [])
    docx = next((f for f in row.get("files") or [] if (f.get("kind") == "docx") or str(f.get("title") or "").endswith(".docx")), None)
    text = str((docx or {}).get("docx_text") or "")
    # roster.csv: 红4 蓝3 绿3
    counts_ok = ("红" in text and "4" in text) and ("蓝" in text and "3" in text) and ("绿" in text and "3" in text)
    return has_xlsx and bool(docx) and counts_ok


def _html_offline(blob: bytes) -> dict[str, Any]:
    text = blob.decode("utf-8", errors="replace")
    low = text.lower()
    remote = (
        "https://" in low
        or "http://" in low
        or "//cdn" in low
        or "jsdelivr" in low
        or "unpkg.com" in low
    )
    return {
        "n": len(blob),
        "looks_html": "<html" in low or "<!doctype html" in low or "<body" in low,
        "remote": remote,
        "head": text[:120],
    }


def _pptx_slides(blob: bytes) -> dict[str, Any]:
    out: dict[str, Any] = {"ok_zip": False, "n_slides": 0, "titles": []}
    if blob[:2] != b"PK":
        return out
    out["ok_zip"] = True
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        slides = sorted(
            n
            for n in zf.namelist()
            if n.startswith("ppt/slides/slide") and n.endswith(".xml")
        )
        out["n_slides"] = len(slides)
        titles: list[str] = []
        a_ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        for name in slides[:8]:
            root = ET.fromstring(zf.read(name))
            texts = [t.text or "" for t in root.findall(".//a:t", a_ns)]
            joined = "".join(texts).strip()
            if joined:
                titles.append(joined[:80])
        out["titles"] = titles
    return out


def _t3_pass(row: dict[str, Any]) -> bool:
    if row.get("status") != "succeeded":
        return False
    html = next(
        (
            f
            for f in row.get("files") or []
            if (f.get("kind") == "html")
            or str(f.get("title") or "").lower().endswith((".html", ".htm"))
        ),
        None,
    )
    pptx = next(
        (
            f
            for f in row.get("files") or []
            if (f.get("kind") == "pptx") or str(f.get("title") or "").lower().endswith(".pptx")
        ),
        None,
    )
    if not isinstance(html, dict) or not isinstance(pptx, dict):
        return False
    h = html.get("html") if isinstance(html.get("html"), dict) else {}
    p = pptx.get("pptx") if isinstance(pptx.get("pptx"), dict) else {}
    html_ok = bool(h.get("looks_html")) and not bool(h.get("remote")) and int(h.get("n") or 0) >= 32
    pptx_ok = bool(p.get("ok_zip")) and int(p.get("n_slides") or 0) >= 3 and len(p.get("titles") or []) >= 1
    return html_ok and pptx_ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:18775")
    parser.add_argument("--out", default="/tmp/workenv-poc/pico-api-t12.json")
    parser.add_argument("--wall", type=float, default=240)
    parser.add_argument("--suite", choices=("t1", "t2", "t3", "all"), default="all")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    code, health, _ = _req("GET", base + "/health", None)
    if code != 200 or health.get("workenv_mode") != "pi":
        print(json.dumps({"error": "health", "code": code, "body": health}, ensure_ascii=False))
        return 2
    token = _token(base)
    t1r1: dict[str, Any] | None = None
    t1r2: dict[str, Any] | None = None
    t2: dict[str, Any] | None = None
    t3: dict[str, Any] | None = None
    if args.suite in {"t1", "all"}:
        t1r1 = _run_one(base, token, title="t1-r1", prompt=T1_R1, convo=CONVO_T1, wall=args.wall)
        t1r2 = _run_one(base, token, title="t1-r2", prompt=T1_R2, convo=CONVO_T1, wall=args.wall)
    if args.suite in {"t2", "all"}:
        t2 = _run_one(base, token, title="t2", prompt=T2, convo=CONVO_T2, wall=args.wall)
    if args.suite in {"t3", "all"}:
        t3 = _run_one(base, token, title="t3-files", prompt=T3, convo=CONVO_T3, wall=args.wall)
    t1_ok = _t1_pass(t1r1, t1r2) if t1r1 is not None and t1r2 is not None else None
    t2_ok = _t2_pass(t2) if t2 is not None else None
    t3_ok = _t3_pass(t3) if t3 is not None else None
    report = {
        "health_workenv": health.get("workenv_mode"),
        "health_sha": health.get("git_sha"),
        "suite": args.suite,
        "t1r1": t1r1,
        "t1r2": t1r2,
        "t2": t2,
        "t3": t3,
        "t1_pass": t1_ok,
        "t2_pass": t2_ok,
        "t3_pass": t3_ok,
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    summary: dict[str, Any] = {"suite": args.suite, "workenv": health.get("workenv_mode")}
    if t1r1 is not None:
        summary["t1r1"] = {"status": t1r1.get("status"), "n": t1r1.get("n_artifacts"), "s": t1r1.get("seconds")}
        summary["t1r2"] = {"status": (t1r2 or {}).get("status"), "n": (t1r2 or {}).get("n_artifacts"), "s": (t1r2 or {}).get("seconds")}
        summary["t1_pass"] = t1_ok
    if t2 is not None:
        summary["t2"] = {"status": t2.get("status"), "n": t2.get("n_artifacts"), "s": t2.get("seconds")}
        summary["t2_pass"] = t2_ok
    if t3 is not None:
        summary["t3"] = {"status": t3.get("status"), "n": t3.get("n_artifacts"), "s": t3.get("seconds")}
        summary["t3_pass"] = t3_ok
    print(json.dumps(summary, ensure_ascii=False))
    if args.suite == "t1":
        return 0 if t1_ok else 1
    if args.suite == "t2":
        return 0 if t2_ok else 1
    if args.suite == "t3":
        return 0 if t3_ok else 1
    return 0 if t1_ok and t2_ok and t3_ok else 1


if __name__ == "__main__":
    sys.exit(main())
