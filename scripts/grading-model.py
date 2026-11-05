#!/usr/bin/env python3
"""Switch exam marking models (pico#1379): one command, no restart, per school or default.

Owner 11-02「阅卷需要单列，至于用哪个模型 我需要灵活可方便切换」. Marking tickets
(``ai:exam-grading``) read ``data/grading-models.json`` inside pico-api on each call:
``ocr`` = handwriting transcription (lane ``pico-ocr``), ``score`` = scoring,
``score2`` = the second scorer edu averages in on some kinds (lane ``pico-score2``,
edu-core#4576; unset = ``score``).

1. Preflight the new model straight at the relay on the marking token
   (``PICO_GRADING_API_KEY``, New API group ``grading``) — that group is exactly
   what marking will hit: ocr must read the probe image, score must answer text
   and read the image (scoring falls back to the picture when transcription fails).
   A few calls on the marking token, never on chat's.
2. Write the file through the api container (atomic rename). Pico picks it up on
   the next call; nothing restarts.
3. One trail line in ~/pico-env-changes.log: what, old -> new, card, why.

Host-only. Never prints keys.

    python3 scripts/grading-model.py show
    python3 scripts/grading-model.py set --school <id> --score gemini-3.8-flash \\
        --card edu-core#4576 --why "G26 补评用 Gemini"
    python3 scripts/grading-model.py set --ocr gemini-3.8-flash --card ... --why ... --dry-run
    python3 scripts/grading-model.py clear --school <id> --card ... --why ...
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "pico-pico-api-1"
CONFIG = "/app/data/grading-models.json"
TRAIL = Path.home() / "pico-env-changes.log"
ROLES = ("ocr", "score", "score2")


def _brain_switch():
    spec = importlib.util.spec_from_file_location("brain_switch", ROOT / "scripts" / "brain-switch.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(mod)
    return mod


bs = _brain_switch()


def read_config() -> dict:
    out = subprocess.run(["docker", "exec", API, "cat", CONFIG], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return {}  # no file yet = today's models
    data = json.loads(out.stdout or "{}")
    return data if isinstance(data, dict) else {}


def write_config(data: dict) -> None:
    code = (
        "import json,os,sys;d=sys.stdin.read();json.loads(d);"
        f"t='{CONFIG}.tmp';open(t,'w',encoding='utf-8').write(d);os.replace(t,'{CONFIG}')"
    )
    subprocess.run(
        ["docker", "exec", "-i", API, "python3", "-c", code],
        input=json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        text=True,
        check=True,
    )


def env_defaults(env: dict[str, str]) -> dict[str, str]:
    """What marking uses with no file entry (Pico's own fallback, same order)."""
    return {"ocr": env.get("PICO_OCR_MODEL", ""), "score": env.get("DEEPSEEK_MODEL", ""), "score2": ""}


def effective(data: dict, school: str | None, env: dict[str, str]) -> dict[str, str]:
    base = env_defaults(env)
    layers = [data.get("default") or {}]
    if school:
        layers.append((data.get("schools") or {}).get(school) or {})
    for layer in layers:
        for role in ROLES:
            if str(layer.get(role) or "").strip():
                base[role] = str(layer[role]).strip()
    base["score2"] = base["score2"] or base["score"]  # Pico's own fallback (score2_backend_model)
    return base


def preflight(base: str, key: str, changes: dict[str, str], long_only: frozenset[str]) -> bool:
    ok = True
    for role, model in changes.items():
        if model in long_only:
            print("BLOCKED", f"{model} 只给多轮会话用，不能阅卷", flush=True)
            ok = False
            continue
        row = {"image": bs.relay_probe(base, key, model, bs.image_content(bs.IMAGE_ASK), bs.IMAGE_WANT)}
        if role in ("score", "score2"):
            row["text"] = bs.relay_probe(base, key, model, bs.TEXT_ASK, bs.TEXT_WANT)
        print(json.dumps({"preflight": role, "model": model, **row}, ensure_ascii=False), flush=True)
        if not all(r["ok"] for r in row.values()):
            print("BLOCKED", f"{role} 模型 {model} 在阅卷分组里不通（文字或读图）", flush=True)
            ok = False
    return ok


def trail(card: str, why: str, what: str) -> None:
    stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {card} {CONFIG} [grading-model] {what}. Why: {why}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    for name in ("set", "clear"):
        p = sub.add_parser(name)
        p.add_argument("--school", default="", help="school_id; empty = default for every school")
        if name == "set":
            p.add_argument("--ocr", default="", help="handwriting transcription model")
            p.add_argument("--score", default="", help="scoring model")
            p.add_argument("--score2", default="", help="second scoring model (edu averages it in on some kinds)")
            p.add_argument("--dry-run", action="store_true", help="preflight only, write nothing")
        p.add_argument("--card", required=True)
        p.add_argument("--why", required=True)
    args = ap.parse_args()

    env = bs.env_file(bs.PICO_ENV)
    data = read_config()
    if args.cmd == "show":
        print(json.dumps({"file": data, "env_defaults": env_defaults(env),
                          "grading_key": bool(env.get("PICO_GRADING_API_KEY"))}, ensure_ascii=False, indent=2))
        return 0

    school = args.school.strip()
    before = effective(data, school or None, env)
    if args.cmd == "clear":
        if not school:
            print("clear 要 --school（默认那层用 set 改）")
            return 2
        (data.get("schools") or {}).pop(school, None)
    else:
        changes = {r: getattr(args, r).strip() for r in ROLES if getattr(args, r).strip()}
        if not changes:
            print("set 要 --ocr / --score / --score2")
            return 2
        base, key = env.get("DEEPSEEK_BASE_URL", ""), env.get("PICO_GRADING_API_KEY", "")
        if not base or not key:
            print("MISSING DEEPSEEK_BASE_URL / PICO_GRADING_API_KEY")
            return 2
        long_only = frozenset(
            m.strip() for m in env.get("PICO_LONG_SESSION_MODELS", "gpt-5.6-sol").split(",") if m.strip()
        )
        if not preflight(base, key, changes, long_only):
            print("NOT SWITCHED")
            return 1
        if args.dry_run:
            print("PREFLIGHT OK (dry-run, not switched)")
            return 0
        layer = data.setdefault("schools", {}).setdefault(school, {}) if school else data.setdefault("default", {})
        layer.update(changes)
    write_config(data)
    after = effective(read_config(), school or None, env)
    what = "; ".join(f"{school or 'default'}.{r}: {before[r] or '-'} -> {after[r] or '-'}" for r in ROLES
                     if before[r] != after[r]) or "no change"
    trail(args.card, args.why, what)
    print("SWITCHED", what)
    return 0


if __name__ == "__main__":
    sys.exit(main())
