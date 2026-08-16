# Phase 3 — Integrate Pico ↔ edu-cloud

```
PICO_SCOPE: agents work **only** in this repo; edu-cloud is out of band
STATUS: M3 PICO STUB READY; LIVE EDU INTEGRATION DEFERRED
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

M3 stub status: JWT issuer modes, `fake|live` validation, and the frozen Change
handoff envelope are implemented and tested in Pico; no live edu request is part
of this milestone.

## edu-cloud endpoints (pico_bridge)

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| POST | `/api/v1/pico/token` | logged-in membership | mint Pico JWT |
| GET | `/api/v1/pico/classes` | service token | list classes for school |
| POST | `/internal/pico/change-proposals` | service token | accept confirmed proposal |
| GET | `/api/v1/pico/ai-status` | any auth | whether edu AI is tombstoned |

## Cutover checklist (no dual-run)

- [ ] Configure shared secrets on both sides
- [ ] `PICO_EDU_MODE=live` + demo list_classes from real Class table
- [ ] Mint token from edu UI → open Pico web with token
- [ ] Confirm change → appears in edu `pico_change_inbox` (or log)
- [ ] Set edu `PICO_AI_PRIMARY=true` → `/api/v1/edu-ai/*` returns **410** with Pico URL
- [ ] Disable Pico test issuer in production (`PICO_ACCEPT_TEST_ISSUER=false`)
- [ ] Do **not** leave edu AI workbench creating parallel Run ledgers

## edu-core ticket (T-SHELL-AI-EDU-ID)

edu signs; Pico verifies. Same claim shape as `issue_test_token`.

| Pico claim | Required | edu-core field |
|------------|----------|----------------|
| `iss` | yes | `PICO_EDU_ISS` (same value on both hosts) |
| `aud` | yes | `PICO_JWT_AUD` (default `pico-api`) |
| `iat` / `exp` | yes | short TTL (Pico default 900s) |
| `school_id` | yes | `public.school_membership.school_id` (= `public.school.id`) |
| `membership_id` | yes | `public.school_membership.id` |
| `scopes` | yes | `["ai:run","ai:read","ai:confirm"]` (chat needs `ai:run`) |
| `sub` | no | `{school_id}:{membership_id}` |

HS256 shared secret: `PICO_EDU_JWT_SECRET` on both. Empty on Pico = `edu_issuer_configured=false`, JWT path closed.

Usage ledger keys are those two claims. `PICO_OPENAI_PROXY_KEY` still maps to `nextchat-user` — that is **not** the edu login person.

edu BFF must call Pico **API** (`/v1/chat/completions`), not LibreChat `/api/pico/*` (that door wants a LibreChat session JWT).

## Security

- Service tokens never in frontend
- User Pico JWT still short-TTL; school_id only from claims
- Cross-school still fail-closed in Pico gateway
- Shared proxy key is not an edu identity

## Rollback

1. `PICO_EDU_MODE=fake`
2. `PICO_AI_PRIMARY=false` on edu
3. Re-enable test issuer only in non-prod


