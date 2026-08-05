# ADR · Durable Run（P-LONG-DURABLE · 包 B）

```
DOC: docs/ADR-DURABLE-RUN.md
STATUS: BINDING for #304
STAGE: P-LONG-DURABLE
BASE: 2424f66734ef1bdc6ab2e17c3cc6b00228b8108b
```

## Context

Package A made multi-step delivery finish within ~15 minutes (900s cap) without
the 120s suicide timeout. Runs were still **tied to the browser SSE lifetime**:
closing the tab cancelled the in-process agent (`stream disconnected`).

Package B goal: approach mainstream “leave and come back” long-task feel —
**not** “raise `MAX_SECONDS` to 8h and call it durable.”

## Decision

### 1. Lifecycle (ledger is source of truth)

```text
queued → preparing → running → succeeded | failed | cancelled
```

- **Server ledger (SQLite Task/Run/Event/Artifact)** is authoritative.
- Browser connection is a **subscriber**, not the owner of the job.
- Explicit user **Stop** sets `cancel_requested` and remains sticky.

### 2. Page close / SSE disconnect (DEFAULT)

| Event | Default behavior |
|-------|------------------|
| Client closes tab / aborts SSE | **Job continues** on the API process |
| Explicit cancel API | Job cancels (sticky) |
| API process restart / deploy | In-flight may be lost; reconcile marks orphan as failed; user **may 续跑/retry** |

Config: `PICO_RUN_DETACH_ON_DISCONNECT=1` (default true).  
When false (legacy/debug): disconnect cancels (pre-B behavior).

### 3. Caps (tiered; durable is a tier, not “only longer timeout”)

| Tier | Use | Default wall |
|------|-----|--------------|
| short | direct model chat | 120s |
| delivery | pico-agent courseware / multi-step | 900s (package A) |
| durable | long job + agent when detach on | **3600s** (`PICO_RUN_DURABLE_MAX_SECONDS`) |

Raising only `MAX_SECONDS` without detach/checkpoint is **out of scope / reject**.

### 4. Events & reconnect

- All progress is appended as `events` (seq ordered).
- Clients poll `GET /v1/runs/{id}` + `/events` or resubscribe `GET /v1/runs/{id}/stream`.
- Detach emits `run.client_detached` (job still `running`).
- Heartbeats: `run.heartbeat` (package A) continue under durable.

### 5. Checkpoint granularity

| Kind | What is stored |
|------|----------------|
| Agent tools | Each `tool.result` also emits `run.checkpoint` with tool name + short summary |
| Durable job | Stage index + wall elapsed + optional Artifact blob per stage |
| Resume | Terminal failed/cancelled → `POST /v1/runs/{id}/retry` (package A) **or** durable-job continue from last stage |

### 6. Deploy / drain

- **Page close**: safe (detach).
- **Deploy/restart**: single-node in-process tasks die; reconcile fails open orphans; **续跑** is the recovery path (honest, documented).
- No multi-region HA / 8h SLA in this package.

## Consequences

- Teachers can close the tab during a long pico-agent or durable job and reopen to see progress/result.
- ≥30 minute wall-clock gold path is implemented as a **durable job** (checkpointed stages) plus detach proof on agent path; not a fake clock skip.
- Package A HTML courseware regression remains green under delivery caps.

## Out of scope (later)

- True multi-worker durable queue, 8h SLA, perfect HA drain.
- Changing default model / restoring agent loop.
