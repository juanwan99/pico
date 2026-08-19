# Grok identity bridge

```
DOC: docs/GROK-AUTH-BRIDGE.md
STATUS: adapter contract
SCOPE: Pico-side JWT issuer only
NOT: xAI model access · not edu-cloud · not a second agent kernel
```

## What this is

Pico already has two identity issuers:

| Issuer | Env | When |
|--------|-----|------|
| Test HS256 | `PICO_JWT_SECRET` + `PICO_ACCEPT_TEST_ISSUER` | Dev / break-glass |
| Edu HS256 / RS256 | `PICO_EDU_ISS` + secret or PEM | Phase 3 edu |

This slice adds a **third, optional issuer** for workbenches that already do real Grok login (`auth.grok.me` / Google / X) and then mint a **short Pico JWT**.

```text
Grok login (identity)  →  workbench mints 15-min HS256 ticket
                              iss = https://auth.grok.me
                              aud = pico-api
                              school_id / membership_id / scopes
                       →  Pico verifies with PICO_GROK_JWT_SECRET
```

Pico is **not** an OAuth client of `auth.grok.me`. The preview client (`grok_preview`) only allows `*.grok-sandbox.com` callbacks. Self-hosted Pico cannot complete that OAuth. Login stays in the workbench; Pico only verifies the minted ticket.

## What this is not

- **Not** an xAI / Grok model key. `PICO_GROK_JWT_SECRET` never calls `api.x.ai`.
- **Not** a forwarded Grok session cookie / broker access token. Those have the wrong type and would be a confused-deputy.
- **Not** a flip of `PICO_MODEL_PROVIDER`. Product default brain stays whatever Pico already ships.
- **Not** `pico-dev` / `sk-pico-dev`. Those stay non-production proxy keys.

## Env

```bash
# Empty secret = issuer disabled (default).
PICO_GROK_ISS=https://auth.grok.me
PICO_GROK_JWT_SECRET=
```

Production fail-closed (only when the secret is set):

- secret ≥ 32 characters and not a known default
- secret **must not** equal `PICO_JWT_SECRET`
- `PICO_GROK_ISS` must be non-empty

Recommended production: `PICO_ACCEPT_TEST_ISSUER=false` and a dedicated grok-bridge secret. Generate with `openssl rand -base64 48`.

## Claim shape (same as test / edu)

Required: `exp`, `iat`, `iss`, `aud`, `school_id`, `membership_id`, `scopes`.

Workbench (浪台) mints:

```json
{
  "iss": "https://auth.grok.me",
  "aud": "pico-api",
  "school_id": "langtai",
  "membership_id": "<grok user id>",
  "scopes": ["ai:run", "ai:read", "ai:confirm"],
  "sub": "langtai:<membership>",
  "amr": ["grok-auth"]
}
```

TTL ceiling on this issuer: **30 minutes** (`exp - iat`). Workbench default is 15 minutes.

## Risks (binding)

| Risk | Mitigation |
|------|------------|
| Shared HS256 secret is a root key | Dedicated secret; never commit; rotate if leaked |
| Reusing `PICO_JWT_SECRET` | Production startup rejects reuse |
| XSS steals a minted ticket | 15-min TTL; workbench does not persist the ticket |
| Forwarding Grok session to Pico | Decode requires Pico claim shape + grok secret → reject |
| `pico-dev` on production | Existing P0 fail-closed |
| Operator pastes a model key as the JWT secret | Workbench rejects `sk-` / `xai-` / DeepSeek-shaped values |
| Public `/health` mistaken for “auth works” | Probe `/v1/models` (`ai:read`) |

## Thin adapter check

- Adapts: existing `decode_token` issuer list.
- Upstream: workbench Grok OAuth + Pico JWT claim contract.
- Upgrade path: only this issuer block + env. No new kernel, ledger, or OAuth stack inside Pico.
