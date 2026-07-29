# Phase 3 — Integrate Pico ↔ edu-cloud

```
PICO_SCOPE: agents work **only** in this repo; edu-cloud is out of band
STATUS: PICO-SIDE COMPLETE ON MAIN (edu team owns their side)
PLAN: MVP-3DAY v1.2 §10
CONTRACTS: Phase 2 FROZEN v1.0 (unchanged field names)
```

## Goals

1. **edu signs** Pico tokens (same claims as Phase 1 test issuer)
2. **FakeEdu → live** adapter for `fake_edu_list_classes` (name stable)
3. **Change handoff** confirm → edu Review queue; callback updates Pico audit
4. **Workbench** opens Pico with minted token
5. **Atomic retire path** for edu AI foundation when `PICO_AI_PRIMARY=true` (no dual ledger)

## Pico configuration

```bash
# .env
PICO_EDU_MODE=live                    # or fake
PICO_EDU_BASE_URL=http://127.0.0.1:8001
PICO_EDU_SERVICE_TOKEN=<shared>
PICO_EDU_HANDOFF_ENABLED=true

PICO_EDU_ISS=https://edu.local/iss/pico
PICO_EDU_JWT_SECRET=<shared-with-edu-issuer>
PICO_ACCEPT_TEST_ISSUER=false         # production after edu issuer live

PICO_HOOK_SERVICE_TOKEN=<shared-for-callbacks>
```

## edu-cloud endpoints (pico_bridge)

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| POST | `/api/v1/pico/token` | logged-in membership | mint Pico JWT |
| GET | `/api/v1/pico/classes` | service token | list classes for school |
| POST | `/api/v1/pico/change-proposals` | service token | accept confirmed proposal |
| GET | `/api/v1/pico/ai-status` | any auth | whether edu AI is tombstoned |

## Cutover checklist (no dual-run)

- [ ] Configure shared secrets on both sides
- [ ] `PICO_EDU_MODE=live` + demo list_classes from real Class table
- [ ] Mint token from edu UI → open Pico web with token
- [ ] Confirm change → appears in edu `pico_change_inbox` (or log)
- [ ] Set edu `PICO_AI_PRIMARY=true` → `/api/v1/edu-ai/*` returns **410** with Pico URL
- [ ] Disable Pico test issuer in production (`PICO_ACCEPT_TEST_ISSUER=false`)
- [ ] Do **not** leave edu AI workbench creating parallel Run ledgers

## Security

- Service tokens never in frontend
- User Pico JWT still short-TTL; school_id only from claims
- Cross-school still fail-closed in Pico gateway

## Rollback

1. `PICO_EDU_MODE=fake`
2. `PICO_AI_PRIMARY=false` on edu
3. Re-enable test issuer only in non-prod


