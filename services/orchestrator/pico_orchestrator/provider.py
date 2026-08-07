"""Model HTTPS provider adapters. Product default = DeepSeek; Kimi optional fallback."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI

DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE = "https://api.deepseek.com/v1"
KNOWN_DEEPSEEK_MODELS = (
    "deepseek-chat",
    "deepseek-reasoner",
)

# Optional fallback (legacy / dual-key ops)
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


def _bare_model(requested: str | None) -> str:
    req = (requested or "").strip()
    if "/" in req:
        return req.split("/")[-1]
    return req


def is_deepseek_model(model: str | None) -> bool:
    bare = _bare_model(model).lower()
    if not bare:
        return False
    if bare in {m.lower() for m in KNOWN_DEEPSEEK_MODELS}:
        return True
    return bare.startswith("deepseek")


def is_kimi_model(model: str | None) -> bool:
    bare = _bare_model(model).lower()
    if not bare:
        return False
    if bare in {m.lower() for m in KNOWN_KIMI_MODELS}:
        return True
    return bare.startswith("kimi") or bare.startswith("moonshot")


def is_agent_model(model: str | None) -> bool:
    bare = _bare_model(model)
    return not bare or bare in {"pico-agent", "pico"} or bare.startswith("pico-")


def _deepseek_config() -> ProviderConfig | None:
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not ds_key:
        return None
    return ProviderConfig(
        name="deepseek",
        api_key=ds_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE).strip()
        or DEFAULT_DEEPSEEK_BASE,
        model=os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip()
        or DEFAULT_DEEPSEEK_MODEL,
    )


def _kimi_config() -> ProviderConfig | None:
    kimi_key = os.environ.get("KIMI_API_KEY", "").strip() or os.environ.get(
        "MOONSHOT_API_KEY", ""
    ).strip()
    if not kimi_key:
        return None
    return ProviderConfig(
        name="kimi",
        api_key=kimi_key,
        base_url=os.environ.get("KIMI_BASE_URL", DEFAULT_KIMI_BASE).strip()
        or DEFAULT_KIMI_BASE,
        model=os.environ.get("KIMI_MODEL", DEFAULT_KIMI_MODEL).strip() or DEFAULT_KIMI_MODEL,
    )


def resolve_provider() -> ProviderConfig | None:
    """Prefer DeepSeek (product brain); fall back to Kimi if only that key exists.

    Override order with ``PICO_MODEL_PROVIDER=deepseek|kimi`` when both keys set.
    """
    prefer = (os.environ.get("PICO_MODEL_PROVIDER") or "deepseek").strip().lower()
    deepseek = _deepseek_config()
    kimi = _kimi_config()

    if prefer == "kimi":
        return kimi or deepseek
    # default deepseek first
    return deepseek or kimi


def resolve_provider_for_model(requested: str | None) -> ProviderConfig | None:
    """Pick the HTTPS provider that owns the requested model family.

    Critical: never send a Kimi model id to DeepSeek (or the reverse). That
    mismatch is the owner-facing "服务出错" when the UI still defaults to
    kimi-k2.x while ``PICO_MODEL_PROVIDER=deepseek``.
    """
    if is_agent_model(requested):
        return resolve_provider()

    if is_deepseek_model(requested):
        cfg = _deepseek_config()
        if cfg is not None:
            return cfg
        # DeepSeek selected but no key — do not silently call Kimi with a
        # deepseek-* model name.
        return None

    if is_kimi_model(requested):
        cfg = _kimi_config()
        if cfg is not None:
            return cfg
        # Legacy UI default (kimi-k2.x) with only DeepSeek configured:
        # remount onto the product default provider so default chat works
        # without requiring operators to wipe every user preference first.
        # Brand honesty is handled by listing DeepSeek first and owned_by.
        fallback = _deepseek_config()
        if fallback is not None:
            return fallback
        return None

    # Unknown / custom id → preferred product provider
    return resolve_provider()


def resolve_model_id(requested: str | None, cfg: ProviderConfig) -> str:
    """Pick model for this request: UI selection if it matches provider, else default.

    Prevents ``kimi-k2.6`` from being forwarded to the DeepSeek HTTPS API when the
    only available key (or remount fallback) is DeepSeek.
    """
    if is_agent_model(requested):
        return cfg.model

    bare = _bare_model(requested)
    if not bare:
        return cfg.model

    if cfg.name == "deepseek":
        if is_deepseek_model(bare):
            return bare
        # Kimi / other labels remounted onto DeepSeek → use product default
        return cfg.model

    if cfg.name == "kimi":
        if is_kimi_model(bare):
            return bare
        return cfg.model

    return bare


def owned_by_for_model(model_id: str) -> str:
    """Honest provider ownership label for /v1/models (not a fake Kimi brand)."""
    if is_agent_model(model_id):
        return "pico"
    if is_deepseek_model(model_id):
        return "deepseek"
    if is_kimi_model(model_id):
        return "kimi"
    return "pico"


async def stream_chat(
    prompt: str,
    *,
    max_tokens: int = 1024,
    history: list[dict] | None = None,
    system: str | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream assistant text deltas from the real model API (token-level).

    Raises RuntimeError if no API key is configured.
    """
    cfg = resolve_provider_for_model(model)
    if cfg is None:
        if is_kimi_model(model) and _deepseek_config() is None:
            raise RuntimeError(
                "Kimi 模型未配置密钥：请管理员配置 KIMI_API_KEY，"
                "或将默认模型改为 deepseek-chat（推荐）。"
            )
        if is_deepseek_model(model) and _kimi_config() is None:
            raise RuntimeError(
                "DeepSeek 模型未配置密钥：请管理员配置 DEEPSEEK_API_KEY（推荐）。"
            )
        raise RuntimeError(
            "尚未配置模型密钥：请在服务端设置 DEEPSEEK_API_KEY（推荐）"
            "或 KIMI_API_KEY / MOONSHOT_API_KEY。密钥只放服务端，勿写入前端。"
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
    except Exception as e:
        msg = str(e)
        low = msg.lower()
        if "401" in msg or ("invalid" in low and "key" in low) or "unauthorized" in low:
            raise RuntimeError(
                f"{cfg.name} 密钥无效或未授权，请检查服务端 API Key。"
            ) from e
        if "404" in msg or ("model" in low and "not" in low):
            raise RuntimeError(
                f"模型不可用：{model_id}。请检查 DEEPSEEK_MODEL / KIMI_MODEL。"
            ) from e
        if "429" in msg or "rate" in low:
            raise RuntimeError("模型调用过于频繁，请稍后再试。") from e
        raise RuntimeError(f"模型调用失败：{msg}") from e

    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
