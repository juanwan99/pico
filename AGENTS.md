# Pico agent rules (binding)

## HARD SCOPE — READ FIRST

```
REPO_OF_RECORD: juanwan99/pico ONLY
FORBIDDEN: any clone/edit/PR/CI/merge on juanwan99/edu-cloud (or any other repo)
OWNER_ORDER: 你只管 pico — permanent; not optional; not overridden by "Phase 3" wording
```

| Allowed | Forbidden |
|---------|-----------|
| Read/write **this** repo (`pico`) | `gh repo clone` / edit / push / PR / watch CI on **edu-cloud** |
| Docs, API, UI, orchestrator, tests **in pico** | Implementing edu issuer, edu modules, edu frontend |
| Phase 2 contracts & Phase 3 **adapters/hooks living in pico** | "Coordinate" by coding the other system |
| **Read-only** reference to edu docs for patterns | Dual-running or fixing edu AI for them |

If a user message says "integrate / Phase 3 / edu", interpret as: **finish Pico-side surface only**.  
If work requires edu source changes → **stop and say so in chat**; do not open edu PRs.

Violation of this file = wrong execution, not a gray area.

---

## Execution workflow (binding)

**Full procedure:** [`docs/WORKFLOW.md`](docs/WORKFLOW.md)

Summary:

1. **One slice → one writer → one branch → one PR.**
2. Writer `VERDICT_AUTHORITY: NONE` — no self-PASS of S1–S8 or "product done".
3. After coherent push: comment **`CANDIDATE`** with **full 40-char SHA** + evidence map.
4. **CI green + independent exact-SHA review** (`PASS`/`REVISE`/`BLOCKED`) before merge.
5. **Watched merge** to `main` only — no unattended merge (MVP S8).
6. Durable facts live on **GitHub Issue/PR/SHA/CI** only.
7. Roles: 写入 / 调查 / 审查 (pattern from edu; **no A/B/C letter requirement** on pico unless owner names them).

Green changes: CI + self-check.  
Yellow/red (auth, tenancy, SSE, agent safety, secrets): **independent review required**.

---

## Product rules

- Product: AI foundation only. No school SaaS rebuild.
- Prefer Kimi Agent + model **APIs**; no custom agent framework.
- Tenant fail-closed; Pico owns the **unique AI ledger**.
- Pricing docs may be DRAFT; do **not** freeze commercial FIXED unless owner orders.
- Small PRs; night long tests OK; no unattended default-branch merge unless owner authorized that PR.
