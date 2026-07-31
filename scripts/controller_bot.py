#!/usr/bin/env python3
"""Pico Controller Bot — poll GitHub and advance yellow/FAST work without chat Grok.

Designed for:
  - GitHub Actions schedule (7x24)
  - ECS cron: python scripts/controller_bot.py poll

Does NOT replace human/Grok for RISK:红. Does not deploy production (E3 does).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

REPO = os.environ.get("GITHUB_REPOSITORY", "juanwan99/pico")
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
AUTO_MERGE = os.environ.get("CONTROLLER_AUTO_MERGE", "0").lower() in {"1", "true", "yes"}
DRY_RUN = os.environ.get("CONTROLLER_DRY_RUN", "0").lower() in {"1", "true", "yes"}
LOG_ISSUE_TITLE = "[controller-bot] poll log"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")


def _headers() -> dict[str, str]:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN/GH_TOKEN required")
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "pico-controller-bot",
    }


def api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = path if path.startswith("http") else f"{API}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {err[:500]}") from e


def gh_rest(path: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    return api(method, path, body)


@dataclass
class PRInfo:
    number: int
    title: str
    draft: bool
    head_sha: str
    html_url: str
    body: str
    labels: list[str]


def list_open_prs() -> list[PRInfo]:
    items = gh_rest(f"/repos/{REPO}/pulls?state=open&per_page=50")
    out: list[PRInfo] = []
    for p in items or []:
        out.append(
            PRInfo(
                number=int(p["number"]),
                title=p.get("title") or "",
                draft=bool(p.get("draft")),
                head_sha=(p.get("head") or {}).get("sha") or "",
                html_url=p.get("html_url") or "",
                body=p.get("body") or "",
                labels=[str(x.get("name") or "") for x in (p.get("labels") or [])],
            )
        )
    return out


def pr_comments(n: int) -> list[str]:
    comments = gh_rest(f"/repos/{REPO}/issues/{n}/comments?per_page=100") or []
    return [c.get("body") or "" for c in comments]


def combined_text(pr: PRInfo) -> str:
    return "\n".join([pr.body, *pr_comments(pr.number)])


def is_red(text: str) -> bool:
    return bool(
        re.search(r"RISK\s*:\s*红", text, re.IGNORECASE)
        or re.search(r"RISK\s*:\s*red", text, re.IGNORECASE)
    )


def is_yellow_fast(text: str) -> bool:
    yellow = bool(re.search(r"RISK\s*:\s*黄", text, re.IGNORECASE) or re.search(r"RISK\s*:\s*yellow", text, re.IGNORECASE))
    fast = "SPRINT-FAST" in text or re.search(r"\bFAST\s*:", text) is not None
    # docs-only heuristic
    docs = bool(re.search(r"^docs\b", text.split("\n")[0] if text else "", re.IGNORECASE))
    return (yellow and fast) or (docs and "docs:" in text.lower())


def has_candidate(text: str) -> bool:
    return "## CANDIDATE" in text or "CANDIDATE" in text


def ci_success(sha: str) -> bool | None:
    """Return True if all completed checks success; False if any failure; None if pending."""
    if not sha:
        return None
    runs = gh_rest(f"/repos/{REPO}/commits/{sha}/check-runs?per_page=50") or {}
    checks = runs.get("check_runs") or []
    # also status contexts
    status = gh_rest(f"/repos/{REPO}/commits/{sha}/status") or {}
    if not checks and status.get("state") in {"success", "failure", "pending"}:
        st = status.get("state")
        if st == "success":
            return True
        if st == "failure":
            return False
        return None
    if not checks:
        return None
    pending = False
    for c in checks:
        conclusion = (c.get("conclusion") or "").lower()
        cstatus = (c.get("status") or "").lower()
        name = c.get("name") or ""
        if cstatus != "completed":
            pending = True
            continue
        if conclusion in {"success", "neutral", "skipped"}:
            continue
        if conclusion in {"failure", "timed_out", "cancelled", "action_required"}:
            # ignore non-required noise if any
            if "controller-bot" in name.lower():
                continue
            return False
    if pending:
        return None
    return True


def comment_pr(n: int, body: str) -> None:
    if DRY_RUN:
        print(f"DRY comment #{n}: {body[:120]}...")
        return
    gh_rest(
        f"/repos/{REPO}/issues/{n}/comments",
        method="POST",
        body={"body": body},
    )


def merge_pr(n: int, sha: str) -> bool:
    if DRY_RUN:
        print(f"DRY merge #{n}")
        return True
    try:
        gh_rest(
            f"/repos/{REPO}/pulls/{n}/merge",
            method="PUT",
            body={
                "merge_method": "merge",
                "sha": sha,
                "commit_title": f"Merge PR #{n}: controller-bot yellow/FAST",
            },
        )
        return True
    except RuntimeError as e:
        print(f"merge failed #{n}: {e}", file=sys.stderr)
        return False


def find_or_create_log_issue() -> int:
    q = urllib.parse.quote(f'repo:{REPO} is:issue is:open in:title "{LOG_ISSUE_TITLE}"')
    res = gh_rest(f"/search/issues?q={q}&per_page=1") or {}
    items = res.get("items") or []
    if items:
        return int(items[0]["number"])
    if DRY_RUN:
        print("DRY create log issue")
        return 0
    created = gh_rest(
        f"/repos/{REPO}/issues",
        method="POST",
        body={
            "title": LOG_ISSUE_TITLE,
            "body": (
                "自动轮询日志（Controller Bot）。\n\n"
                "- 黄档 + FAST + CI 绿：可自动合（见 workflow 开关）\n"
                "- 红档：只提醒，不合\n"
                "- 不部署生产；部署仍归 E3\n"
                "- 对话总管休眠时仍由此 bot 推进\n"
            ),
            "labels": ["controller-bot"],
        },
    )
    return int(created["number"])


def post_log(issue_n: int, body: str) -> None:
    if not issue_n:
        print(body)
        return
    # avoid spam: only comment if last bot comment is older logic skipped — always append poll
    comment_pr(issue_n, body)


def poll() -> int:
    prs = list_open_prs()
    lines = [
        f"## CONTROLLER-BOT POLL · {_now()}",
        f"- repo: `{REPO}`",
        f"- auto_merge: `{AUTO_MERGE}` dry_run: `{DRY_RUN}`",
        f"- open_prs: {len(prs)}",
        "",
        "| PR | title | decision |",
        "|----|-------|----------|",
    ]
    merged = 0
    blocked_red = 0
    waiting_ci = 0
    need_human = 0

    for pr in prs:
        text = combined_text(pr)
        if pr.draft:
            lines.append(f"| #{pr.number} | {pr.title[:40]} | skip draft |")
            continue
        if is_red(text):
            blocked_red += 1
            lines.append(f"| #{pr.number} | {pr.title[:40]} | RED hold |")
            # nudge once-ish: short comment if no recent bot mark
            if "CONTROLLER-BOT" not in text[-2000:]:
                comment_pr(
                    pr.number,
                    "## CONTROLLER-BOT\nRISK:红 — 不合。请对话总管或业主审查。\n",
                )
            need_human += 1
            continue

        ci = ci_success(pr.head_sha)
        if ci is None:
            waiting_ci += 1
            lines.append(f"| #{pr.number} | {pr.title[:40]} | CI pending |")
            continue
        if ci is False:
            lines.append(f"| #{pr.number} | {pr.title[:40]} | CI fail |")
            if "CONTROLLER-BOT" not in text[-1500:]:
                comment_pr(
                    pr.number,
                    "## CONTROLLER-BOT\nCI 失败 — 不合。执行窗请修红。\n",
                )
            continue

        # CI green
        yellow_fast = is_yellow_fast(text) or pr.title.lower().startswith("docs:")
        if yellow_fast and AUTO_MERGE:
            # docs: merge on CI green; code: need CANDIDATE or explicit FAST marker
            ok_to_merge = (
                pr.title.lower().startswith("docs:")
                or has_candidate(text)
                or ("FAST" in text and not is_red(text))
            )
            if ok_to_merge and merge_pr(pr.number, pr.head_sha):
                merged += 1
                lines.append(f"| #{pr.number} | {pr.title[:40]} | **merged** |")
                comment_pr(
                    pr.number,
                    "## CONTROLLER-BOT\n已自动合并（黄/FAST 或 docs + CI 绿）。"
                    "部署请 E3 看 EXECUTION-QUEUE。\n",
                )
            else:
                lines.append(f"| #{pr.number} | {pr.title[:40]} | yellow ready, merge skipped |")
        elif yellow_fast and not AUTO_MERGE:
            lines.append(f"| #{pr.number} | {pr.title[:40]} | yellow ready (auto_merge off) |")
            if "CONTROLLER-BOT" not in text[-1500:]:
                comment_pr(
                    pr.number,
                    "## CONTROLLER-BOT\nCI 绿且像黄/FAST — `CONTROLLER_AUTO_MERGE` 关闭，未代合。"
                    "打开 workflow 开关或总管手合。\n",
                )
        else:
            lines.append(f"| #{pr.number} | {pr.title[:40]} | needs human/Grok |")
            need_human += 1

    lines.extend(
        [
            "",
            f"- merged: **{merged}**",
            f"- red_hold: {blocked_red}",
            f"- ci_pending: {waiting_ci}",
            f"- need_human: {need_human}",
            "",
            "context_reset: false（bot 不清理任何人会话）",
            "下一步：E3 部署 tip；验证窗读 VALIDATION-QUEUE。",
        ]
    )
    report = "\n".join(lines)
    print(report)
    try:
        issue_n = find_or_create_log_issue()
        post_log(issue_n, report)
        print(f"logged to issue #{issue_n}")
    except (RuntimeError, OSError, json.JSONDecodeError, urllib.error.URLError) as e:
        print(f"log issue failed: {e}", file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print("Usage: controller_bot.py poll")
        print("Env: GITHUB_TOKEN, CONTROLLER_AUTO_MERGE=0|1, CONTROLLER_DRY_RUN=0|1")
        return 2
    cmd = argv[1]
    if cmd == "poll":
        return poll()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
