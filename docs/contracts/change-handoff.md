# Contract: Change Handoff

```
STATUS: FROZEN
VERSION: 1.0
OWNER_PROPOSAL: Pico
OWNER_BUSINESS_COMMIT: edu-cloud (Phase 3)
SCHEMA: packages/contracts/schemas/change-proposal.schema.json
```

## 1. Goal

Allow agents to **propose** school-data mutations without Pico becoming school SoT.

```text
Agent / user → ChangeProposal (Pico)
    → Human confirm in Pico UI (mandatory)
    → Pico audit row
    → [Phase 3] handoff to edu Review / Commit
    → edu writes school DB
    → optional callback to Pico (status=committed|rejected)
```

## 2. Phase 1 (realized — audit only)

| Step | API / behavior |
|------|----------------|
| Propose | `POST /v1/changes` or tool `pico_propose_change` |
| List | `GET /v1/changes` |
| Confirm | `POST /v1/changes/{id}/confirm` |
| Effect | status `confirmed` + audit; **no school row written** |

Statuses: `proposed` → `confirmed` | `rejected` (reject API optional Phase 1).

## 3. Proposal payload conventions

`payload` is an **opaque business intent** object for edu. Recommended keys:

```json
{
  "domain": "classes" | "grades" | "exams" | "members" | "other",
  "action": "create" | "update" | "delete" | "reassign" | "...",
  "resource_type": "class",
  "resource_id": "cls-a1",
  "patch": { },
  "idempotency_key": "uuid"
}
```

Pico does not interpret `patch` beyond storage + display.

## 4. Phase 3 handoff API (edu implements)

### 4.1 Pico → edu (push) — preferred

```http
POST {EDU_BASE}/internal/pico/change-proposals
Authorization: Bearer <pico-service-credential>
Content-Type: application/json

{
  "pico_change_id": "uuid",
  "school_id": "string",
  "membership_id": "string",
  "title": "string",
  "summary": "string",
  "payload": { },
  "confirmed_at": "ISO-8601",
  "confirmed_by": "membership_id"
}
```

edu response:

```json
{
  "edu_review_id": "string",
  "status": "accepted_for_review"
}
```

### 4.2 edu → Pico (status callback)

```http
POST {PICO_BASE}/v1/hooks/edu/change-status
Authorization: Bearer <edu-service-credential>

{
  "pico_change_id": "uuid",
  "edu_review_id": "string",
  "status": "committed" | "rejected",
  "detail": { }
}
```

Pico updates local proposal + audit; still **does not** write school data.

### 4.3 Pull alternative

edu may `GET {PICO_BASE}/v1/internal/changes?status=confirmed&school_id=` with service auth. Same payload fields.

## 5. Hard rules

1. No silent business write from agent tool results.
2. Confirm is a **human** (or explicitly delegated school admin) action.
3. Pico ledger remains source of AI proposal history.
4. edu ledger remains source of committed school facts.
5. Phase 3 cutover: retire edu AI runtime/workbench so proposals are not duplicated.

## 6. Mapping to future Review / Commit terms

| Pico term | edu term (Phase 3) |
|-----------|---------------------|
| ChangeProposal | Review candidate |
| confirm | acknowledge for Review queue |
| edu committed | Commit |
| edu rejected | Review reject |

Exact edu table names are edu-internal; this contract only freezes the **handoff envelope**.
