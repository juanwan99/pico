# Pico architecture

```
DOC: docs/ARCHITECTURE.md
STATUS: BINDING ARCHITECTURE BOUNDARY
DATE: 2026-08-01
DECISION: docs/ADR-HARNESS-BOUNDARY.md
```

## 1. Architecture goal

Pico is a browser-based, multi-tenant AI workspace. Its durable product value is not a particular UI,
Harness, or model. Pico owns the stable control plane and the unique AI ledger so those replaceable
components can evolve independently.

```text
Experience shell     LibreChat (React Web)
        ↓
Pico control plane   tenant + project + Task/Run/Event/Artifact + automation
        ↓
Harness contract     normalized input, events, controls, capabilities and version
        ↓
Harness adapter      anti-corruption layer for one runtime
        ↓
Harness runtime      current thin loop; future validated third-party runtime
        ↓
Model provider       Kimi first; DeepSeek and other compatible providers
```

The shell is a long-lived product choice and should be improved incrementally, not rewritten. The
Harness and model are replaceable execution dependencies. Neither may become a second Pico ledger.

## 2. Layer ownership

| Layer | Owns | Must not own | Current implementation |
|-------|------|--------------|------------------------|
| **L1 Experience shell** | Web navigation, compose, conversation rendering, task/result UI | Trusted tenant decisions or terminal Run state | `apps/librechat` (React/TypeScript/Vite + Node; Mongo) |
| **L2 Pico control plane** | Principal, projects, Task/Run/Event/Artifact, automation, audit | Vendor-specific agent internals | `services/api` (FastAPI/SQLAlchemy) |
| **L3 Harness contract/adapter** | Normalized request, events, controls, capability/version mapping | Product truth or direct DB access | Currently implicit in `openai_compat.py` and `run_service.py` |
| **L4 Harness runtime** | Model loop, context execution, tool-call coordination | Tenant widening, silent product writes, a competing ledger | Current `pico_orchestrator.run_agent_loop` thin loop |
| **L5 Capability gateway** | Allowlisted tools, skill policy, fail-closed authorization | General host access by default | `gateway.py`, `tools_builtin.py`, `skill_policy.py` |
| **L6 Model providers** | HTTPS model invocation and provider error mapping | Task status, project state or artifact ownership | `provider.py`: Kimi first, DeepSeek fallback |
| **L7 Storage** | Durable product facts | Duplicated AI truth | LibreChat Mongo for shell data; Pico SQL for AI ledger |

The earlier Vue 3 description is obsolete. The only product shell is LibreChat React. The current
runtime uses Pico's thin OpenAI-compatible tool loop; pinned Kimi Agent SDK/CLI dependencies exist,
but the full Kimi Agent Runtime is not the execution hot path.

## 3. Stable Pico domain

```text
Principal (school_id, membership_id, scopes)
    │
    ├─ Project / workspace context
    │
    └─ Task                 user intent
          └─ Run            one execution attempt
               ├─ Event[]   ordered execution evidence
               ├─ Artifact[] owned deliverables
               └─ external runtime reference (optional, never truth)
```

Pico decides and persists terminal state. A Harness event is evidence to validate, not permission to
bypass state transitions. Artifacts proposed by a Harness become product artifacts only after Pico
validates ownership and persists them.

## 4. Request path

```text
LibreChat request
  → Pico OpenAI-compatible endpoint or Task API
  → resolve server-side Principal
  → create/find Task and create Run in the unique ledger
  → build immutable skill/model/project execution snapshot
  → Harness Adapter.start(RunRequest)
  → normalize runtime events into ordered Pico Events
  → execute tools only through the Pico allowlist gateway
  → persist artifacts and validated terminal Run state
  → stream a product response to LibreChat
```

Refresh, history re-entry, retries and automation must reconstruct truth from the Pico ledger rather
than browser memory or a runtime process.

## 5. Harness boundary

The target boundary is deliberately small:

- **Input:** Pico IDs and idempotency key, authorized context/assets, immutable skill/model snapshot,
  execution caps and allowed tools.
- **Events:** started, step, tool lifecycle, approval, proposed artifact, succeeded/failed/cancelled.
- **Controls:** start, cancel, status, recover, health, capabilities and version.
- **Identity:** external thread/run IDs may be stored only as correlation metadata under a Pico Run.

Pico business code depends on this contract, never directly on a vendor SDK. A third-party Harness
should run unmodified where practical; vendor-specific behavior stays inside its Adapter.

See [ADR-HARNESS-BOUNDARY.md](./ADR-HARNESS-BOUNDARY.md) for the binding decision and admission tests.

## 6. Model boundary

Models are interchangeable providers, not the product control plane. Provider qualification covers
more than a successful text response: streaming, tool calls, structured output, context limits,
cancellation behavior, usage, rate limits and honest error mapping must be verified.

Current order:

1. Kimi HTTPS API is the primary configured provider.
2. DeepSeek is the existing fallback path.
3. Additional providers require a bounded adapter and capability tests; provider fields must not leak
   into Pico domain objects.

## 7. Tenancy and safety

- Every Run resolves a school + membership Principal server-side (or an explicit platform principal).
- The model and Harness cannot widen scope through prompts or tool arguments.
- Tools receive server-resolved identity through the Pico gateway and fail closed across tenants.
- Shell, host File, unrestricted Web and MCP remain off unless a later, explicitly reviewed capability
  creates a narrower safe contract.
- Historical lookup applies tenant and conversation predicates before bounded result windows.
- Business mutation remains proposal → human confirmation → audit; no silent write.

## 8. Storage truth

Two databases do not imply two AI ledgers:

- LibreChat Mongo stores shell concerns such as users, conversations and upstream project records.
- Pico SQL stores Task/Run/Event/Artifact and other AI execution facts.

The conversation-to-ledger bridge must be queryable by `conversation_id / task_id / run_id`. Project
instructions, asset organization, automation runs and terminal execution state must move toward
server-owned facts; browser `localStorage` is never a mature product truth source.

## 9. Evolution path

1. Keep the current thin loop as the first Harness implementation.
2. Extract the smallest contract from proven current calls; do not build a speculative universal SDK.
3. Add conformance tests for success, tools, deny, failure, timeout, cancellation, idempotency, recovery,
   artifacts and terminal-state consistency.
4. Evaluate an external Harness only when it is released, licensable, versionable and can satisfy the
   boundary without becoming a second ledger.
5. Switch implementations only after exact-version tests and real runtime validation; CI alone is not
   production acceptance.

## 10. Non-goals

- No rewrite of the LibreChat shell.
- No second Agent framework grown beside the selected Harness.
- No second Task/Run/Event/Artifact ledger.
- No vendor Harness direct access to Pico databases or tenant credentials.
- No commitment to an unreleased DeepSeek Harness or any other specific future runtime.
- No edu-cloud implementation in this repository.

See also: [CORRECTED-GOALS.md](./CORRECTED-GOALS.md),
[OVERALL-ARCHITECTURE.md](./OVERALL-ARCHITECTURE.md), and
[ADR-SKILL-CATALOG.md](./ADR-SKILL-CATALOG.md).
