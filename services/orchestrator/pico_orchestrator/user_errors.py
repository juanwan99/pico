"""Map technical failures to short, user-visible Chinese messages.

Internal logs/events may keep raw detail; UI should prefer `user_message`.
"""

from __future__ import annotations


def user_message_for_error(raw: str | None, *, code: str | None = None) -> str:
    text = (raw or "").strip()
    low = text.lower()
    c = (code or "").lower()

    if "输入过长" in text or "too long" in low or "max_prompt" in low or c == "prompt_too_long":
        return "输入过长。请缩短问题后重试；系统不会静默截断后继续执行。"
    if "unable to open database file" in low:
        return "服务繁忙，请稍后重试。"
    if code == "token_cap" or "token cap" in low:
        return "本次回答超出长度上限，请缩短问题或新开对话后再试。"
    if "timeout" in low:
        return "处理超时。请重试，或把问题拆短一些。"
    if "cancelled" in low or c == "cancelled":
        return "已停止生成。"
    if (
        "no kimi_api_key" in low or "尚未配置" in text or "kimi_api_key" in low
        or "no deepseek" in low
        or "blocked s1" in low
        or "api key" in low
        or "authentication" in low
        or "unauthorized" in low
        or "401" in low
    ):
        return "模型服务未配置或密钥无效。请管理员配置 KIMI_API_KEY / DEEPSEEK_API_KEY 后重试。"
    if "rate limit" in low or "429" in low:
        return "模型调用繁忙（限流）。请稍后再试。"
    if "connect" in low or "connection" in low or "network" in low or "timed out" in low:
        return "无法连接模型服务。请检查网络或稍后重试。"
    if "owner was lost" in low or "api restart" in low or "greenlet" in low:
        return "服务刚完成维护或重启，请重新打开任务后重试。"
    if "not found" in low:
        return "找不到对应的会话或运行记录。"
    if (
        "database is locked" in low
        or "operationalerror" in low
        or "sqlite3" in low
        or "disk i/o" in low
    ):
        return "服务繁忙，请稍后重试。若刚点了停止，请刷新查看是否已结束。"
    if "missing bearer" in low or "invalid token" in low or "expired" in low:
        return "登录已失效，请打开设置重新获取令牌。"
    if "cross_school" in low or "cross-school" in low or "tenant" in low:
        return "跨校访问已被拒绝（租户隔离）。"
    if "max_steps" in low or "max steps" in low or "step limit" in low or "too many steps" in low:
        return "步骤过多已停止。请把任务拆短后重试。"
    if "max_tokens" in low or "token cap" in low or c == "token_cap":
        return "本次回答超出长度上限，请缩短问题或新开对话后再试。"
    if (
        c in ("kimi.event_contract", "kimi.runtime_error")
        or "event_contract" in low
        or "kimi.runtime" in low
        or "filenotfound" in low
        or ("no such file" in low and any(x in low for x in ("agent", "yaml", "system.md", "pico-kimi")))
    ):
        return "智能体任务未正常完成，请重试。若持续失败请联系管理员。"
    if not text:
        return "出了点问题，请重试。若持续失败，请联系管理员。"
    # Keep short; avoid dumping stack traces
    if "traceback" in low or len(text) > 180:
        return "服务暂时出错，请重试。详情已记入运行日志。"
    return f"未能完成：{text[:160]}"


def enrich_fail_payload(payload: dict) -> dict:
    """Ensure failed run.status / run.error payloads expose user_message."""
    from pico_orchestrator.redact import redact_tenant_text

    out = dict(payload)
    raw = out.get("reason") or out.get("error") or out.get("message")
    code = out.get("code") if isinstance(out.get("code"), str) else None
    if out.get("status") == "failed" or "error" in out or out.get("reason"):
        msg = user_message_for_error(str(raw) if raw else None, code=code)
        out.setdefault("user_message", redact_tenant_text(msg))
    return out
