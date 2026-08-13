# Pico architecture (v0)

```
STATUS: subordinate to docs/TRUTH-FREEZE.md + docs/WHAT-IS-PICO.md
NOTE: "Orchestration" below is TARGET; implementation as of freeze may still be transitional tool-loop
```

## Layers

1. **UI** — LibreChat workbench (task-first); rail / main / artifacts as product IA.
2. **Orchestration (TARGET)** — **Open-source Kimi Agent** (pinned); map agent events → Pico Run/Event.  
   **CURRENT (transitional):** server-side OpenAI-compatible tool loop (`run_agent_loop`); must not be described as "Kimi Agent already integrated".  
   **FORBIDDEN:** pre-commit alternate runtimes (Pi/OpenCode/…) in truth docs; if Kimi Agent cannot embed, stop and re-discuss with owner.
3. **Control plane API** — create task, stream run, cancel, retry, list artifacts; principal server-side only.
4. **Providers** — Kimi (Moonshot) first; DeepSeek/other OpenAI-compatible optional.
5. **Tools** — allowlisted; host Shell/File off; unrestricted crawl off; gateway `web_search` + `web_fetch` only (#507).

## Tenancy

- Every run requires school + membership (or explicit platform principal).
- Model cannot widen scope via prompt.
- Cross-school tool access fail-closed.
- Historical Task lookup applies `school_id` + `membership_id` + `conversation_id`
  before the bounded result window; account growth must not hide an older conversation's ledger.

## Teacher sandbox

- **Not in scope** for default teacher workbench (no Codex-style exec sandbox).
- School isolation = **data tenancy / RLS-style boundaries** (with edu-core), not per-school exec VMs.

## Integration contract (sketch)

Edu-cloud / edu-core will:

- Obtain Pico tokens or service credentials scoped to membership.
- Call Pico to start runs with `context_refs` (exam id, class id, …).
- Receive proposed changes; commit only after Review when mutating school facts.

Details freeze in a short OpenAPI once MVP streams.

---

See also: [TRUTH-FREEZE](./TRUTH-FREEZE.md) · [WHAT-IS-PICO](./WHAT-IS-PICO.md) · [整体技术架构方案（含定价）](./OVERALL-ARCHITECTURE.md)
