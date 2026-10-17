#!/usr/bin/env python3
"""pico#1331「我的接口」对账：卡面「对账命令」①②③④，真走 API 面，不读源码猜。

四步，各自 ✅/❌，任何一步 ❌ 整体 exit 1（卡面原文）：

  ① PUT 真 key → POST /test ok → 一轮对话 → 这一行用量：llm 积分 0、记了
     token、bill_to=personal。
  ② 一轮用到联网搜索的对话 → search 那一行仍照扣（> 0 分），不受①的 0 分
     规则影响（按次功能不是「模型」，见 model_endpoint.personal_provider_config_for
     的文档字符串）。
  ③ PUT 一个坏 key（真 base_url，假密钥）→ 对话回复含「你的接口出错了」，
     且这一轮没有在学校模型上新记一笔 llm 用量（出错不兜底：不准偷偷换
     回学校模型继续扣分）。
  ④ DELETE 这个接口 → 下一轮用回学校模型，llm 又照扣（> 0 分）——证明①③
     的 0 分 / 拒绝不是「以后永远不扣」，只是这一份接口没配好/是老师自己
     的接口。

用法（相对 repo 根；在能连到一个正在跑的 pico-api 的地方跑，容器里或本机
都行）::

    python3 scripts/pico-my-endpoint-check.py \\
        --base http://127.0.0.1:8000 \\
        --membership check-school:check-teacher \\
        --key-file /path/to/deepseek-key.txt

``--membership`` 是 ``school_id:membership_id``（联合头，见
``app.auth.scope_proxy_principal``），``--proxy-key`` 默认 ``pico-dev``——
生产环境这个开发代理 key 会被拒（``app.auth._production_proxy_key`` /
pico#1331 不变），生产验收要换一个真正发给这个 membership 的凭证，用同一
套 ``--base`` / ``--membership`` 形状即可。

密钥只从 ``--key-file`` 读一次，从不打印、不写进任何输出或日志；坏 key 由
``--bad-key`` 内联给（不是真密钥，不用文件）。接口默认 DeepSeek
（``https://api.deepseek.com`` / ``deepseek-chat``），可用 ``--endpoint-base-url``
/ ``--endpoint-model`` 换别的 OpenAI 兼容服务（含本机假服务，见下）。

② 依赖这次部署已经配好联网检索的上游 key（``TAVILY_API_KEY`` /
``ZHIPU_API_KEY``，见 ``pico_orchestrator.web_tools``）；没配时搜索会
「honest miss」、这一行按设计不扣分（见 ``cost_micro_yuan``：``ok=False``
从不计价），不是走「我的接口」的坏——这一步会报 ⚠️ 跳过（不计入
exit 1），把原因印出来，不装作验收过了。

``--pico-db`` 给一个本机 sqlite 路径时，额外复核①那一行的 token 列不是
NULL（teacher 面的 ``/v1/usage/events`` 故意不吐 token 细节，#1331 对老师
隐身模型切换的一部分），以及原来就有的表结构 / 密钥密文形态 / 出错文案
静态检查；这几段只是锦上添花（卡面「只当额外行」），不影响①②③④的判定，
没给 ``--pico-db`` 时直接跳过、照样可以 exit 0。

结束时（无论①②③④成功还是失败）都会 DELETE 掉这次建的接口行，不留现场。
"""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

DEFAULT_ENDPOINT_BASE_URL = "https://api.deepseek.com"
DEFAULT_ENDPOINT_MODEL = "deepseek-chat"
# Not a real key; just has to fail the vendor auth check, never a file.
DEFAULT_BAD_KEY = "sk-pico-my-endpoint-check-bad-key-0000000000"

REQUIRED_COLUMNS = {
    "school_id",
    "membership_id",
    "base_url",
    "model",
    "api_key_enc",
    "enabled",
    "updated_at",
}
FORBIDDEN_COLUMN_SUBSTRINGS = ("api_key_plain", "raw_key", "secret_plain")


# ---------------------------------------------------------------------------
# Real API surface — the same dev-proxy-key + joint X-Pico-Membership-Id
# mechanism scripts/longtask-eval.py and scripts/pico-ruler.py already use to
# call Pico as one membership (app.auth.scope_proxy_principal).
# ---------------------------------------------------------------------------


class CheckFailed(Exception):
    """One acceptance step failed; message is the ❌ reason, never a secret."""


class Api:
    def __init__(self, base: str, proxy_key: str, membership: str, timeout_s: float) -> None:
        self.base = base.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {proxy_key}",
            "X-Pico-Membership-Id": membership,
        }
        self.client = httpx.Client(timeout=httpx.Timeout(timeout_s, connect=10.0), trust_env=False)

    def put_endpoint(self, *, base_url: str, model: str, api_key: str) -> httpx.Response:
        return self.client.put(
            f"{self.base}/v1/me/model-endpoint",
            headers=self.headers,
            json={"base_url": base_url, "model": model, "api_key": api_key, "enabled": True},
        )

    def delete_endpoint(self) -> httpx.Response:
        return self.client.delete(f"{self.base}/v1/me/model-endpoint", headers=self.headers)

    def get_endpoint(self) -> httpx.Response:
        return self.client.get(f"{self.base}/v1/me/model-endpoint", headers=self.headers)

    def test_endpoint(self) -> httpx.Response:
        # Blank body = use whatever was just PUT and saved.
        return self.client.post(
            f"{self.base}/v1/me/model-endpoint/test",
            headers=self.headers,
            json={"base_url": "", "model": "", "api_key": ""},
        )

    def chat(self, text: str, *, product_model: str, timeout_s: float) -> httpx.Response:
        conversation_id = str(uuid.uuid4())
        return self.client.post(
            f"{self.base}/v1/chat/completions",
            headers={**self.headers, "X-Conversation-Id": conversation_id},
            json={
                "model": product_model,
                "stream": False,
                "messages": [{"role": "user", "content": text}],
            },
            timeout=httpx.Timeout(timeout_s, connect=10.0),
        )

    def usage_events(self, *, kind: str, limit: int = 5) -> list[dict[str, Any]]:
        resp = self.client.get(
            f"{self.base}/v1/usage/events",
            headers=self.headers,
            params={"kind": kind, "limit": limit},
        )
        resp.raise_for_status()
        return list(resp.json().get("events") or [])


def _newest_id(events: list[dict[str, Any]]) -> str | None:
    return events[0]["id"] if events else None


def _wait_for_new_row(
    api: Api, *, kind: str, before_id: str | None, attempts: int = 10, pause_s: float = 1.0
) -> dict[str, Any] | None:
    """Usage write can lag a hair behind the HTTP response; poll briefly."""
    for _ in range(attempts):
        rows = api.usage_events(kind=kind, limit=5)
        newest = rows[0] if rows else None
        if newest is not None and newest["id"] != before_id:
            return newest
        time.sleep(pause_s)
    return None


# ---------------------------------------------------------------------------
# ①②③④
# ---------------------------------------------------------------------------


def step1_personal_zero_points(
    api: Api,
    *,
    endpoint_base_url: str,
    endpoint_model: str,
    real_key: str,
    product_model: str,
    chat_timeout_s: float,
) -> dict[str, Any]:
    put_resp = api.put_endpoint(base_url=endpoint_base_url, model=endpoint_model, api_key=real_key)
    if put_resp.status_code != 200:
        raise CheckFailed(f"PUT /v1/me/model-endpoint -> {put_resp.status_code}: {put_resp.text[:300]}")
    saved = put_resp.json()
    if not saved.get("configured") or not saved.get("enabled"):
        raise CheckFailed(f"PUT saved but not configured/enabled: {saved}")

    test_resp = api.test_endpoint()
    if test_resp.status_code != 200 or not test_resp.json().get("ok"):
        raise CheckFailed(f"POST /test not ok: {test_resp.status_code} {test_resp.text[:300]}")

    before = _newest_id(api.usage_events(kind="llm", limit=1))
    chat_resp = api.chat("只回一个字：好", product_model=product_model, timeout_s=chat_timeout_s)
    if chat_resp.status_code != 200:
        raise CheckFailed(f"chat (personal key) -> {chat_resp.status_code}: {chat_resp.text[:300]}")

    row = _wait_for_new_row(api, kind="llm", before_id=before)
    if row is None:
        raise CheckFailed("no new kind=llm usage_events row showed up after the personal-key turn")
    extra = row.get("extra") or {}
    if str(extra.get("bill_to") or "").strip().lower() != "personal":
        raise CheckFailed(f"new llm row bill_to != personal: {extra!r}")
    points = str(row.get("points"))
    if points not in ("0.000", "0", "0.00"):
        raise CheckFailed(f"new llm row points != 0: {points!r}")
    return {"ok": True, "event_id": row["id"], "points": points, "bill_to": extra.get("bill_to")}


def step2_search_still_charged(
    api: Api, *, product_model: str, chat_timeout_s: float
) -> dict[str, Any]:
    before = _newest_id(api.usage_events(kind="search", limit=1))
    chat_resp = api.chat(
        "请用联网搜索工具查一下现在的新闻，必须真的调用搜索工具，然后简单说一句你查到了什么。",
        product_model=product_model,
        timeout_s=chat_timeout_s,
    )
    if chat_resp.status_code != 200:
        raise CheckFailed(f"chat (web search) -> {chat_resp.status_code}: {chat_resp.text[:300]}")
    row = _wait_for_new_row(api, kind="search", before_id=before)
    if row is None:
        return {
            "ok": None,
            "skipped": True,
            "reason": (
                "没有新的 kind=search 用量行——这次部署大概没配联网检索上游 key "
                "(TAVILY_API_KEY / ZHIPU_API_KEY)，搜索会 honest-miss 且按设计不计价，"
                "不是「我的接口」本身的问题，无法在这个环境里判定②"
            ),
        }
    points = str(row.get("points"))
    try:
        charged = float(points) > 0
    except (TypeError, ValueError):
        charged = False
    if not charged:
        raise CheckFailed(f"new search row is not charged (points={points!r}): honest-miss or unpriced")
    return {"ok": True, "event_id": row["id"], "points": points}


def step3_bad_key_refuses_no_fallback(
    api: Api,
    *,
    endpoint_base_url: str,
    endpoint_model: str,
    bad_key: str,
    product_model: str,
    chat_timeout_s: float,
) -> dict[str, Any]:
    put_resp = api.put_endpoint(base_url=endpoint_base_url, model=endpoint_model, api_key=bad_key)
    if put_resp.status_code != 200:
        raise CheckFailed(f"PUT (bad key) -> {put_resp.status_code}: {put_resp.text[:300]}")

    before = _newest_id(api.usage_events(kind="llm", limit=1))
    chat_resp = api.chat("只回一个字：好", product_model=product_model, timeout_s=chat_timeout_s)
    body_text = chat_resp.text
    if "你的接口出错了" not in body_text:
        raise CheckFailed(
            f"bad-key turn did not surface 「你的接口出错了」 (status={chat_resp.status_code}): "
            f"{body_text[:300]}"
        )
    # A new row is fine (e.g. a 0-point personal-tagged failure record for
    # audit); what must never happen is a row billed to the *school* model.
    # Give a real fallback write a moment to land before declaring none
    # happened.
    row = _wait_for_new_row(api, kind="llm", before_id=before, attempts=3, pause_s=0.5)
    if row is not None:
        extra = row.get("extra") or {}
        bill_to = str(extra.get("bill_to") or "").strip().lower()
        if bill_to != "personal":
            raise CheckFailed(
                f"a new kind=llm row on the bad-key turn is not tagged personal "
                f"(bill_to={bill_to!r}) — looks like a silent fallback to the "
                f"school model: {row!r}"
            )
        points = str(row.get("points"))
        if points not in ("0.000", "0", "0.00", "None"):
            raise CheckFailed(f"bad-key turn's personal-tagged row is non-zero: {row!r}")
    return {"ok": True, "status_code": chat_resp.status_code, "row_after": row}


def step4_delete_restores_school_model(
    api: Api, *, product_model: str, chat_timeout_s: float
) -> dict[str, Any]:
    del_resp = api.delete_endpoint()
    if del_resp.status_code != 200:
        raise CheckFailed(f"DELETE -> {del_resp.status_code}: {del_resp.text[:300]}")
    get_resp = api.get_endpoint()
    if get_resp.status_code == 200 and get_resp.json().get("configured"):
        raise CheckFailed(f"GET after DELETE still shows configured: {get_resp.json()}")

    before = _newest_id(api.usage_events(kind="llm", limit=1))
    chat_resp = api.chat("只回一个字：好", product_model=product_model, timeout_s=chat_timeout_s)
    if chat_resp.status_code != 200:
        raise CheckFailed(f"chat (school model) -> {chat_resp.status_code}: {chat_resp.text[:300]}")
    row = _wait_for_new_row(api, kind="llm", before_id=before)
    if row is None:
        raise CheckFailed("no new kind=llm usage_events row after DELETE — school model turn never billed")
    extra = row.get("extra") or {}
    if str(extra.get("bill_to") or "").strip().lower() == "personal":
        raise CheckFailed(f"row after DELETE still billed personal: {extra!r}")
    points = str(row.get("points"))
    try:
        charged = float(points) > 0
    except (TypeError, ValueError):
        charged = False
    if not charged:
        raise CheckFailed(f"school-model row after DELETE is not charged (points={points!r})")
    return {"ok": True, "event_id": row["id"], "points": points}


# ---------------------------------------------------------------------------
# Extra, cheap, static/DB-level checks (kept from the earlier version of this
# script) — never the primary ①②③④ verdict, just bonus lines when a
# --pico-db / nothing extra is needed.
# ---------------------------------------------------------------------------


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _cols(con: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in con.execute(f"PRAGMA table_info({table})")]


def check_schema(db: Path) -> dict[str, Any]:
    if not db.is_file():
        return {"ok": None, "skipped": True, "reason": f"no such db file: {db}"}
    con = _connect_ro(db)
    tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "user_model_endpoint" not in tables:
        con.close()
        return {"ok": False, "reason": "user_model_endpoint table missing"}
    cols = _cols(con, "user_model_endpoint")
    con.close()
    missing = sorted(REQUIRED_COLUMNS - set(cols))
    forbidden = sorted(c for c in cols if any(bad in c.lower() for bad in FORBIDDEN_COLUMN_SUBSTRINGS))
    ok = not missing and not forbidden
    return {"ok": ok, "columns": cols, "missing": missing, "forbidden_plaintext_like_columns": forbidden}


def _looks_like_fernet_token(enc: str) -> bool:
    if not enc:
        return False
    try:
        raw = base64.urlsafe_b64decode(enc.encode("ascii") + b"=" * (-len(enc) % 4))
    except Exception:  # noqa: BLE001
        return False
    return len(raw) > 0 and raw[0] == 0x80


def check_key_hygiene(db: Path) -> dict[str, Any]:
    if not db.is_file():
        return {"ok": None, "skipped": True, "reason": f"no such db file: {db}"}
    con = _connect_ro(db)
    tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "user_model_endpoint" not in tables:
        con.close()
        return {"ok": False, "reason": "user_model_endpoint table missing"}
    rows = con.execute(
        "SELECT school_id, membership_id, api_key_enc FROM user_model_endpoint WHERE api_key_enc != ''"
    ).fetchall()
    con.close()
    bad_shape = [f"{r[0]}/{r[1]}" for r in rows if not _looks_like_fernet_token(r[2])]
    return {"ok": not bad_shape, "rows_with_key": len(rows), "not_fernet_shaped": bad_shape}


def check_event_tokens_recorded(db: Path, event_id: str | None) -> dict[str, Any]:
    """Teacher-facing /v1/usage/events hides token columns on purpose (#1331);
    confirm 「tokens recorded」 straight from the table this co-located DB
    holds, for the exact row ① just made."""
    if event_id is None:
        return {"ok": None, "skipped": True, "reason": "no event id from step 1 (it already failed)"}
    if not db.is_file():
        return {"ok": None, "skipped": True, "reason": f"no such db file: {db}"}
    con = _connect_ro(db)
    row = con.execute(
        "SELECT prompt_tokens, completion_tokens, total_tokens, tokens_unknown"
        " FROM usage_events WHERE id = ?",
        (event_id,),
    ).fetchone()
    con.close()
    if row is None:
        return {"ok": False, "reason": f"event {event_id} not found in {db}"}
    pt, ct, tt, unknown = row
    recorded = not bool(unknown) and (pt is not None or ct is not None or tt is not None)
    return {
        "ok": recorded,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
        "tokens_unknown": bool(unknown),
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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _mark(result: dict[str, Any]) -> str:
    if result.get("ok") is True:
        return "✅"
    if result.get("ok") is None:
        return "⚠️"
    return "❌"


def _print_section(name: str, result: dict[str, Any]) -> None:
    print(f"{_mark(result)} {name}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="http://127.0.0.1:8000", help="pico-api base URL")
    p.add_argument("--proxy-key", default="pico-dev", help="dev/proxy bearer key (non-production only)")
    p.add_argument("--membership", required=True, help="school_id:membership_id (joint header form)")
    p.add_argument("--key-file", required=True, type=Path, help="file holding the real vendor key; never printed")
    p.add_argument("--endpoint-base-url", default=DEFAULT_ENDPOINT_BASE_URL)
    p.add_argument("--endpoint-model", default=DEFAULT_ENDPOINT_MODEL)
    p.add_argument("--bad-key", default=DEFAULT_BAD_KEY, help="inline, never a real key, never a file")
    p.add_argument("--product-model", default="pico-fast", help="top-level chat.completions model (a lane name)")
    p.add_argument("--chat-timeout-s", type=float, default=90.0)
    p.add_argument("--pico-db", type=Path, default=None, help="optional sqlite path for the extra bonus checks")
    args = p.parse_args(argv)

    real_key = args.key_file.read_text(encoding="utf-8").strip()
    if not real_key:
        print("❌ --key-file is empty", file=sys.stderr)
        return 1

    api = Api(args.base, args.proxy_key, args.membership, timeout_s=30.0)

    sections: dict[str, dict[str, Any]] = {}
    event1_id: str | None = None
    try:
        try:
            r1 = step1_personal_zero_points(
                api,
                endpoint_base_url=args.endpoint_base_url,
                endpoint_model=args.endpoint_model,
                real_key=real_key,
                product_model=args.product_model,
                chat_timeout_s=args.chat_timeout_s,
            )
            event1_id = r1.get("event_id")
        except CheckFailed as exc:
            r1 = {"ok": False, "reason": str(exc)}
        sections["① PUT 真 key → test ok → 一轮 → llm 0 分/记 token/bill_to=personal"] = r1

        try:
            r2 = step2_search_still_charged(api, product_model=args.product_model, chat_timeout_s=args.chat_timeout_s)
        except CheckFailed as exc:
            r2 = {"ok": False, "reason": str(exc)}
        sections["② 联网搜索那一行仍照扣"] = r2

        try:
            r3 = step3_bad_key_refuses_no_fallback(
                api,
                endpoint_base_url=args.endpoint_base_url,
                endpoint_model=args.endpoint_model,
                bad_key=args.bad_key,
                product_model=args.product_model,
                chat_timeout_s=args.chat_timeout_s,
            )
        except CheckFailed as exc:
            r3 = {"ok": False, "reason": str(exc)}
        sections["③ 坏 key → 「你的接口出错了」且不兜底扣学校模型"] = r3

        try:
            r4 = step4_delete_restores_school_model(api, product_model=args.product_model, chat_timeout_s=args.chat_timeout_s)
        except CheckFailed as exc:
            r4 = {"ok": False, "reason": str(exc)}
        sections["④ DELETE 后用回学校模型，llm 又照扣"] = r4
    finally:
        # Clean up no matter what happened above — never leave the test row.
        try:
            api.delete_endpoint()
        except Exception as exc:  # noqa: BLE001 — cleanup must not mask the result
            print(f"⚠ 清理失败，测试行可能还在：{exc}", file=sys.stderr)

    if args.pico_db is not None:
        sections["额外·表结构 user_model_endpoint"] = check_schema(args.pico_db)
        sections["额外·密钥密文形态"] = check_key_hygiene(args.pico_db)
        sections["额外·①那一行 token 列确实记了"] = check_event_tokens_recorded(args.pico_db, event1_id)
    sections["额外·出错文案不漏「模型」字样"] = check_no_fallback_copy()

    for name, result in sections.items():
        _print_section(name, result)

    hard_fail = any(result.get("ok") is False for result in sections.values())
    print("PASS" if not hard_fail else "FAIL")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
