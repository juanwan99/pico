# Contract: usage export (Pico meter → edu-core)

```
STATUS: FROZEN
VERSION: 1.0
DATE: 2026-08-29
OWNER: Pico meters · edu-core bills
SCHEMA: packages/contracts/schemas/usage-export.schema.json
PARENT: docs/USAGE-LEDGER.md
```

## Split

| Pico (this contract) | edu-core (not this repo) |
|----------------------|--------------------------|
| Unique usage meter: who / school / kind / model / tokens · derived `points` | Wallet, debit, invoices (same `points` number, no second conversion) |
| Honest `tokens_unknown` / `estimated` | Rate table, 点, SKU |
| Pull API below | Pull on a schedule; never a second AI run ledger |

Pico **must not** grow price/currency/wallet columns. edu **must not** persist a parallel Task/Run tree for product AI.

`points` on each event is Pico's already-converted meter (three decimals). edu debits that number as-is. **Do not multiply again.** null `points` is unknown, not zero. Conversion lives only in Pico (`points_meter.py`). **Which units:** this-turn teacher text (`extra.user_chars`, same units as the composer quote) plus this-turn `completion_tokens`. Provider `prompt_tokens` / `total_tokens` stay on the row for ops (always-on suitcase) and **must not** be re-multiplied. Export must not include rate / scale / formula fields. Teacher-facing Pico JSON omits token columns and `user_chars`.

## Event (one row)

Same shape as `GET /v1/usage/events` plus `schema: pico.usage.v1`.

| Field | Notes |
|-------|--------|
| `kind` | `llm` \| `search` \| `sandbox` \| `image` \| `api` \| `other` |
| `model` | **Backend** model id (`gpt-5.6-sol`, `gemini-…-image`). Not `pico-fast`. |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | Integers or `null` |
| `tokens_unknown` | Provider did not return usage (agent/Pi often). **Do not treat as zero.** |
| `estimated` | Always `false` after scrub. Pico no longer writes char/4. **Do not bill.** |
| `extra.ui_model` | Lane alias `pico-fast` / `pico-deep` when applicable |
| `extra.cached_tokens` / `extra.reasoning_tokens` | Optional ops fields. Suitcase — **not** billed into `points`. |
| `extra.user_chars` | Optional. Teacher text length this turn. Used by Pico `points`; not a token column. |
| `points` | String `N.NNN` or `null`. **edu debits this as-is.** Do not rescale. |
| `billing` | Always `false` |

No `price` / `currency` / `cost` / `charge` / `amount`.

## Pull

```
GET /v1/internal/usage/export
Authorization: Bearer <PICO_HOOK_SERVICE_TOKEN>
```

Query: `school_id` · `kind` · `since` (ISO-8601) · `after_id` · `limit` (1–1000, default 200).

Order: `created_at ASC, id ASC`. `next` is `{ after_id, since }` or `null`.

## Phase 3

edu implements the wallet client. Pico does not push, does not store a balance, does not write edu-cloud. Pico attaches derived `points`; edu must not keep a second conversion.
