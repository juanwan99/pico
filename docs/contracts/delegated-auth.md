# Contract: Delegated Auth (skeleton)

```
STATUS: SKELETON (Phase 1 implements test issuer; Phase 3 edu signs)
VERSION: 0.1
OWNER: Pico (validation) · edu-cloud (Phase 3 issuance)
```

## Claims (required)

| Claim | Type | Notes |
|-------|------|-------|
| `iss` | string | Phase 1: `pico-test-issuer`; Phase 3: edu issuer URL |
| `aud` | string | `pico-api` |
| `exp` | int (unix) | short TTL (default 900s) |
| `iat` | int (unix) | issued at |
| `school_id` | string | tenant |
| `membership_id` | string | actor membership |
| `scopes` | string[] | e.g. `["ai:run", "ai:read"]` |
| `sub` | string | optional stable subject |

## Rules

- Pico **always** validates signature + `iss`/`aud`/`exp` server-side.
- Request body / prompt **must not** expand privileges beyond claims.
- Missing/invalid token → fail-closed (401/403).
- Cross-school tool calls denied by gateway using `token.school_id`.

## Phase 1 test issuer

- Endpoint: `POST /v1/dev/token` (dev only; disabled in production builds).
- Signs with `PICO_JWT_SECRET` (HS256 for test; Phase 3 may move to RS256).

## Reject codes (draft)

| Code | HTTP | Meaning |
|------|------|---------|
| `auth.missing` | 401 | no bearer |
| `auth.invalid` | 401 | bad signature / malformed |
| `auth.expired` | 401 | `exp` passed |
| `auth.aud_mismatch` | 401 | wrong audience |
| `auth.forbidden` | 403 | scope insufficient |
| `tenant.cross_school` | 403 | tool school ≠ token school |

