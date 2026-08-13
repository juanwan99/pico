# Contract: Tools

```
STATUS: FROZEN
VERSION: 1.1
OWNER_GATEWAY: Pico
OWNER_IMPL_PHASE1: Pico FakeEdu + local tools + allowlisted web_search/web_fetch
OWNER_IMPL_PHASE3: edu-cloud remote adapters behind same names
SCHEMA: packages/contracts/schemas/tool-invoke.schema.json
ISSUE: #507 T-WEB-SEARCH-DS-THEN-FETCH
```

## 1. Principles

1. **Allowlist only** — unknown tool name → `tool.not_allowlisted`.
2. **Server intercept** — model never reaches host Shell / host filesystem / arbitrary MCP / unrestricted crawl.
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

Agent multi-step loop uses the same gateway internally; events mirror calls as `tool.call` / `tool.result`. Search/fetch also emit `search.sources` and usage-ledger `kind=search`.

## 3. Function naming rule

Tool `name` MUST match: `^[a-zA-Z][a-zA-Z0-9_]*$`  
(Kimi/OpenAI function-name constraint — **no dots**.)

## 4. Phase 1 allowlist (realized)

| Name | Kind | School-scoped | Description |
|------|------|---------------|-------------|
| `pico_echo` | local | no | Smoke; echoes text + principal |
| `fake_edu_list_classes` | edu-read shape | **yes** | Synthetic classes for token school |
| `pico_propose_change` | local | no | Creates proposal payload (no school write) |
| `web_search` | web (gateway) | no | DeepSeek official server-side search; sources or honest 未检索 |
| `web_fetch` | web (gateway) | no | Read one public http(s) URL → truncated text |

Workspace generate/verify tools remain registered on the product gateway (see true-Pi bridge allowlist). This table lists the original Phase-1 names plus the #507 web pair.

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

### 4.4 `web_search`  ★ #507 · DeepSeek official

**Upstream:** DeepSeek Responses API `tools: [{ "type": "web_search" }]` (server-side). Pico is a thin gateway: register the name, forward the query, map citations into the unique Pico ledger.

**Arguments:** `{ "query": string }`  

**Result (success or honest miss — never fake sources):**

```json
{
  "query": "…",
  "retrieved": true,
  "honest_miss": false,
  "message": "已检索 3 条来源",
  "sources": [{ "title": "…", "url": "https://…", "snippet": "…" }],
  "teacher_sources_md": "来源：\n- [title](url)",
  "provider": "deepseek"
}
```

If nothing usable: `retrieved=false`, `honest_miss=true`, `sources=[]`, message contains **未检索**.  
Optional Tavily adapter may run only when `TAVILY_API_KEY` is set; **must not** be required for green / prod.

**Usage:** `record_usage_event(..., kind="search", source="web_search")`. Extra may include `query_count` / `source_count` — never price/currency.

### 4.5 `web_fetch`  ★ #507 · public page read

**Arguments:** `{ "url": string }`  — **http/https only**.

**Deny (fail closed, human message):**

- loopback / unspecified (`127.0.0.0/8`, `::1`, `0.0.0.0/8`)
- RFC1918 (`10/8`, `172.16/12`, `192.168/16`) and link-local (`169.254/8`, `fe80::/10`)
- cloud metadata hosts (`169.254.169.254`, `metadata.google.internal`)
- Pico/edu admin surfaces (`pico.aivia.asia`, `mcu.asia`, compose names, ports 18765/27017, …)
- DNS that resolves to any of the above (redirect hops re-checked)

**Result:** `{ "url", "host", "text", "truncated", "sources": [{title,url,snippet}] }`  
Body truncated. Failures are human-readable (`web.denied` / `web.fetch_failed`).

**Usage:** `kind=search`, `source="web_fetch"`, extra may include `host` (never price).

**Teacher display (#513):** gateway `sources[]` / `teacher_sources_md` must be shown as clickable links in the result panel or main process. Honest miss copy is **未检索到可用来源**. Never invent URLs.

### 4.6 `sandbox_preview_inspect`  ★ #508 S1 · #513 S2

**Arguments:** `{ "artifact_id"?: string, "preview_url"?: string }` — this-run HTML only.

**Result:** `{ "title", "h1", "seen", "screenshot"?: { "artifact_id", "download_path", "mime", "byte_size" }, "raster"?: … }`  
S2 adds a real PNG raster of the same-run HTML (open via `GET /v1/artifacts/{id}/content`). Raster failure must not drop title/h1. Loopback / admin hosts still `web.denied`. Cross-account → `artifact.not_found`.

**Usage:** `kind=sandbox`, `source="sandbox"`. See [`docs/SANDBOX-S2.md`](../SANDBOX-S2.md).

## 5. Cross-school semantics

| Step | Behavior |
|------|----------|
| Detect | `arguments.school_id` present and ≠ `token.school_id` |
| Reject | `403` + code `tenant.cross_school` |
| Ledger | Emit Event `auth.deny` on the active Run (when in a run) or demo run |

## 6. Forbidden capabilities (hard)

Never register / enable for non-test agents:

- Shell / process execution (host bash, arbitrary command)
- Host filesystem read/write (outside the Artifact ledger)
- **Unrestricted** web crawl, browser login / B3, or fetching intranet / metadata
- MCP arbitrary servers
- Unallowlisted dynamic tools

**Allowed web (this contract):** gateway-allowlisted `web_search` and `web_fetch` only, as specified in §4.4–4.5.

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
| `tool.upstream_error` | 502 | Phase 3 edu failure or DeepSeek search upstream |
| `web.denied` | 400 | SSRF / intranet / admin-host deny |
| `web.fetch_failed` | 400 | Public fetch timeout / HTTP error (human message) |
| `tenant.cross_school` | 403 | School mismatch |
| `auth.*` | 401/403 | See delegated-auth |
