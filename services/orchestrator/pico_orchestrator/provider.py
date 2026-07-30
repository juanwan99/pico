"""Model HTTPS provider adapters (Kimi first, DeepSeek fallback). Keys server-side only."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI

# Current Moonshot / Kimi API model IDs (2026). Prefer kimi-* for new accounts.
DEFAULT_KIMI_MODEL = "kimi-k2.6"
DEFAULT_KIMI_BASE = "https://api.moonshot.cn/v1"
KNOWN_KIMI_MODELS = (
    "kimi-k3",
    "kimi-k2.7-code",
    "kimi-k2.7-code-highspeed",
    "kimi-k2.6",
    "kimi-k2.5",
    "moonshot-v1-8k",
    "moonshot-v1-32k",
    "moonshot-v1-128k",
    "moonshot-v1-8k-vision-preview",
    "moonshot-v1-32k-vision-preview",
    "moonshot-v1-128k-vision-preview",
)


@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str


def resolve_provider() -> ProviderConfig | None:
    kimi_key = os.environ.get("KIMI_API_KEY", "").strip() or os.environ.get(
        "MOONSHOT_API_KEY", ""
    ).strip()
    if kimi_key:
        return ProviderConfig(
            name="kimi",
            api_key=kimi_key,
            base_url=os.environ.get("KIMI_BASE_URL", DEFAULT_KIMI_BASE).strip()
            or DEFAULT_KIMI_BASE,
            model=os.environ.get("KIMI_MODEL", DEFAULT_KIMI_MODEL).strip() or DEFAULT_KIMI_MODEL,
        )
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if ds_key:
        return ProviderConfig(
            name="deepseek",
            api_key=ds_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        )
    return None


def resolve_model_id(requested: str | None, cfg: ProviderConfig) -> str:
    """Pick model for this request: UI selection if sensible, else provider default."""
    req = (requested or "").strip()
    if not req or req in {"pico-agent", "pico"} or req.startswith("pico-"):
        return cfg.model
    # LibreChat sometimes prefixes openAI/
    if "/" in req:
        req = req.split("/")[-1]
    return req


async def stream_chat(
    prompt: str,
    *,
    max_tokens: int = 1024,
    history: list[dict] | None = None,
    system: str | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream assistant text deltas from the real model API (token-level).

    Raises RuntimeError if no API key is configured (S1 BLOCKED).
    """
    cfg = resolve_provider()
    if cfg is None:
        raise RuntimeError(
            "尚未配置 Kimi 密钥：请在服务端设置 KIMI_API_KEY（或 MOONSHOT_API_KEY）。"
            "密钥只放服务端，勿写入前端。"
        )
    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    model_id = resolve_model_id(model, cfg)
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    for h in history or []:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": prompt})
    try:
        stream = await client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
        )
    except Exception as e:  # noqa: BLE001
        # Surface readable Chinese for common failures
        msg = str(e)
        low = msg.lower()
        if "401" in msg or "invalid" in low and "key" in low or "unauthorized" in low:
            raise RuntimeError("Kimi 密钥无效或未授权，请检查 KIMI_API_KEY。") from e
        if "404" in msg or "model" in low and "not" in low:
            raise RuntimeError(f"模型不可用：{model_id}。请换 kimi-k2.6 / kimi-k3 等当前型号。") from e
        if "429" in msg or "rate" in low:
            raise RuntimeError("Kimi 调用过于频繁，请稍后再试。") from e
        raise RuntimeError(f"Kimi 调用失败：{msg}") from e

    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
