"""New API channel price tags. No wallet. Missing tag → lock that pipe.

Rates are cost in yuan. Sell = cost × sell_markup. Points = sell × points_per_yuan.
Owner fills real New API channel prices; seeds in config/channel-rates.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from pico_orchestrator.gateway import ToolError

_MILLION = Decimal(1000000)
_MICRO = Decimal(1000000)


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — untrusted JSON/env numbers
        return Decimal(default)


@dataclass(frozen=True)
class ChannelRate:
    id: str
    kind: str
    model: str
    input_yuan_per_million: Decimal
    output_yuan_per_million: Decimal
    cache_read_yuan_per_million: Decimal
    cache_write_yuan_per_million: Decimal
    per_image_yuan: Decimal
    per_call_yuan: Decimal

    def priced(self) -> bool:
        return any(
            v > 0
            for v in (
                self.input_yuan_per_million,
                self.output_yuan_per_million,
                self.cache_read_yuan_per_million,
                self.cache_write_yuan_per_million,
                self.per_image_yuan,
                self.per_call_yuan,
            )
        )


@dataclass(frozen=True)
class RateCard:
    sell_markup: Decimal
    points_per_yuan: Decimal
    channels: tuple[ChannelRate, ...]

    def find(
        self,
        *,
        kind: str | None,
        model: str | None,
        channel_id: str | None = None,
    ) -> ChannelRate | None:
        want_id = (channel_id or "").strip()
        want_kind = (kind or "").strip().lower()
        want_model = (model or "").strip()
        if want_kind == "llm" and (
            not want_model or want_model.lower() in {"pico-fast", "pico-deep", "pico-agent", "pico"}
        ):
            want_model = "gpt-5.6-sol"
        if want_id:
            for row in self.channels:
                if row.id == want_id:
                    return row
            return None
        hits = [
            row
            for row in self.channels
            if (not want_kind or row.kind == want_kind)
            and (not want_model or row.model == want_model)
        ]
        if len(hits) == 1:
            return hits[0]
        if want_model:
            model_hits = [row for row in hits if row.model == want_model]
            if len(model_hits) == 1:
                return model_hits[0]
        return None


_CARD: RateCard | None = None


def default_rates_path() -> Path:
    raw = (os.environ.get("PICO_CHANNEL_RATES_PATH") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[3] / "config" / "channel-rates.json"


def _parse_card(blob: dict[str, Any]) -> RateCard:
    channels: list[ChannelRate] = []
    raw_channels = blob.get("channels")
    if isinstance(raw_channels, list):
        for item in raw_channels:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "").strip()
            kind = str(item.get("kind") or "").strip().lower()
            model = str(item.get("model") or "").strip()
            if not cid or not kind or not model:
                continue
            channels.append(
                ChannelRate(
                    id=cid,
                    kind=kind,
                    model=model,
                    input_yuan_per_million=_dec(item.get("input_yuan_per_million")),
                    output_yuan_per_million=_dec(item.get("output_yuan_per_million")),
                    cache_read_yuan_per_million=_dec(item.get("cache_read_yuan_per_million")),
                    cache_write_yuan_per_million=_dec(item.get("cache_write_yuan_per_million")),
                    per_image_yuan=_dec(item.get("per_image_yuan")),
                    per_call_yuan=_dec(item.get("per_call_yuan")),
                )
            )
    markup = _dec(blob.get("sell_markup"), "2.5")
    if markup <= 0:
        markup = Decimal("2.5")  # 2.5 is exact in decimal; avoid float 2.5
    ppy = _dec(blob.get("points_per_yuan"), "1000")
    if ppy <= 0:
        ppy = Decimal(1000)
    return RateCard(sell_markup=markup, points_per_yuan=ppy, channels=tuple(channels))


def load_rate_card(*, force: bool = False) -> RateCard:
    global _CARD
    if _CARD is not None and not force:
        return _CARD
    inline = (os.environ.get("PICO_CHANNEL_RATES") or "").strip()
    blob: dict[str, Any] | None = None
    if inline:
        try:
            parsed = json.loads(inline)
            if isinstance(parsed, dict):
                blob = parsed
        except json.JSONDecodeError:
            blob = None
    if blob is None:
        path = default_rates_path()
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                blob = parsed
        except (OSError, json.JSONDecodeError):
            blob = None
    _CARD = _parse_card(blob or {})
    return _CARD


def reset_rate_card() -> None:
    global _CARD
    _CARD = None


def require_rate(
    *,
    kind: str,
    model: str | None,
    channel_id: str | None = None,
) -> ChannelRate:
    card = load_rate_card()
    row = card.find(kind=kind, model=model, channel_id=channel_id)
    if row is None or not row.priced():
        raise ToolError(
            "channel.unpriced",
            "该渠道未标价，已停用。请在渠道价签里补上成本后再用。",
        )
    return row


def cost_micro_yuan(
    rate: ChannelRate,
    *,
    kind: str,
    tokens_unknown: bool,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    cached_tokens: int = 0,
    cache_write_tokens: int = 0,
    ok: bool = True,
    image_count: int = 1,
    call_count: int = 1,
) -> int | None:
    """Cost in micro-yuan (1 yuan = 1_000_000). None = cannot price."""
    if not ok:
        return None
    kind_n = (kind or rate.kind or "").strip().lower()
    if kind_n == "search" and rate.per_call_yuan > 0:
        return _yuan_to_micro(rate.per_call_yuan * Decimal(max(1, int(call_count))))
    if kind_n == "image" and (
        tokens_unknown or (prompt_tokens is None and completion_tokens is None and total_tokens is None)
    ):
        if rate.per_image_yuan <= 0:
            return None
        return _yuan_to_micro(rate.per_image_yuan * Decimal(max(1, int(image_count))))
    if tokens_unknown:
        return None
    prompt = 0 if prompt_tokens is None else max(0, int(prompt_tokens))
    output = 0 if completion_tokens is None else max(0, int(completion_tokens))
    cached = min(max(0, int(cached_tokens)), prompt)
    write = min(max(0, int(cache_write_tokens)), max(0, prompt - cached))
    fresh = max(0, prompt - cached - write)
    if prompt == 0 and output == 0 and total_tokens is not None:
        fresh = max(0, int(total_tokens))
        cached = 0
        write = 0
        output = 0
    if fresh == 0 and cached == 0 and write == 0 and output == 0:
        if kind_n == "image" and rate.per_image_yuan > 0:
            return _yuan_to_micro(rate.per_image_yuan * Decimal(max(1, int(image_count))))
        return None
    cost = Decimal(0)
    cost += Decimal(fresh) / _MILLION * rate.input_yuan_per_million
    cost += Decimal(cached) / _MILLION * rate.cache_read_yuan_per_million
    cost += Decimal(write) / _MILLION * rate.cache_write_yuan_per_million
    cost += Decimal(output) / _MILLION * rate.output_yuan_per_million
    if cost <= 0:
        return None
    return _yuan_to_micro(cost)


def sell_millipoints(cost_micro: int, *, markup: Decimal | None = None, points_per_yuan: Decimal | None = None) -> int:
    card = load_rate_card()
    m = markup if markup is not None else card.sell_markup
    ppy = points_per_yuan if points_per_yuan is not None else card.points_per_yuan
    sell_micro = (Decimal(max(0, int(cost_micro))) * m).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    # 1 yuan = 1e6 micro = points_per_yuan points = points_per_yuan * 1000 millipoints
    milli = (sell_micro * ppy * Decimal(1000) / _MICRO).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return int(milli)


def _yuan_to_micro(yuan: Decimal) -> int:
    return int((yuan * _MICRO).quantize(Decimal(1), rounding=ROUND_HALF_UP))
