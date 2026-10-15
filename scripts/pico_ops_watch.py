#!/usr/bin/env python3
"""pico#1273 · pico ops watch on the ECS host (pico-ops-watch.timer, every 5 min).

  pico_ops_watch.py check [--drill NAME]   run every check; mail when one goes bad, recovers,
                                           or is still bad 6 h later. --drill forces NAME bad once
                                           (mail subject says 演练, state untouched).
  pico_ops_watch.py report [--hours N]     failed / cancelled runs by cause (default 24 h)
  pico_ops_watch.py env-set K=V ... --card N --why TEXT
                                           edit /opt/pico/.env with a backup and a trail line
  pico_ops_watch.py env-record --card N --why TEXT
                                           write the trail for a change another tool just made

Checks: probe (public + local health), runs (failure rate, 60 min window, by cause),
upstream (New API 403 / 429 / 5xx per channel), disk (root ≥ 85 %), buildcache
(BuildKit private > 35 GB), env (.env changed without a trail line).
Host python3 stdlib only. Reads pico.db read-only through the api container.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("HOME", "/home/ops"))
STATE = Path(os.environ.get("PICO_OPS_STATE", HOME / "logs/pico-ops-watch.json"))
LOG = Path(os.environ.get("PICO_OPS_LOG", HOME / "logs/pico-ops-watch.log"))
ALERT_BIN = Path(os.environ.get("PICO_OPS_ALERT", HOME / "scripts/edu-backup-alert.py"))
PICO_ENV = Path(os.environ.get("PICO_OPS_ENV", "/opt/pico/.env"))
ENV_TRAIL = Path(os.environ.get("PICO_OPS_ENV_TRAIL", HOME / "pico-env-changes.log"))
ENV_SNAPSHOT = Path(os.environ.get("PICO_OPS_ENV_SNAPSHOT", HOME / "var/pico-ops/env.snapshot"))
API = os.environ.get("PICO_OPS_API_CONTAINER", "pico-pico-api-1")
NEWAPI = os.environ.get("PICO_OPS_NEWAPI_CONTAINER", "new-api")
PUBLIC = os.environ.get("PICO_OPS_PUBLIC_URL", "https://pico.aivia.asia")
LOCAL = os.environ.get("PICO_OPS_LOCAL_URL", "http://127.0.0.1:18765")

WINDOW_MIN = int(os.environ.get("PICO_OPS_RUNS_WINDOW_MIN", "60"))
RUNS_MIN_BAD = int(os.environ.get("PICO_OPS_RUNS_MIN_BAD", "4"))
RUNS_RATE = float(os.environ.get("PICO_OPS_RUNS_RATE", "0.3"))
UPSTREAM_MIN = int(os.environ.get("PICO_OPS_UPSTREAM_MIN", "5"))
# 85 % ≈ the 30 GB free floor the hourly builder prune keeps (edu-core DEPLOY-ECS #2699):
# past it, the prune can no longer hold the line.
DISK_PCT = float(os.environ.get("PICO_OPS_DISK_PCT", "85"))
BUILDCACHE_GB = float(os.environ.get("PICO_OPS_BUILDCACHE_GB", "35"))
PROBE_FAILS = 2  # consecutive rounds before "down": one blip during a deploy is not an outage
REMIND_H = 6

# First match wins. Kept coarse on purpose: the mail says what to look at, not a diagnosis.
CAUSES: list[tuple[str, str]] = [
    ("钥被停 / 无权限", r"API密钥已被暂停|permission_error|\b403\b"),
    ("上游限流 429", r"\b429\b|rate.?limit|too many requests"),
    ("上游 5xx / 连不上", r"\b50[0-4]\b|URLError|upstream_error|overloaded|could not be completed|connection"),
    ("模型不可用", r"模型不可用|model.*not.*(found|available)"),
    ("流断 / 空输出", r"finish_reason|empty model output"),
    ("没交出文件", r"没有可下载的真文件"),
    ("对话占用中", r"workspace_busy|还在运行"),
    ("无进展熔断", r"熔断|无有效进展"),
    ("超时", r"超时|timeout|timed out"),
    ("代码错误", r"Cannot read properties|Traceback|TypeError|KeyError|AttributeError"),
]


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def stamp() -> str:
    return now().isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"{stamp()} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sh(cmd: list[str], stdin: str | None = None, timeout: int = 60) -> str:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout, check=True).stdout


def mail(subject: str, body: str) -> str:
    if not ALERT_BIN.is_file():
        return "no alert script"
    r = subprocess.run(
        ["python3", str(ALERT_BIN), "--subject", subject, "--body", body],
        capture_output=True, text=True, timeout=600, check=False,
    )
    return (r.stdout or r.stderr).strip()[:200] or f"rc={r.returncode}"


def cause_of(error: str) -> str:
    for name, pat in CAUSES:
        if re.search(pat, error or "", re.IGNORECASE):
            return name
    return "其他"


# ---- checks: each returns (bad, one-line summary, detail) -------------------------------

def check_probe(state: dict) -> tuple[bool, str, str]:
    misses = []
    for url in (f"{PUBLIC}/health", f"{PUBLIC}/login", f"{LOCAL}/health"):
        try:
            with urllib.request.urlopen(url, timeout=12) as r:
                if r.status >= 400:
                    misses.append(f"{url} {r.status}")
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            misses.append(f"{url} {code or type(e).__name__}")
    streak = state.get("probe_streak", 0) + 1 if misses else 0
    state["probe_streak"] = streak
    if not misses:
        return False, "公网与本机 health 都通", ""
    where = "本机 pico-api" if any(LOCAL in m for m in misses) else "公网入口"
    return streak >= PROBE_FAILS, f"{where}连续 {streak} 轮不通", "\n".join(misses)


RUNS_SQL = r"""
import json, sqlite3, sys
c = sqlite3.connect("file:/app/data/pico.db?mode=ro", uri=True)
rows = c.execute(
    "select status, cancel_requested, coalesce(error,''), model from runs "
    "where coalesce(ended_at, created_at) >= datetime('now', ?) and status in ('succeeded','failed','cancelled')",
    (f"-{int(sys.argv[1])} minutes",)).fetchall()
print(json.dumps(rows))
"""


def fetch_runs(minutes: int) -> list[list]:
    out = sh(["docker", "exec", "-i", API, "python3", "-", str(minutes)], stdin=RUNS_SQL)
    return json.loads(out)


def summarize_runs(rows: list[list]) -> tuple[int, int, int, dict[str, list[str]]]:
    ok = bad = user_cancel = 0
    causes: dict[str, list[str]] = {}
    for status, cancel_requested, error, model in rows:
        if status == "succeeded":
            ok += 1
        elif status == "cancelled" and cancel_requested:
            user_cancel += 1
        else:
            bad += 1
            name = "系统取消" if status == "cancelled" else cause_of(error)
            causes.setdefault(name, []).append(f"{model}: {error[:120]}")
    return ok, bad, user_cancel, causes


def format_causes(causes: dict[str, list[str]]) -> str:
    lines = []
    for name, items in sorted(causes.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"  {name} ×{len(items)}  例：{items[0]}")
    return "\n".join(lines)


def check_runs(state: dict) -> tuple[bool, str, str]:
    ok, bad, user_cancel, causes = summarize_runs(fetch_runs(WINDOW_MIN))
    done = ok + bad
    rate = bad / done if done else 0.0
    summary = f"近 {WINDOW_MIN} 分钟 {done} 个任务失败 {bad}（{rate:.0%}），老师自己停 {user_cancel}"
    return bad >= RUNS_MIN_BAD and rate >= RUNS_RATE, summary, format_causes(causes)


GIN = re.compile(r"^\[GIN\] (\S+ - \S+) \| relay \| \S+ \| (\d{3}) \|")
ERR = re.compile(r"^\[ERR\] .*?channel error \(channel #(\d+), status code: (\d{3})\): ?(.*)$")


def check_upstream(state: dict) -> tuple[bool, str, str]:
    since = state.get("upstream_since") or (now() - dt.timedelta(minutes=10)).isoformat(timespec="seconds")
    state["upstream_since"] = stamp()
    r = subprocess.run(
        ["docker", "logs", "--since", since, NEWAPI], capture_output=True, text=True, timeout=60, check=False
    )
    codes: dict[str, int] = {}
    reasons: dict[tuple[str, str, str], int] = {}
    for line in (r.stdout + r.stderr).splitlines():
        m = GIN.match(line)
        if m and m.group(2) in ("403", "429") or (m and m.group(2).startswith("5")):
            codes[m.group(2)] = codes.get(m.group(2), 0) + 1
        e = ERR.match(line)
        if e:
            key = (e.group(1), e.group(2), e.group(3)[:60])
            reasons[key] = reasons.get(key, 0) + 1
    n403 = codes.get("403", 0)
    total = sum(codes.values())
    summary = "上游 " + (" ".join(f"{k}×{v}" for k, v in sorted(codes.items())) or "无 403/429/5xx")
    detail = "\n".join(f"  渠道 #{ch} {code} ×{n}：{msg}" for (ch, code, msg), n in
                       sorted(reasons.items(), key=lambda kv: -kv[1]))
    # 403 = a key was stopped or banned: a person has to act, so one is enough.
    return n403 > 0 or total >= UPSTREAM_MIN, summary, detail


def check_disk(state: dict) -> tuple[bool, str, str]:
    u = shutil.disk_usage("/")
    pct = u.used / (u.used + u.free) * 100  # same as df Use% (root-reserved blocks left out)
    was_bad = bool(state.get("checks", {}).get("disk", {}).get("bad"))
    bad = pct >= DISK_PCT or (was_bad and pct >= DISK_PCT - 2)  # 2-point band: no flapping mail
    return bad, f"根盘 {pct:.0f}%（剩 {u.free / 1e9:.0f} GB）", ""


def check_buildcache(state: dict) -> tuple[bool, str, str]:
    # `docker system df` counts layers shared with images; only "Private" is freed by a prune.
    out = sh(["docker", "buildx", "du"], timeout=120)
    m = re.search(r"Private:\s+([\d.]+)\s*([KMGT]?B)", out)
    unit = {"B": 1e-9, "KB": 1e-6, "MB": 1e-3, "GB": 1, "TB": 1e3}
    gb = float(m.group(1)) * unit[m.group(2)] if m else 0.0
    return gb > BUILDCACHE_GB, f"构建缓存独占 {gb:.1f} GB（上限 {BUILDCACHE_GB:.0f}）", ""


# ---- .env trail -------------------------------------------------------------------------

SECRET = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|PASS|PRIVATE|CREDENTIAL", re.IGNORECASE)


def parse_env(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v
    return out


def shown(key: str, value: str | None) -> str:
    if value is None:
        return "unset"
    if SECRET.search(key):
        return "sha:" + hashlib.sha256(value.encode()).hexdigest()[:8]
    return value if len(value) <= 80 else value[:77] + "..."


def env_diff(old: dict[str, str], new: dict[str, str]) -> list[str]:
    out = []
    for k in sorted(set(old) | set(new)):
        if old.get(k) != new.get(k):
            out.append(f"{k}: {shown(k, old.get(k))} -> {shown(k, new.get(k))}")
    return out


def record_env(card: str, why: str, by: str) -> list[str]:
    """Diff snapshot → current .env, append one trail line, move the snapshot forward."""
    cur = PICO_ENV.read_text(encoding="utf-8")
    old = ENV_SNAPSHOT.read_text(encoding="utf-8") if ENV_SNAPSHOT.is_file() else None
    changes = env_diff(parse_env(old), parse_env(cur)) if old is not None else []
    if changes:
        with ENV_TRAIL.open("a", encoding="utf-8") as f:
            f.write(f"{now().strftime('%Y-%m-%d %H:%M:%S %z')} {card or '-'} {PICO_ENV} [{by}] "
                    f"{'; '.join(changes)}. Why: {why}\n")
    ENV_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    ENV_SNAPSHOT.write_text(cur, encoding="utf-8")
    os.chmod(ENV_SNAPSHOT, 0o600)
    return changes


def check_env(state: dict) -> tuple[bool, str, str]:
    if not ENV_SNAPSHOT.is_file():
        record_env("", "", "watch")  # first run: take the baseline
        return False, ".env 基线已记", ""
    changes = record_env("", "没有走 env-set / env-record，谁改的、为什么待补", "watch:UNLOGGED")
    if not changes:
        return False, ".env 无未记录改动", ""
    return True, f".env 有 {len(changes)} 项改动没留原因（已补记到 {ENV_TRAIL.name}）", "\n".join(changes)


CHECKS = {
    "probe": check_probe,
    "runs": check_runs,
    "upstream": check_upstream,
    "disk": check_disk,
    "buildcache": check_buildcache,
    "env": check_env,
}


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cmd_check(drill: str | None) -> int:
    state = load_state()
    checks = state.setdefault("checks", {})
    fired, recovered, lines = [], [], []
    for name, fn in CHECKS.items():
        try:
            bad, summary, detail = fn(state)
        except Exception as e:  # noqa: BLE001 — a broken check is itself worth a mail
            bad, summary, detail = True, f"检查本身出错：{type(e).__name__}", str(e)[:300]
        if drill == name:
            bad, summary = True, f"【演练】{summary}"
        prev = checks.get(name, {})
        lines.append(f"{name}: {'BAD' if bad else 'ok'} · {summary}")
        if drill == name:
            fired.append((name, summary, detail))
            continue
        entry = {"bad": bad, "summary": summary, "since": prev.get("since") if prev.get("bad") == bad else stamp(),
                 "last_mail": prev.get("last_mail")}
        if bad:
            last = prev.get("last_mail")
            due = not prev.get("bad") or not last or \
                now() - dt.datetime.fromisoformat(last) > dt.timedelta(hours=REMIND_H)
            if due:
                fired.append((name, summary, detail))
                entry["last_mail"] = stamp()
        elif prev.get("bad"):
            recovered.append((name, summary))
            entry["last_mail"] = None
        checks[name] = entry
    log(" | ".join(lines))
    if fired or recovered:
        tag = "演练" if drill else ("告警" if fired else "恢复")
        names = ", ".join(n for n, *_ in fired) or ", ".join(n for n, _ in recovered)
        body = []
        for name, summary, detail in fired:
            body.append(f"[{name}] {summary}\n{detail}".rstrip())
        for name, summary in recovered:
            body.append(f"[{name}] 恢复：{summary}")
        body.append("\n全部：\n" + "\n".join(lines))
        body.append(f"看：{LOG}、python3 /opt/pico/scripts/pico_ops_watch.py report")
        log(f"mail {tag} {names}: {mail(f'[pico] {tag}：{names}', chr(10).join(body))}")
    if not drill:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_report(hours: int) -> int:
    ok, bad, user_cancel, causes = summarize_runs(fetch_runs(hours * 60))
    done = ok + bad
    print(f"近 {hours} 小时：{done} 个任务，成功 {ok}，失败 / 系统取消 {bad}"
          f"（{(bad / done if done else 0):.0%}），老师自己停 {user_cancel}")
    print(format_causes(causes) or "  （无失败）")
    return 0


def cmd_env_set(pairs: list[str], card: str, why: str) -> int:
    text = PICO_ENV.read_text(encoding="utf-8")
    pending = record_env("", "没有走 env-set / env-record，谁改的、为什么待补", "watch:UNLOGGED")
    if pending:
        print("note: earlier unlogged changes recorded first:", "; ".join(pending))
    updates = dict(p.split("=", 1) for p in pairs)
    backup = PICO_ENV.with_name(f".env.bak.{card.replace('#', '')}-{now().strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(PICO_ENV, backup)
    lines, seen = [], set()
    for line in text.splitlines():
        k = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if k in updates:
            lines.append(f"{k}={updates[k]}")
            seen.add(k)
        else:
            lines.append(line)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    PICO_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    changes = record_env(card, f"{why} (backup {backup.name})", "env-set")
    print("\n".join(changes) or "no change")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--drill", choices=sorted(CHECKS))
    r = sub.add_parser("report")
    r.add_argument("--hours", type=int, default=24)
    s = sub.add_parser("env-set")
    s.add_argument("pairs", nargs="+", metavar="KEY=VALUE")
    for p in (s, sub.add_parser("env-record")):
        p.add_argument("--card", required=True)
        p.add_argument("--why", required=True)
    a = ap.parse_args()
    if a.cmd == "check":
        return cmd_check(a.drill)
    if a.cmd == "report":
        return cmd_report(a.hours)
    if a.cmd == "env-set":
        return cmd_env_set(a.pairs, a.card, a.why)
    changes = record_env(a.card, a.why, "env-record")
    print("\n".join(changes) or "no change since last record")
    return 0


if __name__ == "__main__":
    sys.exit(main())
