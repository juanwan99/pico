# Pico documentation index

```
STATUS: BINDING navigation
TRUTH: code + tests + GitHub (PR/SHA/CI/DEPLOY comments) outrank all prose
ONEFLOW: docs/ONEFLOW.md
```

## Do not

- Create new **handoff / wave / status diary** Markdown for cross-window state.
- Treat anything under `docs/archive/` as current.
- Claim progress only in a doc checkbox without a PR.

## Active documents (read in order when unsure)

| Priority | Path | Role |
|----------|------|------|
| 0 | GitHub PR/Issue/Actions | **Task state & evidence** |
| 1 | [AGENTS.md](../AGENTS.md) | Machine + human HARD scope |
| 2 | [ONEFLOW.md](./ONEFLOW.md) | Delivery OS + closed loops |
| 3 | [MVP-3DAY.md](./MVP-3DAY.md) | Product law v1.2 FIXED |
| 4 | [CORRECTED-GOALS.md](./CORRECTED-GOALS.md) | Product memory (not netdisk/SaaS) |
| 5 | [PARALLEL-SPRINT-PLAN.md](./PARALLEL-SPRINT-PLAN.md) | **Current** execution plan (BINDING-v2) |
| 6 | [ADR-SKILL-CATALOG.md](./ADR-SKILL-CATALOG.md) | Skill catalog decision |
| 7 | [WORKFLOW.md](./WORKFLOW.md) · [VERSIONING.md](./VERSIONING.md) | Windows / risk / SHA |
| 8 | [PHASE2-CONTRACTS.md](./PHASE2-CONTRACTS.md) · [PHASE3-INTEGRATION.md](./PHASE3-INTEGRATION.md) · [contracts/](./contracts/) | Integration contracts |
| 9 | [MASTER-PLAN.md](./MASTER-PLAN.md) | Phase map M0–M5 (nav only) |
| 10 | Night cards e.g. [NIGHT-CARD-N1-W-MAINPATH.md](./NIGHT-CARD-N1-W-MAINPATH.md) | Executable card; **evidence still on PR** |
| 11 | [DEMO.md](./DEMO.md) · [DEPLOY-PUBLIC.md](./DEPLOY-PUBLIC.md) | Demo & public deploy notes |
| 12 | [PIXEL-DIFF.md](./PIXEL-DIFF.md) · matrices when present | UX evidence (not task status) |

## Completed / historical (active tree)

| Path | Note |
|------|------|
| [SPRINT-3DAY-PUSH.md](./SPRINT-3DAY-PUSH.md) | Foundation sprint **COMPLETED** — do not re-open as current plan |
| [archive/](./archive/) | Retired handoffs, snapshots, prompts |

## Hygiene rule

New long plans: **one ACTIVE plan** at a time. Previous plan → COMPLETED header or `docs/archive/`.
