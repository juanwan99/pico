# Contract: Delegated Auth

```
STATUS: FROZEN
VERSION: 1.0
OWNER_VALIDATE: Pico
OWNER_ISSUE_PHASE1: Pico test issuer
OWNER_ISSUE_PHASE3: edu-cloud
SCHEMA: packages/contracts/schemas/delegated-claims.schema.json
```

## 1. Token transport

| Item | Value |
|------|-------|
| Header | `Authorization: Bearer <jwt>` |
| Type | JWT (JWS) |
| Phase 1 alg | `HS256` with shared `PICO_JWT_SECRET` (dev/test only) |
| Phase 3 alg | **`RS256` preferred** (edu private key; Pico holds edu public JWKS) |
| `aud` | always `pico-api` |
| Default TTL | **900 seconds** (max recommended 3600) |

## 2. Required claims

| Claim | Type | Required | Description |
|-------|------|----------|-------------|
| `iss` | string | yes | Phase 1: `pico-test-issuer`. Phase 3: edu stable issuer URI, e.g. `https://edu.example/iss/pico` |
| `aud` | string | yes | Must equal `pico-api` |
| `exp` | number | yes | Unix seconds |
| `iat` | number | yes | Unix seconds |
| `school_id` | string | yes | Tenant id (opaque string, not numeric-only requirement) |
| `membership_id` | string | yes | Actor membership within school |
| `scopes` | string[] | yes | Subset of registered scopes |
| `sub` | string | recommended | Stable subject; default `${school_id}:${membership_id}` |
| `jti` | string | optional | Unique token id for revoke/log |

### Registered scopes

| Scope | Grants |
|-------|--------|
| `ai:read` | List tasks/runs/events/artifacts/changes |
| `ai:run` | Create tasks, start/cancel runs, invoke tools |
| `ai:confirm` | Confirm change proposals |
| `ai:admin` | Reserved (platform); not used in school tokens Phase 1 |

Missing `ai:run` → cannot create tasks (403 `auth.forbidden`).

## 3. Validation rules (Pico, fail-closed)

1. Verify signature with configured key/JWKS for `iss`.
2. Reject if `aud` ≠ `pico-api`.
3. Reject if `exp` ≤ now (clock skew allowance: **60s**).
4. Reject if `school_id` or `membership_id` empty.
5. **Never** trust `school_id` / scopes from request body or prompt.
6. Tool gateway re-checks `token.school_id` on every school-scoped tool.

## 4. Reject codes

| Code | HTTP | When |
|------|------|------|
| `auth.missing` | 401 | No `Authorization` bearer |
| `auth.invalid` | 401 | Bad signature / malformed JWT / missing claims |
| `auth.expired` | 401 | `exp` passed |
| `auth.aud_mismatch` | 401 | Wrong audience |
| `auth.iss_unknown` | 401 | Issuer not in Pico trust set |
| `auth.forbidden` | 403 | Scope insufficient for route |
| `tenant.cross_school` | 403 | Tool/input school ≠ token school |

Error body shape:

```json
{ "detail": { "code": "auth.expired", "message": "token expired" } }
```

## 5. Phase 1 test issuer (dev only)

| Item | Value |
|------|-------|
| Route | `POST /v1/dev/token` |
| Enabled when | `PICO_ENV != production` |
| Body | `{ "school_id", "membership_id", "scopes?" }` |
| Response | `{ "access_token", "token_type":"bearer", "expires_in", "claims_shape" }` |

## 6. Phase 3 edu issuer duties

edu-cloud MUST:

1. Authenticate the human/session in edu.
2. Mint Pico token only for **verified** membership in `school_id`.
3. Use short TTL; refresh via edu, not Pico.
4. Publish JWKS (if RS256) at a URL Pico configures as `PICO_EDU_JWKS_URL`.
5. Never send model API keys to the browser.

Pico MUST:

1. Drop Phase 1 HS256 test issuer in production.
2. Trust only configured edu `iss` + JWKS.
3. Keep validation path identical so claim shapes do not change.

## 7. Compatibility

Phase 1 tokens already use this claim set. Phase 3 changes **who signs**, not claim names.
