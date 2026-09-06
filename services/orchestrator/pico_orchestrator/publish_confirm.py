"""One-shot publish confirm. Reuses ask_user park; not a second approval OS."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

from pico_orchestrator.gateway import Principal, ToolError
from pico_orchestrator.sandbox_s1 import preview_signing_secret

TTL_S = 10 * 60
_YES = "确认发布"
_NO = "取消"
_USED: dict[str, float] = {}


def _mac(payload: str) -> str:
    return hmac.new(
        preview_signing_secret(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def reset_confirm_tokens() -> None:
    _USED.clear()


def _purge(now: float) -> None:
    dead = [key for key, exp in _USED.items() if exp <= now]
    for key in dead:
        _USED.pop(key, None)


def issue_confirm_token(
    principal: Principal,
    *,
    artifact_id: str,
    now: float | None = None,
    ttl_s: int = TTL_S,
) -> str:
    aid = (artifact_id or "").strip()
    if not aid:
        raise ToolError("tool.invalid_arguments", "artifact_id is required")
    stamp = int(now if now is not None else time.time())
    exp = stamp + int(ttl_s)
    nonce = secrets.token_hex(8)
    school = str(principal.school_id)
    member = str(principal.membership_id)
    payload = f"{school}\n{member}\n{aid}\n{nonce}\n{exp}"
    return f"{nonce}.{exp}.{_mac(payload)}"


def consume_confirm_token(
    principal: Principal,
    *,
    artifact_id: str,
    token: str,
    now: float | None = None,
) -> None:
    raw = (token or "").strip()
    aid = (artifact_id or "").strip()
    if not raw or not aid:
        raise ToolError(
            "publish.unconfirmed",
            "发布需要老师确认具体页面。没有确认，未公开发布。",
        )
    parts = raw.split(".")
    if len(parts) != 3:
        raise ToolError("publish.unconfirmed", "确认令牌无效。未公开发布。")
    nonce, exp_raw, sig = parts
    try:
        exp = int(exp_raw)
    except ValueError as exc:
        raise ToolError("publish.unconfirmed", "确认令牌无效。未公开发布。") from exc
    stamp = float(now if now is not None else time.time())
    _purge(stamp)
    if exp <= stamp:
        raise ToolError("publish.confirm_replay", "确认已过期。未公开发布。")
    if nonce in _USED:
        raise ToolError("publish.confirm_replay", "确认不能重放。未公开发布。")
    school = str(principal.school_id)
    member = str(principal.membership_id)
    payload = f"{school}\n{member}\n{aid}\n{nonce}\n{exp}"
    expected = _mac(payload)
    if not hmac.compare_digest(expected, sig):
        raise ToolError(
            "publish.confirm_mismatch",
            "确认与当前身份或页面不符。未公开发布。",
        )
    _USED[nonce] = float(exp)


def confirm_options(artifact_id: str) -> list[str]:
    short = (artifact_id or "").strip()[:8] or "page"
    return [f"{_YES} {short}", _NO]


def is_confirm_answer(answer: str, artifact_id: str) -> bool:
    chosen = (answer or "").strip()
    yes, no = confirm_options(artifact_id)
    if chosen == no or chosen.startswith(_NO):
        return False
    return chosen == yes


async def require_teacher_confirm(
    principal: Principal,
    *,
    artifact_id: str,
    title: str,
    confirm_token: str | None,
    run_id: str | None,
    emit: Any | None,
) -> str:
    del principal, artifact_id, title, confirm_token, run_id, emit
    raise ToolError(
        "publish.edu_channel_required",
        "公开发布不是 Pico 的能力。学校页面走 Edu 专用申请通道，由校管批准。",
    )
