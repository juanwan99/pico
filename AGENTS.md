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
| **Read-only** reference to edu AGENTS for workflow patterns | Copying edu ECS/OneFlow/prod ports as if pico owned them |

If work needs edu source changes → **stop and say so**; do not open edu.

---

## Execution workflow (binding) — **same mode as edu**

**Full:** [`docs/WORKFLOW.md`](docs/WORKFLOW.md) · **Versioning:** [`docs/VERSIONING.md`](docs/VERSIONING.md)  
**Why/what absorbed:** [`docs/WORKFLOW-COMPARE-EDU.md`](docs/WORKFLOW-COMPARE-EDU.md)

| Rule | |
|------|---|
| Isolation | One slice → one writer → one branch → one PR |
| Window states | `OPEN` / `KEEP` / `CLEAR` / `WAIT` |
| Roles | `Grok-Pico写入` / `调查` / `审查` |
| After push | **`CANDIDATE` + full 40-char SHA + evidence map** |
| Gates | CI ∥ independent review ∥ UI QA when UI |
| Verdict | Writer `VERDICT_AUTHORITY: NONE` — **no self-PASS** |
| Merge | **Watched** only; no unattended main merge |
| Facts | GitHub Issue/PR/SHA/CI only — no parallel status system |
| Review | Exact SHA; writer cannot issue independent `PASS` |
| Risk | Green CI+self; Yellow/Red **independent exact-SHA review** |
| Version | Full 40-char SHA; no parallel VERSION-MAP; see VERSIONING.md |

Do **not** invent coordinators, mailboxes, leases, or auto-dispatchers.

---

## Corrected goals snapshot

Owner-aligned goals + purged wrong memories: [`docs/CORRECTED-GOALS.md`](docs/CORRECTED-GOALS.md).

Live engineering calibration (branch tip, S1–S8, stale-doc index): [`docs/CALIBRATION-NOW.md`](docs/CALIBRATION-NOW.md).

Execution blueprint (W0–W4): [`docs/ORCHESTRATION-PLAN.md`](docs/ORCHESTRATION-PLAN.md).

## Product rules

- AI foundation only (conversation + agent + ledger + artifacts). Not netdisk, not school SaaS rebuild.
- Kimi Agent + model HTTPS APIs; no custom agent OS.
- Tenant fail-closed; **Pico owns the unique AI ledger**.
- Pricing docs may stay DRAFT; do not freeze commercial FIXED unless owner orders.
- Prefer smallest correct fix; delete dual-run croft rather than stack adapters.
