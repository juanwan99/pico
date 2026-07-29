# Pico — 3-Day MVP Plan **v1.1** (Codex REVISE applied)

```
STATUS: REVISED — awaiting PLAN: PASS re-confirm or execute on owner GO
SUPERSEDES: docs/MVP-3DAY.md @ d8fee789 (v1)
REPO: juanwan99/pico
BASELINE_MAIN_AT_REVIEW: d8fee789d61e6aa07dd921a205746e72c6b553a0
REVIEWER: Codex → PLAN: REVISE (6 must-fix) on pico#1
AUTHOR: Grok-Global-Control
```

---

## 0. 前因后果（unchanged intent, sharper boundary)

### 0.1 Parent product

**edu-cloud** = multi-school education SaaS (membership, exams, grading, deploy/OneFlow).  
Architecture freeze: database owns school business truth; AI must not become a second business truth.

### 0.2 Product correction

「教师 / AI 空间」= ChatGPT / Grok / Kimi **class product** (experience + **agent orchestration** + artifacts), **not** a netdisk.  
Models = **HTTP APIs** (Kimi / DeepSeek). Orchestration = **open-source Kimi Agent** (thin patches only).  
Business SaaS stays in edu-cloud and **connects** via tools + membership credentials + reviewable writes.

### 0.3 Why Pico exists + **frozen ownership (Codex #1)**

| Owner | Facts |
|-------|--------|
| **Pico (sole AI product)** | **All** AI Task / Run / Event / Artifact / Change / Review / Commit truth from **D1** |
| **edu-cloud** | School business facts only (students, exams, grades, membership, deploy…) |

**Cutover outcome (binding):**

- edu-cloud **AI runtime / AI workbench / AI API / AI worker paths are retired atomically**.
- They **must never run in parallel** with Pico as a second AI stack.
- No “Pico-local Task/Run first, align edu AI later” dual-running period.
- edu may keep **thin client/embed** that calls Pico; it must not own competing AI run ledgers.

### 0.4 Available assets

| Asset | Use |
|-------|-----|
| edu AI workbench shell (disconnected) | **IA reference only** → reimplement/port under Pico; then **delete/retire** edu AI surfaces |
| edu `ai_foundation` Task/Run/Event | **Pattern reference** → Pico is system of record; edu path **tombstoned**, not dual-written |
| Kimi Agent SDK/Code | Runtime driver (version **pinned before D1 writers**) |
| Model HTTP APIs | Provider adapters |
| edu membership | **Issuer of short-lived Pico credentials** (see §2) |

---

## 1. Success definition (end of Day 3) — v1.1

**MVP PASS only if S1–S8 all hold.**

| ID | Criterion |
|----|-----------|
| **S1** | **One real** model provider API (Kimi **or** DeepSeek) end-to-end; streaming to UI; keys server-side only. **Mock cannot satisfy S1** (Codex #5). Separate secret-backed job may collect provider evidence. |
| **S2** | **Pinned** Kimi Agent runtime runs multi-step tool loop **server-side**. |
| **S3** | Pico DB persists **Task + Run + ordered Events** (+ artifact metadata as needed). Cancel/fail/success correct. **Pico is sole ledger.** |
| **S4** | **edu-issued membership-scoped credential only** on product path (Codex #2): issuer, audience, expiry, school_id, membership_id, scopes. Request body/prompt **cannot** supply or widen identity. Tests may use **fixtures** that mint the same shape; **no product “principal stubs”**. |
| **S5** | Three-zone UI live: history/tasks, compose+stream+tool timeline, ≥1 artifact type. Honest errors. |
| **S6** | **≥1 real read-only edu-cloud tool** against **synthetic/Preview business data** via **API boundary** (Codex #3), plus any additional Pico tools if needed. **Cross-school denial enforced at edu capability boundary**, recorded as Pico run **Event**. (Two Pico-only toys **do not** prove the split.) |
| **S7** | Minimal confirm path: proposal → human confirm → audit in Pico; no silent school-fact write. Edu write-back may be interface/stub **after** confirm policy is real. |
| **S8** | **CI mandatory** (Codex #5): CANDIDATE PR → **exact-SHA CI green** → independent review → **attended** merge. S8 is **not** satisfied by “docs saying checks later.” |

### Non-goals (Day 3)

- Netdisk/#428 full file product as center  
- Vendor pixel/trademark clone  
- Dual model product routing  
- Rebuilding edu domains inside Pico  
- Leaving edu AI stack alive “for a while”  
- Unattended merge to main  

---

## 2. Auth contract (freeze before parallel writers — Codex #2, #6)

**Delegated auth (product path):**

```text
edu-cloud (issuer)
  mints short-lived token/assertion
  aud = pico
  claims: school_id, membership_id, scopes[], exp, iss
       │
       ▼
Pico API middleware
  verify signature/iss/aud/exp
  bind Run to claims
  reject missing/forged/widened identity
```

- Prompt and JSON body **must not** be trusted for identity.  
- Fixtures in tests mint **same claim shape** with test keys.  
- D1 deliverable: short `docs/contracts/delegated-auth.md` + OpenAPI sketch frozen.

---

## 3. Agent safety boundary (Codex #4)

Before any non-test Agent run:

| Built-in | MVP state |
|----------|-----------|
| Shell | **Disabled** |
| File (host FS) | **Disabled** |
| Web | **Disabled** |
| MCP / arbitrary tools | **Disabled** |
| Pico allowlisted tools only | **Enabled** (incl. ≥1 edu read tool) |

- SDK approval / tool-call events **intercepted server-side**; only allowlist may execute.  
- If **pinned** SDK/runtime **cannot prove** this boundary → **MVP BLOCKED** (do **not** replace with a custom agent framework).

---

## 4. Edu tool boundary (Codex #3)

```text
Pico Agent tool call
  → Pico tool gateway (allowlist + principal from token)
  → edu-cloud capability API (Preview/synthetic data OK)
  → edu enforces school scope; cross-school → deny
  → Pico records Event (success|deny|error)
```

- Proves **repo split + SaaS integration**, not only local stubs.  
- Synthetic/Preview data is enough for MVP; no production student PII required.

---

## 5. Architecture (v1.1)

```text
Pico Web (Vue 3 + Vite) ──────────────────────────────┐
                                                      │
Pico API + principal middleware (edu token)           │
                                                      │
Orchestrator: Kimi Agent (pinned) + allowlist gateway │
        │                        │                    │
        ▼                        ▼                    │
 Model HTTPS API          Tools: edu read + …         │
 (Kimi or DeepSeek)       (Shell/File/Web/MCP off)    │
        │                        │                    │
        └──────────► Pico DB: Task/Run/Event/Artifact ◄┘
                     (sole AI truth)

edu-cloud: membership issuer + business APIs + (retired AI surfaces)
```

---

## 6. D1 freezes before parallel writers (Codex #6)

Must be committed on main or MVP branch **before** W1/W2/W3 parallel code:

| Freeze | Decision |
|--------|----------|
| Agent | **Pin** Kimi Agent SDK/runtime **version or commit SHA** in lockfile/docs |
| Stack | **Python 3.11+** API/orchestrator + **Vue 3 / Vite** web (**fixed**) |
| Schema | Task / Run / Event (+ artifact meta) field list frozen in `docs/contracts/ai-facts.md` |
| Auth | Delegated-auth contract §2 frozen |
| Provider spend | Bounded retries, max wall time, max tokens/run — soaks cannot runaway |
| Provider choice | Primary: **Kimi API** (unless key missing → clock stop; DeepSeek only if Kimi impossible, still real API for S1) |

---

## 7. Day plan (with night unattended)

| Day | Attended | Night (low risk only) | Exit |
|----:|---|---|---|
| **D1** | Freezes §6; scaffold; pin Agent; provider hello stream; auth verify path; **prove** Shell/File/Web/MCP off | deps, unit tests, **no** unbounded provider loops | Pins + stream smoke + safety proof |
| **D2** | Persist facts; wire UI; tool timeline; start edu read tool | integration + cancel/timeout soaks under **token/time caps** | UI ← real Events |
| **D3** | Cross-school deny Event; confirm path; **CANDIDATE PR**; CI; independent review; **attended merge**; DEMO | full suite re-run only | **S1–S8** on merged main |

**Parallel after freezes:** W1 Agent+provider+gateway · W2 API+DB+auth · W3 Vue UI.  
**Serial:** schema + auth middleware + tool allowlist table.

**Night forbidden:** merge main, secret changes, production deploy, unlimited provider soaks.

---

## 8. CI / merge gate (Codex #5)

```text
branch work → CANDIDATE PR (exact SHA)
  → GitHub Actions CI green on that SHA
  → independent review PASS
  → attended merge to main
```

- Real provider evidence: optional secret-backed workflow or attended job; **still required for S1**.  
- Mock-only pipelines **cannot** close S1.

---

## 9. Demo script

1. Obtain **edu-issued** membership token (Preview/synthetic school A).  
2. Create task in Pico UI; stream model+agent.  
3. Agent calls **edu read tool**; timeline shows tool Event.  
4. Artifact panel shows result.  
5. Same user forges school B context on tool → **edu deny** + Pico Event.  
6. Proposal → UI confirm → audit row; no silent write.  
7. Cancel run → terminal state in Pico DB.  
8. Confirm edu AI routes **not** used (retired/tombstone check).

---

## 10. Risks / stop

| Risk | Action |
|------|--------|
| Cannot pin Agent or cannot disable Shell/File/Web/MCP | **BLOCKED** MVP |
| No real model API key | **STOP** clock; no S1 PASS |
| Edu Preview API unavailable for tool | Unblock with minimal read capability endpoint in edu **or** BLOCK S6 — do not fake with Pico-only tools only |
| Pressure to keep edu AI “temporary dual” | **Reject** — violates cutover |

---

## 11. Delta vs v1 (Codex 6 items)

| # | Fix in v1.1 |
|---|-------------|
| 1 | Pico sole AI truth D1; edu AI retired atomically; no parallel AI |
| 2 | edu-issued membership credential only; no product principal stubs |
| 3 | ≥1 real edu-cloud read tool + deny at edu boundary + Pico Event |
| 4 | Agent builtins off; allowlist only; else BLOCKED |
| 5 | CI + CANDIDATE + review + attended merge mandatory |
| 6 | Pin Agent, Python+Vue, contracts, spend bounds before parallel writers |

---

## 12. Ask / GO

```text
PLAN: PASS   → D1 freezes + scaffold may start
PLAN: REVISE → further must-fix list
```

Owner may also: **GO D1 on v1.1** if they accept this revision without a second Codex round.
