# Contract: Tools

```
STATUS: FROZEN
VERSION: 1.0
OWNER_GATEWAY: Pico
OWNER_IMPL_PHASE1: Pico FakeEdu + local tools
OWNER_IMPL_PHASE3: edu-cloud remote adapters behind same names
SCHEMA: packages/contracts/schemas/tool-invoke.schema.json
```

## 1. Principles

1. **Allowlist only** — unknown tool name → `tool.not_allowlisted`.
2. **Server intercept** — model never reaches host Shell/File/Web/MCP.
3. **Tenant fail-closed** — school-scoped tools bind to `token.school_id`.
4. **Adapter swap** — Phase 3 replaces FakeEdu implementation; **names + IO stay**.
5. **Idempotency** — mutating tools (Phase 3+) require `idempotency_key`.

## 2. Invocation envelope (control plane)

```http
POST /v1/tools/invoke
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "fake_edu_list_classes",
  "arguments": { "limit": 20 }
}
```

Success:

```json
{ "ok": true, "result": { } }
```

Failure:

```json
{ "detail": { "code": "tenant.cross_school", "message": "..." } }
```

Agent multi-step loop uses the same gateway internally; events mirror calls as `tool.call` / `tool.result`.

## 3. Function naming rule

Tool `name` MUST match: `^[a-zA-Z][a-zA-Z0-9_]*$`  
(Kimi/OpenAI function-name constraint — **no dots**.)

## 4. Phase 1 allowlist (realized)

| Name | Kind | School-scoped | Description |
|------|------|---------------|-------------|
| `pico_echo` | local | no | Smoke; echoes text + principal |
| `fake_edu_list_classes` | edu-read shape | **yes** | Synthetic classes for token school |
| `pico_propose_change` | local | no | Creates proposal payload (no school write) |

### 4.1 `pico_echo`

**Arguments:** `{ "text": string }`  
**Result:** `{ "echo", "school_id", "membership_id" }`

### 4.2 `fake_edu_list_classes`  ★ future edu read shape

**Arguments:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `school_id` | string | no | If present MUST equal token; else filled from token |
| `limit` | int | no | Default 20, max 100 |

**Result:**

```json
{
  "school_id": "school-a",
  "classes": [{ "id": "cls-a1", "name": "一年级 1 班" }]
}
```

**Phase 3 adapter:** same name/IO; fetch from edu read API; still gateway-enforced cross-school.

### 4.3 `pico_propose_change`

**Arguments:** `{ "title": string, "summary": string, "payload"?: object }`  
**Result:** `{ "proposal": { "title", "summary", "payload", "school_id", "membership_id", "status": "proposed", "note" } }`  
Does **not** write school business data.

## 5. Cross-school semantics

| Step | Behavior |
|------|----------|
| Detect | `arguments.school_id` present and ≠ `token.school_id` |
| Reject | `403` + code `tenant.cross_school` |
| Ledger | Emit Event `auth.deny` on the active Run (when in a run) or demo run |

## 6. Forbidden capabilities (hard)

Never register / enable for non-test agents:

- Shell / process execution  
- Host filesystem read/write  
- Web search / fetch  
- MCP arbitrary servers  
- Unallowlisted dynamic tools  

## 7. Phase 3 remote tool registration (preview)

edu may expose HTTPS tool endpoints; Pico adapter maps:

```text
fake_edu_list_classes  →  GET {EDU_BASE}/internal/pico/classes?school_id=
```

Contract for edu HTTP (Phase 3 detail can extend without renaming tool):

| Item | Value |
|------|-------|
| Auth | Service credential Pico→edu (not user JWT) |
| Tenant | Pico sends only `token.school_id` |
| Timeout | ≤ 10s |
| Error | Map edu 403 → `tenant.cross_school` |

## 8. Error codes

| Code | HTTP | Meaning |
|------|------|---------|
| `tool.not_allowlisted` | 400 | Unknown name |
| `tool.invalid_arguments` | 400 | Schema fail |
| `tool.upstream_error` | 502 | Phase 3 edu failure |
| `tenant.cross_school` | 403 | School mismatch |
| `auth.*` | 401/403 | See delegated-auth |
