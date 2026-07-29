# Contract: Tools (skeleton)

```
STATUS: SKELETON
VERSION: 0.1
```

## Principles

1. **Allowlist only** — tools not registered in Pico gateway are rejected.
2. **Server-side intercept** — model/tool_call never executes raw host capabilities.
3. **Tenant fail-closed** — every school-scoped tool checks `token.school_id`.
4. **Idempotency** — mutating tools (Phase 3) carry client idempotency keys.

## Phase 1 tools (planned shapes)

| Name | Kind | Phase 1 adapter | Notes |
|------|------|-----------------|-------|
| `fake_edu_list_classes` | read | FakeEdu + synthetic data | future edu read shape |
| `pico_echo` | local | Pico | smoke / allowlist demo |
| *(more)* | — | — | ≥2 allowlist tools by S6 |

### `fake_edu_list_classes` (draft)

**Input**

```json
{
  "school_id": "string",
  "limit": 20
}
```

**Output**

```json
{
  "school_id": "string",
  "classes": [{ "id": "string", "name": "string" }]
}
```

**Errors**

| Code | When |
|------|------|
| `tenant.cross_school` | `input.school_id != token.school_id` |
| `tool.not_allowlisted` | unknown tool name |

## Forbidden by default

Shell · host File · Web · MCP · any non-allowlisted tool.

