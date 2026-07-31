**Controller poll:** [`docs/CONTROLLER-POLL.md`](docs/CONTROLLER-POLL.md)  
**Execution queue (×3):** [`docs/EXECUTION-QUEUE.md`](docs/EXECUTION-QUEUE.md)  
**Validation queue:** [`docs/VALIDATION-QUEUE.md`](./VALIDATION-QUEUE.md)  
**FAST sprint:** [`docs/SPRINT-FAST.md`](docs/SPRINT-FAST.md)  
**P0 security:** [`docs/P0-SECURITY-HARDENING.md`](docs/P0-SECURITY-HARDENING.md)  
**Test window:** [`docs/TEST-WINDOW.md`](docs/TEST-WINDOW.md)  
**24h plan:** [docs/STANDALONE-AI-24H.md](./STANDALONE-AI-24H.md)

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
| 2b | [RACI-GROK-CODEX.md](./RACI-GROK-CODEX.md) | 总管/写入/审查映射 · 并行 · 夜间6h · GitHub交接 |
| 2c | [templates/](./templates/) | 日间任务 / 审查 / CANDIDATE-DEPLOYED |
| 3 | [MVP-3DAY.md](./MVP-3DAY.md) | Product law v1.2 FIXED |
| 4 | [CORRECTED-GOALS.md](./CORRECTED-GOALS.md) | Product memory (not netdisk/SaaS) |
| 5 | [PARALLEL-SPRINT-PLAN.md](./PARALLEL-SPRINT-PLAN.md) | **Current** execution plan (BINDING-v2) |
| 6 | [ADR-SKILL-CATALOG.md](./ADR-SKILL-CATALOG.md) | Skill catalog decision |
| 7 | [WORKFLOW.md](./WORKFLOW.md) · [VERSIONING.md](./VERSIONING.md) | Windows / risk / SHA |
| 8 | [M5-INTEGRATION-RUNBOOK.md](./M5-INTEGRATION-RUNBOOK.md) · [M5-API-CHECKLIST.md](./M5-API-CHECKLIST.md) | M5 筹备（未授权不真连） |
| 8b | [PHASE2-CONTRACTS.md](./PHASE2-CONTRACTS.md) · [PHASE3-INTEGRATION.md](./PHASE3-INTEGRATION.md) · [contracts/](./contracts/) | Integration contracts |
| 9 | [MASTER-PLAN.md](./MASTER-PLAN.md) | Phase map M0–M5 (nav only) |
| 9b | [DAY-TASK-2026-07-30-SKILL-UX.md](./DAY-TASK-2026-07-30-SKILL-UX.md) | **当前日间派工**（Skill+UX 双轨） |
| 10 | Night cards: [N1](./NIGHT-CARD-N1-W-MAINPATH.md) · [N2](./NIGHT-CARD-N2-SKILL-THIN.md) · [N3-THICK](./NIGHT-CARD-N3-THICK.md) · [N4-THICK](./NIGHT-CARD-N4-THICK.md) · [policy](./NIGHT-CARD-POLICY.md) | Executable card; **evidence still on PR** |
| 11 | [DEMO.md](./DEMO.md) · [DEPLOY-TWO-HOST.md](./DEPLOY-TWO-HOST.md) · [DEPLOY-PUBLIC.md](./DEPLOY-TWO-HOST.md](./DEPLOY-TWO-HOST.md) · [DEPLOY-PUBLIC.md) | Demo & public deploy notes |
| 12 | [PIXEL-DIFF.md](./PIXEL-DIFF.md) · matrices when present | UX evidence (not task status) |

## Repeatable smokes

- N3 Skill snapshot: `python scripts/n3_skill_snapshot_smoke.py` for CI policy/frontmatter; add `--api http://127.0.0.1:18765` against a running Pico API for live Run snapshot + S7 proof.

## Completed / historical (active tree)

| Path | Note |
|------|------|
| [SPRINT-3DAY-PUSH.md](./SPRINT-3DAY-PUSH.md) | Foundation sprint **COMPLETED** — do not re-open as current plan |
| [archive/](./archive/) | Retired handoffs, snapshots, prompts |

## Hygiene rule

New long plans: **one ACTIVE plan** at a time. Previous plan → COMPLETED header or `docs/archive/`.
