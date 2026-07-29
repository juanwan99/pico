# Pico architecture (v0)

## Layers

1. **UI** — Claude-like three zones: rail (history/tasks), main (compose + stream + tool timeline), artifacts (doc/table/report).
2. **Orchestration** — Kimi Agent SDK/runtime; map agent events → Pico Run/Event records.
3. **Control plane API** — create task, stream run, cancel, list artifacts; always resolve principal server-side.
4. **Providers** — `providers/kimi`, `providers/deepseek` (OpenAI-compatible where possible).
5. **Tools** — allowlisted; edu-cloud may register remote tools later; v0 can ship stub + 1–2 local read tools.

## Tenancy

- Every run requires school + membership (or explicit platform principal).
- Model cannot widen scope via prompt.
- Cross-school tool access fail-closed.

## Integration contract (sketch)

Edu-cloud will:

- Obtain Pico tokens or service credentials scoped to membership.
- Call Pico to start runs with `context_refs` (exam id, class id, …).
- Receive proposed changes; commit only after edu-side Review when mutating school facts.

Details freeze in a short OpenAPI once MVP streams.
