"""Model HTTPS provider adapters (Kimi first, DeepSeek fallback). Keys server-side only."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str


def resolve_provider() -> ProviderConfig | None:
    kimi_key = os.environ.get("KIMI_API_KEY", "").strip()
    if kimi_key:
        return ProviderConfig(
            name="kimi",
            api_key=kimi_key,
            base_url=os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
            model=os.environ.get("KIMI_MODEL", "moonshot-v1-8k"),
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


async def stream_chat(prompt: str, *, max_tokens: int = 256) -> AsyncIterator[str]:
    """Stream assistant text deltas from the real model API.

    Raises RuntimeError if no API key is configured (S1 BLOCKED).
    """
    cfg = resolve_provider()
    if cfg is None:
        raise RuntimeError(
            "BLOCKED S1: no KIMI_API_KEY or DEEPSEEK_API_KEY configured "
            "(mock is not a substitute)"
        )
    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    stream = await client.chat.completions.create(
        model=cfg.model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=max_tokens,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
