"""Teacher-visible copy never names a model, a vendor or the plumbing behind it.

Owner 2026-10-14 14:28: a teacher saw「主渠道（gpt-5.6-sol）…备用模型 gemini-3.8-flash」.
Switching models must be invisible; errors say what to do, not which pipe broke.
Raw detail stays in run events / logs for us.
"""

from __future__ import annotations

import re

GENERIC_RETRY = "这次没完成，请再发一次。不是你的问题写错。"
RETRYING = "（稍等，正在重试）\n"

# Model / vendor names, relay plumbing, HTTP codes and env-style names.
_LEAK_PATTERNS = (
    r"gpt",
    r"o[134]-",
    r"gemini",
    r"grok",
    r"claude",
    r"openai",
    r"anthropic",
    r"google",
    r"deepseek",
    r"kimi",
    r"moonshot",
    r"qwen",
    r"glm",
    r"zhipu",
    r"doubao",
    r"siliconflow",
    r"aiproxy",
    r"litellm",
    r"new ?api",
    r"x\.ai",
    r"通义",
    r"千问",
    r"智谱",
    r"豆包",
    r"硅基",
    r"文心",
    r"模型",
    r"主渠道",
    r"渠道",
    r"中转",
    r"网关",
    r"上游",
    r"首包",
    r"api ?key",
    r"api error",
    r"error code",
    r"http ?\d{3}",
    r"(?<!\d)(?:4[0-2]\d|429|5\d\d)(?!\d)",
)
_LEAK_RE = re.compile("|".join(f"(?:{p})" for p in _LEAK_PATTERNS), re.IGNORECASE)
# Env-style names (PICO_IMAGE_GATEWAY_URL); case-sensitive so snake_case words pass.
_ENV_RE = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]{2,}\b")


def leak_terms(text: str | None) -> list[str]:
    """Every leaking fragment in ``text`` (empty when the copy is clean)."""
    s = text or ""
    return [m.group(0) for m in _LEAK_RE.finditer(s)] + _ENV_RE.findall(s)


def leaks(text: str | None) -> bool:
    return bool(leak_terms(text))


def teacher_safe(text: str | None, fallback: str = GENERIC_RETRY) -> str:
    """``text`` if a teacher may see it as is, else ``fallback``."""
    s = (text or "").strip()
    if not s or leaks(s):
        return fallback
    return text or ""
