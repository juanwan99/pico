#!/usr/bin/env python3
"""Point Pico DEEPSEEK_* at New API loopback. Host-only. Never prints keys.

Backup the old AIProxy key first. Recreate pico-api without changing git SHA.
Run on ECS: python3 scripts/cutover-brain-to-newapi.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PICO_ENV = Path("/opt/pico/.env")
BACKUP = Path("/home/ops/.secrets/aiproxy-direct.env")
NEW_BASE = "http://127.0.0.1:3000/v1"


def env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v.strip().strip('"')
    return out


def rewrite_pico_env(text: str, updates: dict[str, str]) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            lines.append(line)
            continue
        k, _v = line.split("=", 1)
        if k in updates:
            lines.append(f"{k}={updates[k]}")
            seen.add(k)
        else:
            lines.append(line)
    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not PICO_ENV.is_file():
        print("MISSING_PICO_ENV")
        return 2
    pico = env_file(PICO_ENV)
    old_base = pico.get("DEEPSEEK_BASE_URL") or ""
    old_key = pico.get("DEEPSEEK_API_KEY") or ""
    gateway_key = pico.get("PICO_IMAGE_GATEWAY_KEY") or ""
    if not old_key or not gateway_key:
        print("MISSING_KEYS")
        return 2
    if "127.0.0.1:3000" in old_base.lower():
        print("already_new_api", "base_ok", True, "keys_equal", old_key == gateway_key)
        return 0
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if not BACKUP.exists():
        BACKUP.write_text(
            f"AIPROXY_BASE_URL={old_base}\nAIPROXY_API_KEY={old_key}\n",
            encoding="utf-8",
        )
        os.chmod(BACKUP, 0o600)
        print("backup_written", True)
    else:
        print("backup_exists", True)
    text = PICO_ENV.read_text(encoding="utf-8")
    PICO_ENV.write_text(
        rewrite_pico_env(
            text,
            {
                "DEEPSEEK_BASE_URL": NEW_BASE,
                "DEEPSEEK_API_KEY": gateway_key,
            },
        ),
        encoding="utf-8",
    )
    os.chmod(PICO_ENV, 0o600)
    print("env_rewritten", "new_base", NEW_BASE, "key_switched_to_gateway", True)
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.host.yml",
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--force-recreate",
            "pico-api",
        ],
        cwd="/opt/pico",
        check=True,
    )
    probe = subprocess.check_output(
        [
            "docker",
            "exec",
            "pico-pico-api-1",
            "python3",
            "-c",
            (
                "import os; u=os.environ.get('DEEPSEEK_BASE_URL',''); "
                "k=os.environ.get('DEEPSEEK_API_KEY',''); "
                "g=os.environ.get('PICO_IMAGE_GATEWAY_KEY',''); "
                "print('container_base', u); "
                "print('via_new_api', '127.0.0.1:3000' in u); "
                "print('keys_equal', k==g); "
                "print('key_len', len(k))"
            ),
        ],
        text=True,
    )
    print(probe.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
