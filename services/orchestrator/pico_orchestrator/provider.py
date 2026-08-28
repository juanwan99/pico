"""Model HTTPS provider adapters. Product default = DeepSeek; Kimi optional fallback."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI

DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_REASONER = "deepseek-reasoner"
DEFAULT_DEEPSEEK_VISION = "deepseek-v4-flash-vision-exp"
DEFAULT_DEEPSEEK_BASE = "https://api.deepseek.com/v1"
KNOWN_DEEPSEEK_MODELS = (
    "deepseek-v4-flash",
    "deepseek-v4-flash-vision-exp",
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
    return bare.startswith(("kimi", "moonshot"))


def is_agent_model(model: str | None) -> bool:
    bare = _bare_model(model)
    return not bare or bare in {"pico-agent", "pico", "pico-fast", "pico-deep"} or bare.startswith("pico-")


def is_openai_responses_model(model: str | None) -> bool:
    """Codex / OpenAI Responses ids (gpt-5.5, gpt-5.6, …). Not DeepSeek."""
    return _bare_model(model).lower().startswith("gpt-")


def uses_openai_responses_brain(cfg: ProviderConfig | None = None) -> bool:
    """True when the product brain is an OpenAI Responses proxy, not DeepSeek.

    Codex-class relays (AIProxy ``base_url=…/openai`` + ``wire_api=responses``)
    keep using the DEEPSEEK_* env slot as the brain key, but Pi must spawn
    ``--provider openai`` and overlay ``baseUrl``.
    """
    target = cfg if cfg is not None else resolve_provider()
    if target is None:
        return False
    base = (target.base_url or "").strip().lower()
    if "deepseek.com" in base:
        return False
    if is_openai_responses_model(target.model):
        return True
    return "/openai" in base


def product_backend_model(*, deep: bool) -> str:
    """Lane backend id. OpenAI Responses brain keeps its configured model."""
    cfg = resolve_provider()
    if cfg is not None and uses_openai_responses_brain(cfg):
        return cfg.model
    return DEFAULT_DEEPSEEK_REASONER if deep else DEFAULT_DEEPSEEK_MODEL


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
        low = str(requested).strip().lower()
        if low == "pico-fast":
            return product_backend_model(deep=False)
        if low == "pico-deep":
            return product_backend_model(deep=True)
        return cfg.model

    bare = _bare_model(requested)
    if not bare:
        return cfg.model

    if cfg.name == "deepseek":
        if is_deepseek_model(bare):
            return bare
        if bare == "pico-fast":
            return product_backend_model(deep=False)
        if bare == "pico-deep":
            return product_backend_model(deep=True)
        # Kimi / other labels remounted onto DeepSeek → use product default
        return cfg.model

    if cfg.name == "kimi":
        if is_kimi_model(bare):
            return bare
        return cfg.model

    return bare


def runtime_policy_for_model(model: str | None) -> dict[str, object]:
    """Return the Pico product policy for a selected model.

    fast: deepseek-v4-flash with thinking off (easy / short)
    deep: deepseek-reasoner with thinking on (hard / multi-step office)
    """
    requested = (model or "").strip()
    low = requested.lower()
    if low == "pico-fast":
        return {
            "ui_model": low,
            "backend_model": product_backend_model(deep=False),
            "thinking": False,
            "max_steps": 12,
            "max_tokens": 8000,
            "max_context": 128000,
            "fallback": product_backend_model(deep=False),
        }
    if low == "pico-deep":
        return {
            "ui_model": low,
            "backend_model": product_backend_model(deep=True),
            "thinking": True,
            "max_steps": 24,
            "max_tokens": 32000,
            "max_context": 256000,
            "fallback": product_backend_model(deep=True),
        }
    if low in {"pico-agent", "pico"}:
        return {
            "ui_model": "pico-agent",
            "backend_model": product_backend_model(deep=True),
            "thinking": True,
            "max_steps": 24,
            "max_tokens": 32000,
            "max_context": 256000,
            "fallback": product_backend_model(deep=True),
        }
    return {
        "ui_model": requested or "pico-fast",
        "backend_model": product_backend_model(deep=False),
        "thinking": False,
        "max_steps": 12,
        "max_tokens": 8000,
        "max_context": 128000,
        "fallback": product_backend_model(deep=False),
    }


def thinking_extra_body(
    model: str | None,
    *,
    thinking: bool | None = None,
) -> dict[str, object]:
    """DeepSeek v4 thinking is on by default. Honor Pico fast/deep policy.

    Direct HTTPS (sidebar json_only) must send this or reasoning tokens eat
    max_tokens and the stream finishes HTTP 200 with empty content.
    Not a global off: pico-deep stays enabled unless the caller overrides.
    """
    if thinking is None:
        thinking = bool(runtime_policy_for_model(model).get("thinking", False))
    return {"thinking": {"type": "enabled" if thinking else "disabled"}}


def should_circuit_break(
    *,
    tool_exec_count: int,
    repeated_no_progress: int,
    wall_seconds: float,
    thinking_on: bool,
) -> bool:
    """Deep mode breaker: stop empty or runaway loops before OOM / infinite stall.

    The guard is intentionally conservative: if the deep lane has no useful tool
    progress and keeps looping, we bail out with a human-readable message.
    """
    if not thinking_on:
        return False
    if tool_exec_count <= 0 and repeated_no_progress >= 2:
        return True
    if wall_seconds >= 180 and tool_exec_count == 0:
        return True
    return repeated_no_progress >= 4


def owned_by_for_model(model_id: str) -> str:
    """Honest provider ownership label for /v1/models (not a fake Kimi brand)."""
    if is_agent_model(model_id):
        return "pico"
    if is_deepseek_model(model_id):
        return "deepseek"
    if is_kimi_model(model_id):
        return "kimi"
    return "pico"


def _messages_for_chat(
    prompt: str,
    *,
    history: list[dict] | None,
    system: str | None,
) -> list[dict]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    for h in history or []:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": prompt})
    return messages


def _responses_instructions_and_input(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Split chat messages into Responses ``instructions`` + ``input``."""
    instructions_parts: list[str] = []
    items: list[dict] = []
    for row in messages:
        role = str(row.get("role") or "")
        content = str(row.get("content") or "")
        if not content:
            continue
        if role == "system":
            instructions_parts.append(content)
            continue
        if role in ("user", "assistant"):
            items.append({"role": role, "content": content})
    if not items:
        items = [{"role": "user", "content": " "}]
    instructions = "\n".join(instructions_parts).strip() or None
    return instructions, items


def _responses_text_delta(event: object) -> str:
    """Yield visible assistant text from an OpenAI Responses stream event."""
    if isinstance(event, dict):
        et = str(event.get("type") or "")
        delta = event.get("delta")
    else:
        et = str(getattr(event, "type", "") or "")
        delta = getattr(event, "delta", None)
    if et not in {"response.output_text.delta", "response.refusal.delta"}:
        return ""
    return str(delta or "")


def _responses_create_kwargs(
    *,
    model_id: str,
    messages: list[dict],
    max_tokens: int,
    thinking: bool | None,
) -> dict[str, object]:
    instructions, input_items = _responses_instructions_and_input(messages)
    kwargs: dict[str, object] = {
        "model": model_id,
        "input": input_items,
        "stream": True,
        "max_output_tokens": max_tokens,
    }
    if instructions:
        kwargs["instructions"] = instructions
    # pico-fast / json_only keep thinking off; pico-deep uses medium (true Pi overlay).
    if thinking is True:
        kwargs["reasoning"] = {"effort": "medium"}
    return kwargs


async def _iter_stream_text(stream: object, *, responses: bool) -> AsyncIterator[str]:
    if responses:
        async for event in stream:  # type: ignore[union-attr]
            piece = _responses_text_delta(event)
            if piece:
                yield piece
        return
    async for chunk in stream:  # type: ignore[union-attr]
        delta = chunk.choices[0].delta.content if getattr(chunk, "choices", None) else None
        if delta:
            yield delta


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc)
    low = msg.lower()
    return "401" in msg or ("invalid" in low and "key" in low) or "unauthorized" in low


def _is_model_missing_error(exc: Exception) -> bool:
    msg = str(exc)
    low = msg.lower()
    return "404" in msg or ("model" in low and "not" in low) or "invalid_request" in low


async def stream_chat(
    prompt: str,
    *,
    max_tokens: int = 1024,
    history: list[dict] | None = None,
    system: str | None = None,
    model: str | None = None,
    thinking: bool | None = None,
) -> AsyncIterator[str]:
    """Stream assistant text deltas from the real model API (token-level).

    Raises RuntimeError if no API key is configured.

    If the UI still selects a broken Kimi model while DeepSeek is the product
    brain and has a working key, fall back to DeepSeek rather than failing the
    default path with a generic service error.
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

    messages = _messages_for_chat(prompt, history=history, system=system)
    model_id = resolve_model_id(model, cfg)
    extra_body = thinking_extra_body(model, thinking=thinking)

    async def _open_stream(provider: ProviderConfig, mid: str):
        client = AsyncOpenAI(api_key=provider.api_key, base_url=provider.base_url)
        if uses_openai_responses_brain(provider):
            kwargs = _responses_create_kwargs(
                model_id=mid,
                messages=messages,
                max_tokens=max_tokens,
                thinking=thinking,
            )
            return await client.responses.create(**kwargs)
        return await client.chat.completions.create(
            model=mid,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )

    try:
        stream = await _open_stream(cfg, model_id)
    except Exception as e:
        # Broken Kimi key / unavailable kimi model → remount product DeepSeek.
        fallback = _deepseek_config()
        can_fallback = (
            cfg.name == "kimi"
            and fallback is not None
            and (_is_auth_error(e) or _is_model_missing_error(e))
        )
        if can_fallback:
            try:
                stream = await _open_stream(fallback, fallback.model)
            except Exception as fallback_exc:  # noqa: BLE001 — surface as user RuntimeError
                e = fallback_exc
            else:
                cfg = fallback
                model_id = fallback.model
                async for piece in _iter_stream_text(
                    stream, responses=uses_openai_responses_brain(cfg)
                ):
                    yield piece
                return

        msg = str(e)
        low = msg.lower()
        if _is_auth_error(e):
            raise RuntimeError(
                f"{cfg.name} 密钥无效或未授权，请检查服务端 API Key。"
            ) from e
        if _is_model_missing_error(e):
            raise RuntimeError(
                f"模型不可用：{model_id}。请检查 DEEPSEEK_MODEL / KIMI_MODEL。"
            ) from e
        if "429" in msg or "rate" in low:
            raise RuntimeError("模型调用过于频繁，请稍后再试。") from e
        raise RuntimeError(f"模型调用失败：{msg}") from e

    async for piece in _iter_stream_text(
        stream, responses=uses_openai_responses_brain(cfg)
    ):
        yield piece
