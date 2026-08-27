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
        return "本次回答超出长度上限。可点「再跑一次」，或缩短问题后重试。"
    if c == "timeout" or "timeout" in low or "timed out" in low:
        return (
            "处理超时。可点「再跑一次」继续生成，"
            "或把任务拆短；交付类任务默认预算约 15 分钟。"
        )
    if "cancelled" in low or c == "cancelled":
        # Distinct from input-bar「停止生成」(screen-only): this is ledger cancel.
        return "云端任务已停止。需要结果时可点「重新运行」。"
    if c == "image.unsupported_tier" or "只有 cheap" in text:
        return "出图只有 cheap / high 两档。不能编造图片。"
    if c.startswith("diagram.") or "结构图" in text:
        if c == "diagram.timeout" or "超时" in text:
            return "结构图超时。请稍后重试，不能假装画出结构图。"
        if c == "diagram.unsupported":
            return text or "这一档只支持 mermaid。D2 还没接，不能假装画出结构图。"
        if c == "diagram.parse":
            return text or "这段结构图语法不对，我没画出来。"
        return text or "这次没能画出结构图。请稍后重试，不能假装画出来。"
    # Image / office before generic「未配置」so SILICONFLOW 无钥不会装成模型钥。
    if (
        c.startswith("image.")
        or "siliconflow" in low
        or "不能编造" in text
        or "出图服务" in text
    ):
        if c == "image.timeout" or "超时" in text:
            return "出图超时。请稍后重试，不能编造图片。"
        if c in ("image.provider", "image.invalid") and "未配置" not in text:
            return "这次没能出图。请稍后重试，不能编造图片。"
        return "出图服务未配置。请管理员在主机写入密钥后重试，不能编造图片。"
    if c in ("office.timeout", "artifact.not_ooxml", "artifact.not_binary", "artifact.not_found") or (
        "找不到" in text and ("文件" in text or "原件" in text or "word" in low or "ppt" in low)
    ):
        if c == "office.timeout":
            return "改文档超时。请换更小的文件或稍后再试。"
        return "找不到可改的 Word/PPT 原件。请先在工作台上传后再改。"
    if (
        "no kimi_api_key" in low or "尚未配置" in text or "kimi_api_key" in low
        or "no deepseek" in low
        or "deepseek_api_key" in low
        or "blocked s1" in low
        or "api key" in low
        or "authentication" in low
        or "unauthorized" in low
        or "401" in low
        or "model.unconfigured" in low
        or c == "model.unconfigured"
    ):
        return "模型服务未配置或密钥无效。请管理员配置 DEEPSEEK_API_KEY（推荐）或 KIMI_API_KEY 后重试。"
    if "rate limit" in low or "429" in low or c in ("rate_limit", "concurrency_limit"):
        if c == "concurrency_limit" or "concurrency" in low:
            return "当前对话繁忙（并发已满）。请稍后再试，或关闭其他进行中的任务。"
        return "请求过于频繁或模型限流。请稍后再试，勿并行轰炸。"
    if c in (
        "runtime.emergency_noop",
        "runtime.loop_removed",
        "runtime.kimi_required",
        "runtime.pi_required",
        "runtime.not_allowlisted",
    ):
        return "多智能体运行时当前不可用。请确认 Pi 编排已开启，或联系管理员。"
    if "connect" in low or "connection" in low or "network" in low:
        return "无法连接模型服务。请检查网络或稍后重试。"
    if (
        c == "api.restart"
        or "owner was lost" in low
        or "api restart" in low
        or "greenlet" in low
        # LibreChat stream death after process kill (main bubble often shows this)
        or "terminated" in low
        or "processing the request: terminated" in low
    ):
        return (
            "服务维护或重启导致本次任务中断。"
            "请点「重新运行」继续；刷新后侧栏与主区状态应一致。"
        )
    if c in ("kb.miss", "kb.not_found") or "honest_miss" in low or "未在已挂载" in text:
        return "未在已挂载材料中找到依据。请先生成或上传材料后再问，或换关键词。"
    if c.startswith("mcp.") or "mcp allowlist" in low or "mcp_bridge" in low:
        return "MCP 工具当前不可用或不在白名单。请联系管理员检查 PICO_MCP_ALLOWLIST。"
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
    if (
        c in ("kimi.max_steps", "max_steps", "pi.max_steps")
        or "max_steps" in low
        or "max steps" in low
        or "step limit" in low
        or "too many steps" in low
        or "reached the step limit" in low
    ):
        return "步骤过多已停止。可点「再跑一次」继续，或把任务拆成更小步骤。"
    if c in ("pi.no_progress", "circuit_breaker", "circuit.breaker") or "熔断" in text:
        return (
            "深度模式长时间无有效进展，已自动熔断以避免空转。"
            "可点「再跑一次」，或改用 Pico 快速档重试。"
        )
    if "max_tokens" in low or "token cap" in low or c == "token_cap":
        return "本次回答超出长度上限。可点「再跑一次」，或缩短问题后重试。"
    if (
        c in ("kimi.event_contract", "kimi.runtime_error", "pi.runtime_error", "pi.empty_response")
        or "event_contract" in low
        or "kimi.runtime" in low
        or "pi.runtime" in low
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
