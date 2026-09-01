# Phase 2 — Integration Contracts (FROZEN v1.0)

```
STATUS: FROZEN
VERSION: 1.0
DATE: 2026-07-29
PLAN: docs/MVP-3DAY.md v1.2 §4 / §0.4 Phase 2
RULE: Phase 3 only swaps adapters + issuer; does NOT rewrite protocol
```

## Purpose

Freeze the **shape** of identity, tools, AI facts, and change handoff so:

1. Pico Phase 1 implementations already conform.
2. edu-cloud Phase 3 can implement issuer + business tools without renegotiating fields.
3. No dual AI ledger; no silent school writes from Pico.

## Documents

| Doc | Freeze content |
|-----|----------------|
| [`contracts/delegated-auth.md`](contracts/delegated-auth.md) | JWT claims, alg, TTL, reject codes, edu issuer duties |
| [`contracts/tools.md`](contracts/tools.md) | Allowlist tool protocol, FakeEdu→Edu swap, cross-school |
| [`contracts/ai-facts.md`](contracts/ai-facts.md) | Task/Run/Event/Artifact ownership + event types |
| [`contracts/change-handoff.md`](contracts/change-handoff.md) | Propose → confirm → edu Review/Commit boundary |
| [`contracts/usage-export.md`](contracts/usage-export.md) | Pico meter → edu bill (no money in Pico) |
| [`contracts/page-collect.md`](contracts/page-collect.md) | Land join keys (`source_item_ids`) · answers land in edu |
| [`../packages/contracts/schemas/`](../packages/contracts/schemas/) | JSON Schema (machine-readable) |

## Non-goals (Phase 2)

- No edu-cloud code changes in this phase
- No live network calls to edu
- No retiring edu AI yet (Phase 3)

## Acceptance for Phase 2

- [x] Four contract docs marked **FROZEN v1.0**
- [x] JSON Schemas for claims, tool envelope, event, change proposal
- [x] Explicit Phase 3 adapter swap notes
- [x] Cross-links from README / PHASE1-STATUS

## Change control

Breaking changes require:

1. Bump contract `VERSION` (semver)
2. Note in this index under **Delta log**
3. Dual-read window if edu already implementing

### Delta log

| Ver | Date | Note |
|-----|------|------|
| 1.0 | 2026-07-29 | Initial freeze from Phase 1 realized shapes |
| 1.0+usage | 2026-08-29 | Additive: usage-export (Pico meters, edu bills). Does not rewrite 1.0 fields |
| 1.0+page-collect | 2026-09-01 | Additive: land envelope `source_item_ids` / `pico_artifact_id`. Does not rewrite 1.0 fields |
