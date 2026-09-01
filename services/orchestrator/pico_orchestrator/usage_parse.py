"""Canonical token-usage mapping. Statistics only — never money.

Provider blobs (OpenAI Responses / chat.completions / Pi RPC) → one dict
the Pico usage ledger can store. edu-core later rates this; Pico does not.
"""

from __future__ import annotations

from typing import Any

_UI_LANES = frozenset({"pico-fast", "pico-deep", "pico-agent", "pico", "pico-durable-job"})
# Keys that mean "this mapping is already a usage blob" (do not only unwrap .usage).
_USAGE_HINT_KEYS = frozenset(
    {
        "prompt_tokens",
        "completion_tokens",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "totalTokens",
        "input",
        "output",
    }
)
# Terminal RPC kinds whose usage is this Pico turn — not streaming deltas, not session totals.
_TERMINAL_RPC_USAGE_KINDS = frozenset({"agent_end", "compaction_end"})
_ATTR_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "totalTokens",
    "input",
    "output",
    "cached_tokens",
    "reasoning_tokens",
    "cacheRead",
    "cacheWrite",
    "reasoning",
    "estimated",
    "input_tokens_details",
    "output_tokens_details",
    "prompt_tokens_details",
    "completion_tokens_details",
)


def int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def is_ui_lane(model: str | None) -> bool:
    return (model or "").strip().lower() in _UI_LANES


def _from_mapping(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    out: dict[str, Any] = {}
    for key in _ATTR_USAGE_KEYS:
        if hasattr(raw, key):
            out[key] = getattr(raw, key)
    return out or None


def _details_int(details: Any, *names: str) -> int | None:
    blob = _from_mapping(details) or {}
    for name in names:
        n = int_or_none(blob.get(name))
        if n is not None:
            return n
        nested = blob.get(name)
        if isinstance(nested, dict):
            inner = int_or_none(nested.get("tokens") or nested.get("count"))
            if inner is not None:
                return inner
    return None


def _has_numeric_usage_hint(blob: dict[str, Any]) -> bool:
    """True when this dict itself looks like a token blob, not a message wrapper."""
    for key in _USAGE_HINT_KEYS:
        if key not in blob:
            continue
        if int_or_none(blob.get(key)) is not None:
            return True
    return False


def usage_blobs_from_rpc_event(kind: str, raw: Any) -> list[Any]:
    """Harvest this Pico-turn's provider usage from a true-Pi RPC event.

    Only ``agent_end.messages[].usage`` and ``compaction_end`` result usage.
    ``message_update.usage`` is cumulative mid-stream — never harvest it.
    Session-file / get_session_stats totals are not this turn.
    """
    if not isinstance(raw, dict):
        return []
    kind_n = str(kind or "").strip()
    if kind_n not in _TERMINAL_RPC_USAGE_KINDS:
        return []
    blobs: list[Any] = []
    if kind_n == "agent_end":
        packed = raw.get("messages")
        if not isinstance(packed, list):
            result = raw.get("result")
            packed = result.get("messages") if isinstance(result, dict) else None
        if isinstance(packed, list):
            for item in packed:
                if not isinstance(item, dict):
                    continue
                usage = item.get("usage")
                if isinstance(usage, dict):
                    blobs.append(usage)
        if not blobs and isinstance(raw.get("usage"), dict):
            blobs.append(raw["usage"])
        return blobs
    result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
    if isinstance(result.get("usage"), dict):
        blobs.append(result["usage"])
    elif isinstance(raw.get("usage"), dict):
        blobs.append(raw["usage"])
    return blobs


def parse_usage_blob(raw: Any) -> dict[str, Any] | None:
    """Return a canonical usage dict or None when nothing usable is present.

    Canonical keys:
      prompt_tokens, completion_tokens, total_tokens
      cached_tokens, reasoning_tokens (optional extras for edu weights)
      estimated (bool)
    All-zero without estimated → None (honest unknown, not a fake free turn).
    """
    blob = _from_mapping(raw)
    if not blob:
        return None
    # Nested provider wrappers (OpenAI message.usage / Pi assistant.usage).
    # Do not treat list-valued `input` (models.json modalities) as a usage hint.
    if "usage" in blob and not _has_numeric_usage_hint(blob):
        nested = parse_usage_blob(blob.get("usage"))
        if nested is not None:
            return nested
    prompt = int_or_none(blob.get("prompt_tokens"))
    if prompt is None:
        prompt = int_or_none(blob.get("input_tokens"))
    if prompt is None:
        prompt = int_or_none(blob.get("input"))
    completion = int_or_none(blob.get("completion_tokens"))
    if completion is None:
        completion = int_or_none(blob.get("output_tokens"))
    if completion is None:
        completion = int_or_none(blob.get("output"))
    total = int_or_none(blob.get("total_tokens"))
    if total is None:
        total = int_or_none(blob.get("totalTokens"))
    cached = int_or_none(blob.get("cached_tokens"))
    if cached is None:
        cached = int_or_none(blob.get("cacheRead"))
    if cached is None:
        cached = _details_int(
            blob.get("input_tokens_details") or blob.get("prompt_tokens_details"),
            "cached_tokens",
            "cache_read",
            "cache_read_input_tokens",
            "cacheRead",
        )
    reasoning = int_or_none(blob.get("reasoning_tokens"))
    if reasoning is None:
        reasoning = int_or_none(blob.get("reasoning"))
    if reasoning is None:
        reasoning = _details_int(
            blob.get("output_tokens_details") or blob.get("completion_tokens_details"),
            "reasoning_tokens",
            "reasoning",
        )
    estimated = bool(blob.get("estimated"))
    if prompt is None and completion is None and total is None:
        return None
    if not estimated and (prompt or 0) == 0 and (completion or 0) == 0 and (total or 0) == 0:
        return None
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    out: dict[str, Any] = {}
    if prompt is not None:
        out["prompt_tokens"] = prompt
        out["input_tokens"] = prompt
    if completion is not None:
        out["completion_tokens"] = completion
        out["output_tokens"] = completion
    if total is not None:
        out["total_tokens"] = total
    if cached is not None:
        out["cached_tokens"] = cached
    if reasoning is not None:
        out["reasoning_tokens"] = reasoning
    if estimated:
        out["estimated"] = True
    return out


def add_usage(acc: dict[str, Any] | None, piece: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sum per-call usage into a run total. Mixing estimated into real marks estimated."""
    parsed = parse_usage_blob(piece) if piece is not None else None
    if parsed is None:
        return acc
    if not acc:
        return dict(parsed)
    out = dict(acc)
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "input_tokens",
        "output_tokens",
    ):
        a = int_or_none(out.get(key))
        b = int_or_none(parsed.get(key))
        if a is None and b is None:
            continue
        out[key] = (a or 0) + (b or 0)
    if parsed.get("estimated") or out.get("estimated"):
        out["estimated"] = True
    return out


def billed_model_id(ui_or_backend: str | None, backend: str | None = None) -> str | None:
    """Model id edu should rate. Never a Pico lane alias when a backend id exists."""
    backend_n = (backend or "").strip() or None
    raw = (ui_or_backend or "").strip() or None
    if backend_n and not is_ui_lane(backend_n):
        return backend_n
    if raw and not is_ui_lane(raw):
        return raw
    try:
        from pico_orchestrator.provider import resolve_model_id, resolve_provider_for_model

        cfg = resolve_provider_for_model(raw)
        if cfg is None:
            return raw
        resolved = (resolve_model_id(raw, cfg) or "").strip()
        if resolved and not is_ui_lane(resolved):
            return resolved
        product = (cfg.model or "").strip()
        return product or resolved or raw
    except Exception:  # noqa: BLE001 — resolve is best-effort for a label
        return raw


def usage_extra_bits(usage: dict[str, Any] | None) -> dict[str, Any]:
    """Non-money extras for usage_events.extra_json.

    Cache/reasoning come from the canonical parse (Pi ``cacheRead`` / ``reasoning``
    included). ui_model / runtime stay on the raw dict. Never copy cost or rates.
    """
    if not isinstance(usage, dict):
        return {}
    extra: dict[str, Any] = {}
    parsed = parse_usage_blob(usage) or {}
    for key in ("cached_tokens", "reasoning_tokens"):
        val = parsed.get(key)
        if val is None or val == "":
            continue
        extra[key] = val
    for key in ("ui_model", "runtime"):
        val = usage.get(key)
        if val is None or val == "":
            continue
        extra[key] = val
    return extra
