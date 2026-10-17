#!/usr/bin/env python3
"""pico#1331「我的接口」对账：存储 / 密钥卫生 / 积分不扣 / 出错不兜底。Read-only.

典型本机用法（相对 repo 根，``data/pico.db`` 是本机常用相对路径）::

    python3 scripts/pico-my-endpoint-check.py --pico-db data/pico.db

四段各自 ✅/❌，任何一段 ❌ 整体 exit 1：

1. 表结构：``user_model_endpoint`` 列齐全，且没有明文密钥列（只有
   ``api_key_enc``）。
2. 密钥卫生：已存的 ``api_key_enc`` 都是 Fernet 密文形态（不是裸 ``sk-…``
   或别的明文），本脚本从不打印、也不要求传入真实密钥——只看形态。给
   ``--secret-file``（内容就是 ``PICO_ENDPOINT_SECRET`` 的值，一行，不进
   卡面/日志）时额外解一遍，只报「能/不能解开」，仍不打印明文。
3. 积分：``usage_events`` 里 ``kind='llm'`` 且 ``extra.bill_to=='personal'``
   的行，用正本的 ``points_from_row`` 复算，必须全是 0 分（走自己接口不扣
   积分，按次功能的 search/kb/image/sandbox 行不带这个 tag，不受影响）。
4. 出错不兜底：静态扫 ``personal_endpoint_reason()`` 对一批真实错误形态
   （401/404/429/超时/连不上）的返回文案与完整
   ``user_message_for_error()`` 输出——必须都是「你的接口出错了：…」开头，
   且不含老师不该看到的词（复用 ``teacher_text.leaks()`` 同一张词表，包含
   「模型」本身——切模型对老师必须隐身）。这段纯代码检查，不连库、不连网。

没有 ``PICO_ENDPOINT_SECRET`` 时第 2 段的「解密」子检查跳过（不算 ❌），
因为本机常没有配这个密钥——这正是模块自己 fail-open 的设计（见
``model_endpoint.personal_provider_config_for``）。
"""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

REQUIRED_COLUMNS = {
    "school_id",
    "membership_id",
    "base_url",
    "model",
    "api_key_enc",
    "enabled",
    "updated_at",
}
# Any of these names showing up would mean a plaintext key column exists.
FORBIDDEN_COLUMN_SUBSTRINGS = ("api_key_plain", "raw_key", "secret_plain")


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _cols(con: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in con.execute(f"PRAGMA table_info({table})")]


def check_schema(db: Path) -> dict[str, Any]:
    if not db.is_file():
        return {"ok": False, "reason": f"no such db file: {db}"}
    con = _connect_ro(db)
    tables = {
        str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "user_model_endpoint" not in tables:
        con.close()
        return {"ok": False, "reason": "user_model_endpoint table missing"}
    cols = _cols(con, "user_model_endpoint")
    con.close()
    missing = sorted(REQUIRED_COLUMNS - set(cols))
    forbidden = sorted(
        c for c in cols if any(bad in c.lower() for bad in FORBIDDEN_COLUMN_SUBSTRINGS)
    )
    ok = not missing and not forbidden
    return {
        "ok": ok,
        "columns": cols,
        "missing": missing,
        "forbidden_plaintext_like_columns": forbidden,
    }


def _looks_like_fernet_token(enc: str) -> bool:
    """Fernet tokens are urlsafe-base64, version byte 0x80 once decoded."""
    if not enc:
        return False
    try:
        raw = base64.urlsafe_b64decode(enc.encode("ascii") + b"=" * (-len(enc) % 4))
    except Exception:  # noqa: BLE001
        return False
    return len(raw) > 0 and raw[0] == 0x80


def check_key_hygiene(db: Path, secret_file: Path | None) -> dict[str, Any]:
    if not db.is_file():
        return {"ok": False, "reason": f"no such db file: {db}"}
    con = _connect_ro(db)
    tables = {
        str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "user_model_endpoint" not in tables:
        con.close()
        return {"ok": False, "reason": "user_model_endpoint table missing"}
    rows = con.execute(
        "SELECT school_id, membership_id, api_key_enc FROM user_model_endpoint"
        " WHERE api_key_enc != ''"
    ).fetchall()
    con.close()
    bad_shape = [f"{r[0]}/{r[1]}" for r in rows if not _looks_like_fernet_token(r[2])]
    decrypt_checked = 0
    decrypt_failed: list[str] = []
    secret = ""
    if secret_file is not None:
        secret = secret_file.read_text(encoding="utf-8").strip()
    if secret:
        import hashlib

        from cryptography.fernet import Fernet, InvalidToken

        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        f = Fernet(key)
        for school_id, membership_id, enc in rows:
            decrypt_checked += 1
            try:
                plain = f.decrypt(enc.encode("ascii"))
                if not plain:
                    decrypt_failed.append(f"{school_id}/{membership_id} (empty)")
            except InvalidToken:
                decrypt_failed.append(f"{school_id}/{membership_id}")
    ok = not bad_shape and not decrypt_failed
    return {
        "ok": ok,
        "rows_with_key": len(rows),
        "not_fernet_shaped": bad_shape,
        "decrypt_checked_with_secret": decrypt_checked,
        "decrypt_failed": decrypt_failed,
        "note": "decrypt sub-check skipped (no --secret-file / empty)" if not secret else "",
    }


def check_billing(db: Path) -> dict[str, Any]:
    if not db.is_file():
        return {"ok": False, "reason": f"no such db file: {db}"}
    from app.points_meter import points_from_row

    con = _connect_ro(db)
    tables = {
        str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "usage_events" not in tables:
        con.close()
        return {"ok": False, "reason": "usage_events table missing"}
    rows = con.execute(
        "SELECT id, model, prompt_tokens, completion_tokens, total_tokens, tokens_unknown,"
        " extra_json FROM usage_events WHERE kind = 'llm'"
    ).fetchall()
    con.close()
    nonzero: list[dict[str, Any]] = []
    checked = 0
    for row_id, model, pt, ct, tt, unknown, extra_json in rows:
        try:
            extra = json.loads(extra_json or "{}")
        except json.JSONDecodeError:
            extra = {}
        if str(extra.get("bill_to") or "").strip().lower() != "personal":
            continue
        checked += 1
        points = points_from_row(
            kind="llm",
            model=model,
            tokens_unknown=bool(unknown),
            total_tokens=tt,
            prompt_tokens=pt,
            completion_tokens=ct,
            extra=extra,
        )
        if points not in (None, "0.000", "0"):
            nonzero.append({"id": row_id, "points": points})
    return {
        "ok": not nonzero,
        "personal_llm_rows_checked": checked,
        "nonzero_points_rows": nonzero,
        "note": "0 personal llm rows is fine (nothing recorded yet locally); gate only fires on a nonzero row",
    }


_ERROR_SHAPES = [
    "HTTP 401 Unauthorized invalid api key",
    "HTTP 404 model_not_found: the model does not exist",
    "HTTP 429 rate limit exceeded",
    "connection timed out after 10s",
    "connect error: could not connect to host",
    "HTTP 402 insufficient quota",
]


def check_no_fallback_copy() -> dict[str, Any]:
    from pico_orchestrator.teacher_text import leaks
    from pico_orchestrator.user_errors import (
        PERSONAL_ENDPOINT_ERROR_TAG,
        personal_endpoint_reason,
        user_message_for_error,
    )

    bad: list[dict[str, Any]] = []
    for shape in _ERROR_SHAPES:
        reason = personal_endpoint_reason(shape)
        full = user_message_for_error(PERSONAL_ENDPOINT_ERROR_TAG + shape)
        if leaks(reason):
            bad.append({"shape": shape, "stage": "personal_endpoint_reason", "text": reason})
        if not full.startswith("你的接口出错了："):
            bad.append({"shape": shape, "stage": "user_message_for_error_prefix", "text": full})
        if leaks(full):
            bad.append({"shape": shape, "stage": "user_message_for_error", "text": full})
    return {"ok": not bad, "shapes_checked": len(_ERROR_SHAPES), "violations": bad}


def _print_section(name: str, result: dict[str, Any]) -> None:
    mark = "✅" if result.get("ok") else "❌"
    print(f"{mark} {name}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pico-db", type=Path, default=ROOT / "data" / "pico.db")
    p.add_argument(
        "--secret-file",
        type=Path,
        default=None,
        help="file holding PICO_ENDPOINT_SECRET (one line); never printed",
    )
    args = p.parse_args(argv)

    sections = {
        "1. 表结构 user_model_endpoint": check_schema(args.pico_db),
        "2. 密钥卫生（密文形态，不是明文）": check_key_hygiene(args.pico_db, args.secret_file),
        "3. 走自己接口不扣积分（kind=llm, bill_to=personal → 0 分）": check_billing(args.pico_db),
        "4. 出错不兜底、不漏「模型」字样": check_no_fallback_copy(),
    }
    for name, result in sections.items():
        _print_section(name, result)
    ok = all(result.get("ok") for result in sections.values())
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
