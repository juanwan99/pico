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
| Pointing at frozen contracts for edu team | Dual-running or fixing edu AI for them |

If a user message says "integrate / Phase 3 / edu", interpret as: **finish Pico-side surface only** (env, validation, Fake→HTTP adapter, hooks, docs).  
If work seems to require edu source changes → **stop and say so in chat**; do not open edu.

Violation of this file = wrong execution, not a gray area.

---

## Product rules

- Product: AI foundation only. No school SaaS rebuild.
- Prefer Kimi Agent + model **APIs**; no custom agent framework.
- Tenant fail-closed; no dual-run legacy AI (Pico owns AI ledger).
- Small PRs; CANDIDATE + CI + independent review before merge when required.
- Night: long tests OK; no unattended merge to default branch unless owner authorized for that PR.
