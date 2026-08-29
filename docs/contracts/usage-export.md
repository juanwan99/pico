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
| Unique usage meter: who / school / kind / model / tokens | Points, wallets, price, debit, invoices |
| Honest `tokens_unknown` / `estimated` | Rate table, 点, SKU |
| Pull API below | Pull on a schedule; never a second AI run ledger |

Pico **must not** grow price/currency/wallet columns. edu **must not** persist a parallel Task/Run tree for product AI.

## Event (one row)

Same shape as `GET /v1/usage/events` plus `schema: pico.usage.v1`.

| Field | Notes |
|-------|--------|
| `kind` | `llm` \| `search` \| `sandbox` \| `image` \| `api` \| `other` |
| `model` | **Backend** model id (`gpt-5.6-sol`, `gemini-…-image`). Not `pico-fast`. |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | Integers or `null` |
| `tokens_unknown` | Provider did not return usage (agent/Pi often). **Do not treat as zero.** |
| `estimated` | Char/4 last resort. **Do not bill as native usage.** |
| `extra.ui_model` | Lane alias `pico-fast` / `pico-deep` when applicable |
| `extra.cached_tokens` / `extra.reasoning_tokens` | Optional; edu may weight |
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

edu implements the client. Pico does not push, does not convert 点, does not write edu-cloud.
