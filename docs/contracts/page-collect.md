# Contract: page collect envelope (Pico land → edu-core)

```
STATUS: FROZEN
VERSION: 1.0
DATE: 2026-09-01
OWNER: Pico attaches · edu-core stores + collects
SCHEMA: packages/contracts/schemas/page-collect.schema.json
CARD: T-PAGE-COLLECT-LAND #842
```

## Split

| Pico (this contract) | edu-core (not this repo) |
|----------------------|--------------------------|
| Teacher `@` named school files; generate HTML; land grey draft | Materials, display page, parent send, answers |
| Attach join keys on `POST /v1/pico/membership/land` | Persist keys on the grey page; public collect later |
| Unique AI ledger (Task / Artifact) | Business SoT (page / roster / answers) |

Pico does **not** mint exam/question/parent ids. Pico does **not** publish the school page. Pico does **not** store grades.

First period join is **page-level**: which display page came from which `@`'d item ids. Per-question refs are out of this version.

## Land extra fields

Same POST as today (`title`, `filename`, `kind`, `field_id`, `item_id`, `body_html` / `content_b64`) plus:

| Field | Required | Notes |
|-------|----------|--------|
| `source_item_ids` | yes | UUID array. This conversation's named ids. Empty `[]` if none `@`'d. Pico does not invent. |
| `pico_artifact_id` | no | Pico HTML/office Artifact UUID when land is from 我的文件 / that artifact |
| `pico_task_id` | no | Pico Task UUID when known |
| `collect_fields` | no | Optional; may be omitted or `[]`. See below |

`source_item_ids` max 12 (same cap as named `@`). Unknown extra keys: ignore (old edu still lands the page).

### `collect_fields[]` (optional)

| Field | Notes |
|-------|--------|
| `key` | Form `name` on the page |
| `ref` | If present, must be one of `source_item_ids` |
| `value_kind` | `string` \| `string[]` \| `number` \| `bool` |

Empty / omitted = whole page is one bag; edu keys answers by page id.

## Pico duties

1. On land, copy session `named_ids` → `source_item_ids` (sanitize UUIDs). Do not ask the model to rename them.
2. When the teacher 转到学校 an artifact, send that `pico_artifact_id`.
3. Keep grey-draft-only. Do not call school publish / pin-guardians.
4. Pico public `/p/{id}/collect` stays a separate teacher-link path. Not this contract.

## edu-core duties (other repo)

1. Accept the extra fields; persist on the grey display page (not `query_blocks`).
2. Keep `landed=true` and `green=false`. Public still needs school-admin review.
3. Later: `POST /p/:slug/collect` lands answers in edu keyed by `page_id` + snapshot `source_item_ids`.

## Phase

| Slice | Where |
|-------|--------|
| 1 Attach envelope on land | Pico (this card) |
| 2 Persist envelope on grey page | edu-core |
| 3 Public collect POST | edu-core |
| 4 Question-level `ref` | later; needs structured ids on excerpts |
