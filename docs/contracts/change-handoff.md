# Contract: Change Handoff (skeleton)

```
STATUS: SKELETON (Phase 1: proposal + human confirm + audit only)
VERSION: 0.1
```

## Flow (future edu write-back)

```text
Pico Agent proposes Change
    → human confirm in Pico UI (S7)
    → audit row in Pico
    → (Phase 3) handoff to edu Review / Commit
    → edu owns business write
```

## Phase 1 minimum (S7)

| Step | Pico behavior |
|------|----------------|
| Propose | Create `change_proposal` fact + Event |
| Confirm | Explicit UI action; no silent business write |
| Audit | Immutable audit line (who/when/what) |

## Phase 3 boundary

- edu Review/Commit owns school DB mutations.
- Pico never becomes school business source of truth.
- No dual AI ledger: edu legacy AI retired atomically.

## Interface sketch (not implemented in D1)

```http
POST /v1/changes/{id}/confirm   # human confirm
GET  /v1/changes/{id}/audit
# Phase 3: edu webhook / pull for pending commits
```


## Phase 1 realized

- `POST /v1/changes` creates `change_proposals` row status=`proposed`
- `POST /v1/changes/{id}/confirm` sets `confirmed` + audit_log row
- Explicit UI confirm required — no silent business write
- Phase 3: replace audit-only confirm with edu Review/Commit handoff
