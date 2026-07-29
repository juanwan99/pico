# Contract: AI Facts Ledger

```
STATUS: FROZEN
VERSION: 1.0
OWNER: Pico only (unique AI ledger — never dual-run with edu AI)
SCHEMA: packages/contracts/schemas/event.schema.json
```

## 1. Ownership

| Fact | Owner | Consumer |
|------|-------|----------|
| Task / Run / Event / Artifact | **Pico** | Pico UI; edu may deep-link |
| ChangeProposal + Audit (AI-side) | **Pico** | edu receives handoff in Phase 3 |
| Students / exams / grades / membership | **edu-cloud** | Pico tools read via adapters |

**Invariant:** edu MUST NOT persist a parallel Run/Event ledger for product AI after Phase 3 cutover.

## 2. Entities

### Task

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid string | PK |
| `school_id` | string | from token at create |
| `membership_id` | string | creator |
| `title` | string | |
| `created_at` / `updated_at` | ISO-8601 datetime | |

### Run

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid string | PK |
| `task_id` | uuid | FK Task |
| `status` | enum | `queued` \| `running` \| `succeeded` \| `failed` \| `cancelled` |
| `model` | string | provider label |
| `prompt` | string | user prompt snapshot |
| `error` | string? | |
| `token_usage` | object | e.g. `{ "total_tokens": n }` |
| `cancel_requested` | bool | |
| `started_at` / `ended_at` | datetime? | |

Terminal statuses: `succeeded` | `failed` | `cancelled`.

### Event (ordered)

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | PK |
| `run_id` | uuid | FK Run |
| `seq` | int | **monotonic per run**, starts at 1 |
| `type` | string | see catalog |
| `payload` | object | type-specific |
| `created_at` | datetime | |

### Artifact

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | |
| `task_id` / `run_id` | uuid | |
| `kind` | string | `doc` \| `table` \| `report` \| … |
| `title` | string | |
| `inline` | string? | small Phase 1 body |
| `uri` | string? | Phase 3 object storage optional |

### ChangeProposal (AI-side)

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | |
| `school_id` / `membership_id` | string | |
| `task_id` / `run_id` | uuid? | optional links |
| `title` / `summary` | string | |
| `payload` | object | proposed business delta (not applied) |
| `status` | enum | `proposed` \| `confirmed` \| `rejected` |
| `confirmed_at` / `confirmed_by` | optional | |
| `audit` | array | append-only human actions |

## 3. Event type catalog (Phase 1+)

| type | payload (min) | Meaning |
|------|----------------|---------|
| `run.status` | `{ status, reason? }` | lifecycle |
| `agent.step` | `{ step, phase? }` | multi-step progress |
| `message.delta` | `{ text }` | assistant partial/final chunk |
| `message.final` | `{ text }` | optional rollup |
| `tool.call` | `{ tool, arguments, call_id? }` | gateway inbound |
| `tool.result` | `{ tool, ok, result? \| code?, message? }` | gateway outbound |
| `auth.deny` | `{ code, message, token_school_id, ... }` | cross-school etc. |
| `artifact.created` | `{ artifact_id, title, kind }` | product surfaced |
| `change.proposed` | `{ change_id, title }` | S7 |
| `run.cancel_requested` | `{}` | user cancel |
| `run.error` | `{ error, retry? }` | provider errors |

## 4. HTTP surface (stable for integrators)

| Method | Path | Scope | Notes |
|--------|------|-------|-------|
| POST | `/v1/tasks` | `ai:run` | create Task+Run; starts loop |
| GET | `/v1/tasks` | `ai:read` | list by school |
| GET | `/v1/tasks/{id}` | `ai:read` | + artifacts |
| GET | `/v1/tasks/{id}/runs` | `ai:read` | |
| GET | `/v1/runs/{id}` | `ai:read` | |
| POST | `/v1/runs/{id}/cancel` | `ai:run` | |
| GET | `/v1/runs/{id}/events` | `ai:read` | ordered |
| GET | `/v1/runs/{id}/stream` | `ai:read` | SSE of events |
| GET | `/v1/tools` | `ai:read` | allowlist metadata |
| POST | `/v1/tools/invoke` | `ai:run` | direct invoke |
| POST | `/v1/changes` | `ai:run` | propose |
| GET | `/v1/changes` | `ai:read` | |
| POST | `/v1/changes/{id}/confirm` | `ai:confirm` or `ai:run` | human confirm |

## 5. Streaming

- UI may poll `GET .../events` (Phase 1 default with bearer auth).
- `GET .../stream` is SSE; clients that cannot set `Authorization` on EventSource should poll.
- Event order is by `seq`, not wall clock.

## 6. Retention (policy default)

| Data | Default |
|------|---------|
| Events | 90 days (configurable later) |
| Artifacts inline | 90 days |
| Audit log | 365 days |

Not binding on storage engine in Phase 1 SQLite.
