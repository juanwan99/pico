#!/usr/bin/env python3
"""Switch Pico's brain (primary + fallbacks) only after the models prove they work.

10-14 incident: primary went to gpt-5.6-sol while its relay had no image channel;
exam AI marking failed for 14 minutes before anyone saw it. Never again flip
blind:

1. Preflight every candidate straight at the relay (DEEPSEEK_BASE_URL): one text
   turn, one image turn. Primary must pass both; at least one fallback must pass
   both (image work needs a landing). A fallback that is down now stays listed
   (failover skips it, #1261) with a DOWN line.
2. Back up /opt/pico/.env, write DEEPSEEK_MODEL + PICO_BRAIN_FALLBACKS, recreate
   pico-api (the only service that reads them).
3. Post-check through Pico itself (text lane + image lane). Any failure → restore
   the backup and recreate again.

Host-only. Never prints keys. Smoke membership only (never a real school).

    python3 scripts/brain-switch.py --primary gemini-3.8-flash --fallbacks grok-4.6,gpt-5.6-sol --dry-run
    python3 scripts/brain-switch.py --primary gemini-3.8-flash --fallbacks grok-4.6,gpt-5.6-sol
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PICO_ENV = Path("/opt/pico/.env")
PICO_API = "http://127.0.0.1:18765"
SMOKE_MEMBER = "smoke-school:smoke-e2e"
IMAGE = ROOT / "testdata" / "brain" / "probe-ans.png"
TEXT_ASK = "只回答一个数字：17乘以23等于多少？"
TEXT_WANT = "391"
IMAGE_ASK = '逐字转写图中写的内容，只回 JSON：{"text": "..."}。不要调用任何工具。'
IMAGE_WANT = "42"


def env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v.strip().strip('"').strip("'")
    return out


def rewrite_env(text: str, updates: dict[str, str]) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for line in text.splitlines():
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("#") else ""
        if key in updates:
            lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            lines.append(line)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    return "\n".join(lines) + "\n"


def image_content(ask: str) -> list[dict]:
    data = base64.b64encode(IMAGE.read_bytes()).decode()
    return [
        {"type": "text", "text": ask},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + data}},
    ]


def post(url: str, headers: dict[str, str], body: dict, timeout: float) -> tuple[str, str]:
    """(reply, error). Error text is trimmed and never carries headers."""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return "", f"HTTP {exc.code} {exc.read().decode('utf-8', 'replace')[:200]}"
    except Exception as exc:  # noqa: BLE001 — report, never raise mid-switch
        return "", f"{type(exc).__name__}: {str(exc)[:200]}"
    return reply_text(out), ""


def reply_text(out: dict) -> str:
    """Chat-completions body, or a Responses-API body (some relay channels answer that way)."""
    if out.get("choices"):
        return str((out["choices"][0].get("message") or {}).get("content") or "")
    parts = [
        str(c.get("text") or "")
        for item in out.get("output") or []
        if isinstance(item, dict) and item.get("type") == "message"
        for c in item.get("content") or []
        if isinstance(c, dict) and c.get("type") == "output_text"
    ]
    return "".join(parts) or str(out.get("output_text") or "")


def relay_probe(base: str, key: str, model: str, content, want: str) -> dict:
    t0 = time.time()
    reply, err = post(
        base.rstrip("/") + "/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {"model": model, "stream": False, "messages": [{"role": "user", "content": content}]},
        timeout=120,
    )
    return {"ok": not err and want in reply, "s": round(time.time() - t0, 1), "err": err, "reply": reply[:80]}


def pico_probe(token: str, lane: str, content, want: str, extra: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Pico-Membership-Id": SMOKE_MEMBER,
        "X-Conversation-Id": str(uuid.uuid4()),
    }
    if extra:  # exam-style direct lane, same as edu AI marking
        headers["x-pico-output"] = "json_only_no_files"
    t0 = time.time()
    reply, err = post(
        PICO_API + "/v1/chat/completions",
        headers,
        {"model": lane, "stream": False, "messages": [{"role": "user", "content": content}], **(extra or {})},
        timeout=300,
    )
    return {"ok": not err and want in reply, "s": round(time.time() - t0, 1), "err": err, "reply": reply[:80]}


def preflight(base: str, key: str, primary: str, fallbacks: list[str]) -> bool:
    rows = {}
    for model in [primary, *fallbacks]:
        rows[model] = {
            "text": relay_probe(base, key, model, TEXT_ASK, TEXT_WANT),
            "image": relay_probe(base, key, model, image_content(IMAGE_ASK), IMAGE_WANT),
        }
        print(json.dumps({"preflight": model, **rows[model]}, ensure_ascii=False), flush=True)
    problems = []
    if not (rows[primary]["text"]["ok"] and rows[primary]["image"]["ok"]):
        problems.append(f"主模型 {primary} 文字或读图不过")
    # A backup that is down now may stay listed: failover skips a dead channel or
    # key (#1261) and it comes back on its own. One backup must catch everything.
    for m in fallbacks:
        if not rows[m]["text"]["ok"]:
            print("DOWN", f"备用 {m} 现在不通，留在名单里，坏着会自动跳过", flush=True)
    if fallbacks and not any(rows[m]["text"]["ok"] and rows[m]["image"]["ok"] for m in fallbacks):
        problems.append("备用里没有一个文字、读图都通的")
    for p in problems:
        print("BLOCKED", p, flush=True)
    return not problems


def recreate_api() -> None:
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.host.yml", "up", "-d",
         "--no-deps", "--no-build", "--force-recreate", "pico-api"],
        cwd="/opt/pico", check=True,
    )
    for _ in range(60):
        try:
            with urllib.request.urlopen(PICO_API + "/health", timeout=5) as resp:
                if resp.status == 200:
                    return
        except Exception:  # noqa: BLE001, S110 — still booting
            pass
        time.sleep(2)
    raise RuntimeError("pico-api not healthy after recreate")


def postcheck(token: str) -> bool:
    checks = {
        "text": pico_probe(token, "pico-fast", TEXT_ASK, TEXT_WANT),
        "image": pico_probe(
            token, "pico-fast", image_content(IMAGE_ASK), IMAGE_WANT,
            {"web_search": False, "allowed_tools": [], "force_agent": False, "reasoning_effort": "none"},
        ),
    }
    for name, row in checks.items():
        print(json.dumps({"postcheck": name, **row}, ensure_ascii=False), flush=True)
    return all(row["ok"] for row in checks.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", required=True)
    ap.add_argument("--fallbacks", default="", help="comma list, order = try order")
    ap.add_argument("--dry-run", action="store_true", help="preflight only, touch nothing")
    args = ap.parse_args()
    fallbacks = [m.strip() for m in args.fallbacks.split(",") if m.strip()]
    env = env_file(PICO_ENV)
    base, key = env.get("DEEPSEEK_BASE_URL", ""), env.get("DEEPSEEK_API_KEY", "")
    token = env.get("PICO_OPENAI_PROXY_KEY", "")
    if not base or not key or not token:
        print("MISSING DEEPSEEK_BASE_URL / DEEPSEEK_API_KEY / PICO_OPENAI_PROXY_KEY")
        return 2
    print(f"now primary={env.get('DEEPSEEK_MODEL')} fallbacks={env.get('PICO_BRAIN_FALLBACKS', '')}", flush=True)
    if not preflight(base, key, args.primary, fallbacks):
        print("NOT SWITCHED")
        return 1
    if args.dry_run:
        print("PREFLIGHT OK (dry-run, not switched)")
        return 0
    backup = PICO_ENV.with_name(f".env.bak.brain-{time.strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(PICO_ENV, backup)
    PICO_ENV.write_text(
        rewrite_env(
            PICO_ENV.read_text(encoding="utf-8"),
            {"DEEPSEEK_MODEL": args.primary, "PICO_BRAIN_FALLBACKS": ",".join(fallbacks)},
        ),
        encoding="utf-8",
    )
    PICO_ENV.chmod(0o600)
    print("env written, backup", backup.name, flush=True)
    recreate_api()
    if postcheck(token):
        print(f"SWITCHED primary={args.primary} fallbacks={','.join(fallbacks)}")
        return 0
    shutil.copy2(backup, PICO_ENV)
    recreate_api()
    print("ROLLED_BACK to", backup.name)
    return 1


if __name__ == "__main__":
    sys.exit(main())
