# Contract: AI Facts Ledger (skeleton)

```
STATUS: SKELETON
VERSION: 0.1
OWNER: Pico only (unique AI ledger — no dual-run with edu AI)
```

## Entities

### Task

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | PK |
| `school_id` | string | from token |
| `membership_id` | string | from token |
| `title` | string | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

### Run

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | PK |
| `task_id` | uuid | FK |
| `status` | enum | `queued\|running\|succeeded\|failed\|cancelled` |
| `model` | string | provider model id |
| `started_at` / `ended_at` | datetime | |
| `token_usage` | object | optional |
| `error` | string? | |

### Event (ordered)

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | PK |
| `run_id` | uuid | FK |
| `seq` | int | monotonic per run |
| `type` | string | e.g. `message.delta`, `tool.call`, `tool.result`, `run.status`, `auth.deny` |
| `payload` | json | |
| `created_at` | datetime | |

### Artifact (metadata)

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | |
| `run_id` / `task_id` | uuid | |
| `kind` | string | `doc\|table\|report\|…` |
| `title` | string | |
| `uri` / `inline` | string? | Phase 1 may keep small inline |

## Invariants

- Pico DB is the **only** AI Run/Event truth for Phase 1+.
- Cancel / fail / success must close the Run with terminal status.
- Cross-school denies are recorded as Events (`auth.deny` / `tenant.cross_school`).


## Phase 1 realized API (D2)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/v1/tasks` | create Task + Run; starts agent loop |
| GET | `/v1/tasks` | list by school |
| GET | `/v1/tasks/{id}` | + artifacts |
| GET | `/v1/runs/{id}` | status |
| POST | `/v1/runs/{id}/cancel` | cancel_requested |
| GET | `/v1/runs/{id}/events` | ordered Event |
| GET | `/v1/runs/{id}/stream` | SSE |
| POST | `/v1/demo/cross-school-deny` | auth.deny Event demo |
| POST | `/v1/changes` | propose |
| POST | `/v1/changes/{id}/confirm` | human confirm + audit |
