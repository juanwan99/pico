# Pico agent rules (binding)

## HARD SCOPE — READ FIRST

```
REPO_OF_RECORD: juanwan99/pico ONLY
FORBIDDEN: any clone/edit/PR/CI/merge on juanwan99/edu-cloud (or any other repo)
OWNER_ORDER: 你只管 pico — permanent; not optional; not overridden by "Phase 3" wording
```

| Allowed | Forbidden |
|---------|-----------|
| Read/write **this** repo (`pico`) | Write/PR/CI/merge on **edu-cloud** |
| Docs, API, UI, orchestrator, tests **in pico** | Implementing edu issuer/modules/frontend |
| Phase 2/3 **Pico-side** adapters/hooks/docs | Dual AI ledger / dual-run with edu AI |
| **Read-only** reference to edu AGENTS/OneFlow for workflow patterns | Copying edu ECS/1908x/mcu.asia as if pico owned them |
| Pico **OneFlow 适配版** (`docs/ONEFLOW.md`) | Pretending full GHCR→UAT auto-prod exists before stage B |

If work needs edu source changes → **stop and say so**; do not open edu.

---

## Execution workflow (binding) — **OneFlow adapted from edu**

**OneFlow (end-to-end OS + closed loops):** [`docs/ONEFLOW.md`](docs/ONEFLOW.md)  
**3-day push (when active):** [`docs/SPRINT-3DAY-PUSH.md`](docs/SPRINT-3DAY-PUSH.md)  
**Parallel sprint (BINDING-v2 · N1+):** [`docs/PARALLEL-SPRINT-PLAN.md`](docs/PARALLEL-SPRINT-PLAN.md) · Skill ADR: [`docs/ADR-SKILL-CATALOG.md`](docs/ADR-SKILL-CATALOG.md)  
**Windows / risk / review detail:** [`docs/WORKFLOW.md`](docs/WORKFLOW.md) · **Versioning:** [`docs/VERSIONING.md`](docs/VERSIONING.md)  
**Why/what absorbed:** [`docs/WORKFLOW-COMPARE-EDU.md`](docs/WORKFLOW-COMPARE-EDU.md)  
**Helper (not authority):** `bash scripts/oneflow-status.sh`

### OneFlow closed loop (must not skip)

```text
goal → one PR → CANDIDATE+SHA → CI green → review(if Y/R) → MERGED main
  → stage-A deploy → health.git_sha match → DEPLOYED comment → CLEAR
```

- **CI red ⇒ no merge.** Writer `VERDICT_AUTHORITY: NONE` (no self-PASS).
- **Controller** merges after gates; writer does not self-merge yellow/red.
- GitHub Issue/PR/SHA/CI/Deploy comments = only durable facts.

| Rule | |
|------|---|
| Isolation | One slice → one writer → one branch → one PR |
| Window states | `OPEN` / `KEEP` / `CLEAR` / `WAIT` |
| Roles | `Grok-Pico写入` / `调查` / `审查` |
| After push | **`CANDIDATE` + full 40-char SHA + evidence map** |
| Gates | CI ∥ independent review ∥ UI QA when UI |
| Verdict | Writer `VERDICT_AUTHORITY: NONE` — **no self-PASS** |
| Merge | **Controller** after CI (+ review if Y/R); no unattended / no merge on red CI |
| Facts | GitHub Issue/PR/SHA/CI only — no parallel status system |
| Review | Exact SHA; writer cannot issue independent `PASS` |
| Risk | Green CI+self; Yellow/Red **independent exact-SHA review** |
| Version | Full 40-char SHA; no parallel VERSION-MAP; see VERSIONING.md |

Do **not** invent coordinators, mailboxes, leases, or auto-dispatchers.

---

## Corrected goals snapshot

Owner-aligned goals: [`docs/CORRECTED-GOALS.md`](docs/CORRECTED-GOALS.md).

**Truth freeze:** [`docs/TRUTH-FREEZE.md`](docs/TRUTH-FREEZE.md)  
**What is Pico:** [`docs/WHAT-IS-PICO.md`](docs/WHAT-IS-PICO.md)  
**Current snapshot:** [`docs/STATE-NOW.md`](docs/STATE-NOW.md) — tip、门禁。  
**Memory reset:** [`docs/MEMORY-RESET.md`](docs/MEMORY-RESET.md) — 错误记忆黑名单 · **单窗 SOLO**。  
**Stage package:** [`docs/STAGE-PACKAGE-MODE.md`](docs/STAGE-PACKAGE-MODE.md) — 单窗阶段包（废默认多窗碎卡）。  
**Task card format:** [`docs/TASK-CARD-STANDARD.md`](docs/TASK-CARD-STANDARD.md) — CLAIM/BASE/PRODUCT · 锁定句 · Issue 正文为准。  
**Doc index (truth order):** [`docs/README.md`](docs/README.md) — prefer GitHub over prose.

**Context policy:** [`docs/CONTEXT-POLICY.md`](docs/CONTEXT-POLICY.md)（默认不清理上下文）  
**Controller bot (7x24):** [`docs/CONTROLLER-BOT.md`](docs/CONTROLLER-BOT.md) — 机制说明；**派工以总管任务卡 + STATE-NOW 为准**  
**Controller poll:** [`docs/CONTROLLER-POLL.md`](docs/CONTROLLER-POLL.md)  
**Execution queue:** [`docs/EXECUTION-QUEUE.md`](docs/EXECUTION-QUEUE.md) — **SUPERSEDED** 自动 E1/E2/E3；勿当现行派工  
**Validation queue:** [`docs/VALIDATION-QUEUE.md`](docs/VALIDATION-QUEUE.md)  
**FAST sprint:** [`docs/SPRINT-FAST.md`](docs/SPRINT-FAST.md)  
**P0 security:** [`docs/P0-SECURITY-HARDENING.md`](docs/P0-SECURITY-HARDENING.md)  
**Test window:** [`docs/TEST-WINDOW.md`](docs/TEST-WINDOW.md)  
**24h Standalone AI:** [`docs/STANDALONE-AI-24H.md`](docs/STANDALONE-AI-24H.md) (historical baseline)  
**Current dispatch:** **单窗 SOLO** · 日卡 [`docs/DAY-TASK-P0-PI-CUTOVER.md`](docs/DAY-TASK-P0-PI-CUTOVER.md) · [#310](https://github.com/juanwan99/pico/issues/310)  
**Kimi legacy:** [`docs/KIMI-AGENT-GAP.md`](docs/KIMI-AGENT-GAP.md) 仅考古/回滚；**产品默认 = Pi**  
**KA-4:** soft historical [`docs/KA4-SOFT.md`](docs/KA4-SOFT.md) **superseded** · ops: [`docs/OPS-RUNBOOK-STABILIZE.md`](docs/OPS-RUNBOOK-STABILIZE.md)  
**Skill ADR:** [`docs/ADR-SKILL-CATALOG.md`](docs/ADR-SKILL-CATALOG.md).  
**Completed foundation sprint:** [`docs/SPRINT-3DAY-PUSH.md`](docs/SPRINT-3DAY-PUSH.md) (COMPLETED).  
**Completed day task (do not re-open):** [`docs/DAY-TASK-2026-07-30-SKILL-UX.md`](docs/DAY-TASK-2026-07-30-SKILL-UX.md)

Do **not** use `docs/archive/**`, new HANDOFF markdown, or open PR **#121 harness multi-runtime** as task truth.

## Product rules
- **Org:** default **single-window SOLO** — [docs/STAGE-PACKAGE-MODE.md](docs/STAGE-PACKAGE-MODE.md). Old windows 1/2/4 are **duty aliases**, not parallel staffing. See [docs/MEMORY-RESET.md](docs/MEMORY-RESET.md).
- **Ship steps:** [docs/FAST-PATH.md](docs/FAST-PATH.md) — change → merge → prod-update → chat/stop → 3-line report. **One window** runs the chain; no multi-issue process OS.
- **Product goal:** Web WorkBuddy degree (six bars) — [docs/HANDOFF-WB-PI.md](docs/HANDOFF-WB-PI.md).
- **Default runtime:** **Pi** + **DeepSeek**. Kimi Agent = **legacy rollback only**. Self-built `run_agent_loop` stays **deleted** (never the goal).
- **Prod flags:** `PICO_PI_AGENT_RUNTIME=1` default; legacy Kimi only if emergency. Do **not** claim `CLAIM-WB-DEGREE-WEB` until six bars + GitHub evidence.
- **KA-4 HARD:** `run_agent_loop` / `runner.py` **removed**. Rollback multi-step = redeploy prior tip or legacy flag — not revive loop.
- **Speed:** deploy + smoke beat new process docs; see `docs/VELOCITY-CLEAN.md`.
- Tenant fail-closed; **Pico owns the unique AI ledger**.
- Prefer smallest correct fix; no dual-run; no dual-kernel product truth.

## Speed vs safety

**Default org:** stage package + **SOLO** ([STAGE-PACKAGE-MODE](docs/STAGE-PACKAGE-MODE.md)).  
**Default tech rhythm:** [docs/FAST-PATH.md](docs/FAST-PATH.md) steps inside one window.

**KEEP:** secrets out of git; allowlist tools; exact-SHA deploy; CI green; no fake global / WB CLAIM; no dual-run; **Pi + DeepSeek default**.

**CUT:** multi-window daily dispatch, multi-card ceremonies, auto E1 queue, per-gap micro-issues, Kimi-as-only-goal memory, Dify-as-product, scene-exam-as-WB.

PRs stay (one writer / one branch / CI). Do **not** split one theme into many waiting rounds or many windows.

