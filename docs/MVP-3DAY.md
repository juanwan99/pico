# Pico — 3-Day MVP Plan (for independent review)

```
STATUS: PROPOSAL
REPO: juanwan99/pico
BASELINE_MAIN: 5d9cd16ece77 (bootstrap docs only)
AUTHOR: Grok-Global-Control
REVIEW_TARGET: Codex → PLAN: PASS | REVISE | REJECT
RELATED: edu-cloud #408 (60-day control); AI work extracted from edu-cloud
```

---

## 0. 前因后果（Why Pico exists）

### 0.1 Parent product

**edu-cloud** is a multi-school education SaaS (membership, exams, grading, deploy/OneFlow). Architecture freeze:

- Database is the only business source of truth.
- AI drives work under DB governance (Task/Run/Change/Review/…); AI must not become a second truth.
- Frontend collaboration style is Codex/GitHub-like (task → run → change → review → publish).

### 0.2 What went wrong in planning

Global control (and earlier slices) partially treated 「教师空间」as a **netdisk / 5GB file product** (#428-style Space/File/Quota as the G1 center).

**User correction (binding):**

1. **Teacher / AI space ≈ ChatGPT / Grok / Kimi product class** — conversation, agent orchestration, artifacts — **not** a drive homepage.
2. **Do not invent a new UX paradigm** — deep-align one mature AI product (IA: Claude-style chat + artifacts; agent stack: Kimi).
3. **Business SaaS already exists in edu-cloud** — do not rebuild exams/HR inside the AI repo; **connect** via tools + auth + reviewable writes.
4. **Bottom model layer = HTTP API** (Kimi and/or DeepSeek), not self-hosted weights as default.
5. **Agent orchestration uses open-source Kimi Agent** — thin adapters only; no custom agent OS.
6. Night hours should run **low-risk long jobs** (tests, soaks); no unattended merge/release.

### 0.3 Why a separate GitHub repo

| Problem if AI stays only inside edu-cloud | Pico split |
|---|---|
| AI iteration blocked by school SaaS CI (~28 runner-min product PRs), alembic contention, module freezes | AI can move on its own cadence |
| Risk of AI work tangling exam/schema mega-slices | Clear ownership boundary |
| Empty “AI workbench shell” already exists in edu-cloud but disconnected | Pico owns the **real** AI product; edu-cloud later consumes |

**Pico** = standalone **AI foundation** (experience + orchestration + model APIs).  
**edu-cloud** = school business + membership + deploy; integrates Pico.

**Not allowed:** two long-lived competing AI products without an explicit cutover plan.

### 0.4 Assets already available (do not re-invent)

| Asset | Location | Use in MVP |
|---|---|---|
| DB Task/Run/Event vertical | edu-cloud master (PR #429) | **Pattern + later integration**; MVP may implement minimal equivalent **inside Pico** first, then align contracts |
| AI workbench three-pane shell (disconnected) | edu-cloud `frontend/.../ai-workbench` | **IA reference** (left rail / task console / result workspace + `needs_confirmation`); re-home or reimplement in Pico under Pico brand |
| Kimi Agent SDK / Kimi Code | upstream open source | **Runtime driver** |
| Model APIs | Kimi / DeepSeek HTTP | **Provider adapters** |
| Membership / fail-closed auth | edu-cloud | MVP: Pico-local principal stubs **or** signed context from edu; must fail-closed either way |

### 0.5 What “3-day MVP” is for

Prove end-to-end:

```text
UI → Pico API → Kimi Agent → Model API → tools (read) → events persisted → artifact visible → optional human confirm
```

Not: full education rewrite, full file product, production multi-school cutover.

---

## 1. Success definition (end of Day 3)

**MVP PASS only if all S1–S8 hold** (demo + automated tests; no theatre).

| ID | Criterion |
|----|-----------|
| **S1** | **One** model provider API works end-to-end (Kimi **or** DeepSeek first). Streaming tokens reach the UI. Keys server-side only. |
| **S2** | **Kimi Agent runtime** executes a multi-step tool loop **server-side** (not a frontend fake progress bar). |
| **S3** | Each run persists **Task + Run + ordered Events** (names may match edu-cloud). Cancel/fail/success reflected in DB. |
| **S4** | **Principal injected server-side** (school_id + membership_id or explicit platform principal). Prompt/body cannot widen scope. Missing principal → deny. |
| **S5** | UI: three zones live — history/tasks, compose+stream+tool timeline, **one** artifact type (doc **or** table). Honest empty/error states. |
| **S6** | **≥2 read-only tools** allowlisted; at least one **cross-tenant deny** test (tool refuses other school’s ref). |
| **S7** | **Minimal confirm path**: agent may emit a *proposal*; human confirm records acceptance; **no silent business write**. (Full exam grade write-back can remain stub/interface for edu-cloud.) |
| **S8** | Automated tests for S3–S7 happy + deny paths; CI green on default branch **or** documented required checks if CI not yet full. |

### Explicit non-goals (Day 3)

- Full #428 file/netdisk product  
- Pixel-perfect clone of any vendor UI / use of vendor trademarks as product identity  
- Dual hot model routing as a product feature (single provider OK; second provider adapter stub allowed)  
- Migrating all edu-cloud modules  
- Production OneFlow / multi-school G5 gates (those stay edu-cloud + later)  
- Self-hosted GPU inference as default  

---

## 2. Architecture (MVP)

```text
┌─────────────────────────────────────────────┐
│ Pico Web (Vue or minimal stack)             │
│ Rail | Compose+Stream+Tools | Artifact      │
└─────────────────┬───────────────────────────┘
                  │ HTTPS + auth cookie/JWT
┌─────────────────▼───────────────────────────┐
│ Pico API                                    │
│ POST /tasks /runs  · stream · cancel        │
│ principal middleware (fail-closed)          │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│ Orchestrator                                │
│ Kimi Agent runtime (thin config/patches)    │
│ map agent events → Run/Event rows           │
└─────────────┬───────────────┬───────────────┘
              │               │
              ▼               ▼
        Provider API     Allowlisted tools
        (Kimi/DS HTTP)   (read-only v0)
              │
              ▼
         Secrets (env)
```

**Governance rule:** Agent session IDs are external references only; **Pico DB owns recovery truth** for Task/Run/Event.

---

## 3. Day plan (calendar, with night unattended)

Assume T0 = plan PASS + secrets available.

| Day | Human window (build) | Night unattended (low risk) | Exit |
|----:|---|---|---|
| **D1** | Repo scaffold (API+DB+web skeleton); provider adapter #1; Agent process boots; smoke “hello” completion **without** tools | Install/deps; unit tests; retry provider flakes | Agent + API + model stream proof in logs/UI raw |
| **D2** | Persist Task/Run/Event; principal middleware; wire three-pane UI to real streams; tool timeline | Integration tests; long stream soaks; cancel/timeout cases | UI shows real run from DB events |
| **D3** | Two read-only tools + cross-tenant tests; confirm/proposal path; harden errors; CI; DEMO script | Full test suite re-run; no merge while sleeping | **S1–S8** evidence on main (or release tag) |

**Parallel slots (if 2–3 writers):**

| Slot | Focus | Touches |
|---|---|---|
| W1 | Agent + provider + orchestrator events | server core |
| W2 | API + DB schema + principal | server |
| W3 | Web three-pane + stream client | frontend |

**Serial hotspot:** event schema + principal middleware (one writer at a time).

**Forbidden night actions:** merge to main, secret rotation, production deploy.

---

## 4. Stack defaults (revisable on REVISE)

| Choice | Default | Rationale |
|---|---|---|
| Language | Python 3.11+ for API/orchestrator (align edu-cloud) | Shared patterns; Agent SDK bindings as available |
| Web | Vue 3 Vite (align edu-cloud workbench) **or** minimal React if Agent samples force it — **pick one on D1, document** | Reuse IA knowledge from edu AI shell |
| DB | SQLite for MVP OK; Postgres-ready schema | Speed; edu is multi-PG later |
| Agent | Kimi Agent SDK / Code runtime upstream | User mandate |
| Model | Kimi API first; DeepSeek adapter interface stub | User mandate API-only |
| Auth MVP | Dev JWT/HMAC with school_id+membership_id claims; document edu SSO later | Fail-closed without full edu coupling on day 1 |

---

## 5. Demo script (acceptance theatre must be real)

1. Login/dev principal as School A membership.  
2. Create task: “Summarize class roster tool output for my school.”  
3. Agent calls read tool; stream + tool events visible.  
4. Artifact panel shows short summary doc.  
5. Switch/forged School B id on tool → **denied**, event recorded.  
6. Proposal “update note X” → UI **needs confirmation** → confirm stores acceptance audit; no silent skip.  
7. Cancel an in-flight run → terminal state failed/cancelled in DB.

---

## 6. Risks and stops

| Risk | Response |
|---|---|
| No API key / billing on D1 morning | **STOP** MVP clock or run provider-mock **only** for wiring — **cannot claim S1 PASS** until real API once |
| Kimi Agent integration harder than “slight patch” | Cap D2: one tool loop + events; defer fancy swarm |
| Scope creep (file product, exam write-back) | Reject; track as post-MVP issues |
| Dual AI in edu-cloud + pico forever | Post-MVP: cutover issue; edu shell either embeds Pico or redirects |

---

## 7. Relationship back to edu-cloud (after MVP)

1. Freeze **OpenAPI** for create-run / stream / tools context.  
2. edu-cloud passes membership-scoped credential + `context_refs`.  
3. Mutating school facts: Pico proposal → edu Review/Commit (existing philosophy).  
4. Optional: replace edu `ai-workbench` disconnected shell with Pico embed/link.  
5. edu 20-day plan AI track becomes **integration**, not second agent rewrite.

---

## 8. Quality gates (no waiver)

- No self-PASS; independent review on MVP tag/PR.  
- Secrets not in git.  
- Tenant deny tests required (S6).  
- Honest UI if provider down (no fake success).  
- CANDIDATE PR + CI when CI exists.

---

## 9. Deliverables checklist

- [ ] Running app (docker-compose or `make dev`) documented in README  
- [ ] `docs/DEMO.md` with script §5  
- [ ] Schema migration for Task/Run/Event  
- [ ] Provider config sample `.env.example`  
- [ ] Test suite commands  
- [ ] Issue milestones D1/D2/D3 closed with evidence links  

---

## 10. Ask to Codex

Please return exactly one of:

```text
PLAN: PASS
PLAN: REVISE
  - …
PLAN: REJECT
  - …
```

Focus questions:

1. Is the Pico/edu-cloud split sound vs dual-source AI risk?  
2. Is S1–S8 the right MVP bar (too weak / too strong for 3 days)?  
3. Is “Pico-local Task/Run first, align edu later” acceptable vs forcing edu-cloud DB in week 1?  
4. Any must-fix before D1 scaffold?

---

## 11. Out of scope for this review

- edu-cloud 20-day full calendar rewrite (separate doc)  
- Production G5/G7 numbers (remain edu-cloud launch gates)  
