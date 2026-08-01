- **Context policy:** [`docs/CONTEXT-POLICY.md`](./CONTEXT-POLICY.md)（默认不清理上下文）
- **Controller bot (7x24):** [`docs/CONTROLLER-BOT.md`](./CONTROLLER-BOT.md) — 机制文档；**现行派工仍以总管任务卡为准**
- **Controller poll:** [`docs/CONTROLLER-POLL.md`](./CONTROLLER-POLL.md)
- **Execution queue:** [`docs/EXECUTION-QUEUE.md`](./EXECUTION-QUEUE.md) — **SUPERSEDED** 自动派工；历史队列
- **Validation queue:** [`docs/VALIDATION-QUEUE.md`](./VALIDATION-QUEUE.md)
- **FAST sprint:** [`docs/SPRINT-FAST.md`](./SPRINT-FAST.md)
- **P0 security:** [`docs/P0-SECURITY-HARDENING.md`](./P0-SECURITY-HARDENING.md)
- **Test window:** [`docs/TEST-WINDOW.md`](./TEST-WINDOW.md)
- **Completed 24h baseline:** [docs/STANDALONE-AI-24H.md](./STANDALONE-AI-24H.md)

# Pico documentation index

```
STATUS: BINDING navigation
TRUTH: code + tests + GitHub (PR/SHA/CI/DEPLOY comments) outrank all prose
ONEFLOW: docs/ONEFLOW.md
GOALS: docs/TRUTH-FREEZE.md · docs/WHAT-IS-PICO.md （目标）；STATE-NOW（快照）
```

## Do not

- Create new **handoff / wave / status diary** Markdown for cross-window state.
- Treat anything under `docs/archive/` as current.
- Claim progress only in a doc checkbox without a PR.
- Treat **#121 harness / multi-runtime** drafts as accepted architecture.
- Claim **Kimi Agent 已接入** because KA-0/1/2 merged or pins are green.

## Active documents (read in order when unsure)

| Priority | Path | Role |
|----------|------|------|
| **0** | **[TRUTH-FREEZE.md](./TRUTH-FREEZE.md)** | **真源冻结 v1.0（防丢失 · 权威决策集）** |
| **0a** | **[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)** | **Pico 是什么 / 编排目标 vs 现状** |
| **0b** | **[STATE-NOW.md](./STATE-NOW.md)** | **当前 SHA、派发、门禁、黑名单** |
| **0c** | **[KIMI-AGENT-GAP.md](./KIMI-AGENT-GAP.md)** | **真接差距 + KA-0…4 状态（默认未归位）** |
| **0d** | **[POLLUTION-SWEEP.md](./POLLUTION-SWEEP.md)** | **污染清理执行记录** |
| **0e** | **[VELOCITY-CLEAN.md](./VELOCITY-CLEAN.md)** | **速度阻碍清理（部署主链）** |
| 0 | GitHub PR/Issue/Actions | **Task state & evidence** |
| 1 | [AGENTS.md](../AGENTS.md) | Machine + human HARD scope |
| 2 | [ONEFLOW.md](./ONEFLOW.md) | Delivery OS + closed loops |
| 2b | [RACI-GROK-CODEX.md](./RACI-GROK-CODEX.md) | 总管/写入/审查映射 |
| 2c | [templates/](./templates/) | 日间任务 / 审查 / CANDIDATE-DEPLOYED |
| 3 | [MVP-3DAY.md](./MVP-3DAY.md) | Product law v1.2 FIXED |
| 4 | [CORRECTED-GOALS.md](./CORRECTED-GOALS.md) | Product memory (not netdisk/SaaS) |
| 5 | [PARALLEL-SPRINT-PLAN.md](./PARALLEL-SPRINT-PLAN.md) | 历史并行冲刺计划（以 STATE-NOW 为准是否现行） |
| 6 | [ADR-SKILL-CATALOG.md](./ADR-SKILL-CATALOG.md) | Skill catalog decision |
| 7 | [WORKFLOW.md](./WORKFLOW.md) · [VERSIONING.md](./VERSIONING.md) | Windows / risk / SHA |
| 8 | [M5-INTEGRATION-RUNBOOK.md](./M5-INTEGRATION-RUNBOOK.md) · [M5-API-CHECKLIST.md](./M5-API-CHECKLIST.md) | M5 筹备（未授权不真连） |
| 8b | [PHASE2-CONTRACTS.md](./PHASE2-CONTRACTS.md) · [PHASE3-INTEGRATION.md](./PHASE3-INTEGRATION.md) · [contracts/](./contracts/) | Integration contracts |
| 9 | [MASTER-PLAN.md](./MASTER-PLAN.md) | Phase map M0–M5 (nav only) |
| 10 | [NIGHT-CARD-POLICY.md](./NIGHT-CARD-POLICY.md) | Night execution policy |
| 11 | [DEMO.md](./DEMO.md) · [DEPLOY-TWO-HOST.md](./DEPLOY-TWO-HOST.md) · [DEPLOY-PUBLIC.md](./DEPLOY-PUBLIC.md) | Demo & public deploy notes |
| 12 | [PIXEL-DIFF.md](./PIXEL-DIFF.md) · matrices when present | UX evidence (not task status) |

## Repeatable smokes

- N3 Skill snapshot: `python scripts/n3_skill_snapshot_smoke.py` for CI policy/frontmatter; add `--api http://127.0.0.1:18765` against a running Pico API for live Run snapshot + S7 proof.

## Completed / historical (active tree)

| Path | Note |
|------|------|
| [SPRINT-3DAY-PUSH.md](./SPRINT-3DAY-PUSH.md) | Foundation sprint **COMPLETED** — do not re-open as current plan |
| [DAY-TASK-2026-07-30-SKILL-UX.md](./DAY-TASK-2026-07-30-SKILL-UX.md) | Skill expansion and UX debt completed by #55/#56 |
| [EXECUTION-QUEUE.md](./EXECUTION-QUEUE.md) | **SUPERSEDED** auto E1/E2/E3 dispatch |
| [archive/completed-tasks-2026-07/](./archive/completed-tasks-2026-07/) | Completed day/night/test cards; never use for dispatch |
| [archive/](./archive/) | Retired handoffs, snapshots, prompts |

## Hygiene rule

New long plans: **one ACTIVE plan** at a time. Previous plan → COMPLETED header or `docs/archive/`.
