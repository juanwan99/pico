# Pico architecture (current)

```
STATUS: subordinate to docs/TRUTH-FREEZE.md v2.2 + docs/WHAT-IS-PICO.md + DIRECTION-NOW §0-star
DATE: 2026-09-19
NOTE: This page is a layer sketch. Frozen product/runtime sentences live in TRUTH-FREEZE.
      docs/OVERALL-ARCHITECTURE.md (2026-07-29 Kimi / 点池 draft) is not live.
```

## Layers

1. **UI** — LibreChat workbench (`apps/librechat`). Conversation + result pane. Not a scene workflow.
2. **Control plane** — Pico API: JWT principal, Task / Run / Event / Artifact, cancel / retry, usage ledger. Browser is a subscriber, not the job owner.
3. **Orchestration (default unique)** — **true Pi RPC** (`health.default_runtime=pi-true`, `run_true_pi_agent`). Events map into the Pico ledger.  
   **Rollback only (explicit flag, not a second official kernel):** hosted `pi_runtime` (`PICO_HOSTED_LOOP=1`); Kimi Agent (`PICO_KIMI_AGENT_RUNTIME`).  
   **Removed:** self-built `run_agent_loop`. Do not revive.
4. **Model / metering** — **New API only** (chat `openai-responses`, images on the same gateway). Slot names may still be `DEEPSEEK_*`. Outward name is Pico. No vendor-direct second ledger.
5. **Tools** — allowlist gateway. Host shell / Pi builtins / generic `exec` off. Office write path = `sandbox_office_lib` in the `pico-office` container. HTML still uses `generate_html_document` (shortcut, not a second office kernel). `generate_docx` / `generate_pptx` / inspect projectors are unregistered.
6. **School library** — Meili mount (chunk index; hybrid + New API embed/rerank when on). Pico does not pick an embedding vendor. Chat paperclips are not the school library.

## Tenancy

- Every run requires school + membership (or an explicit platform principal).
- The model cannot widen scope via the prompt.
- Cross-school tool access fail-closed.
- Historical Task lookup applies `school_id` + `membership_id` + `conversation_id` before the bounded result window.

## Teacher sandbox / office computer

- HTML preview + inspect: [SANDBOX-S1.md](./SANDBOX-S1.md) / [SANDBOX-S2.md](./SANDBOX-S2.md). Not a PDF kernel.
- Office execution: isolated `pico-office` (no net, no secrets, tmpfs). Full Python + python-docx / openpyxl / python-pptx. Not host bash. Not an interpreter jail inside pico-api.
- Not a per-school VM / cloud PC.

## Integration (edu)

- Pico = AI process ledger. edu-core = money / school facts.
- edu pulls `usage/export` `points` and must not multiply. This repo does not write edu.

## See

[TRUTH-FREEZE](./TRUTH-FREEZE.md) · [WHAT-IS-PICO](./WHAT-IS-PICO.md) · [LAW](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md) · [USAGE-LEDGER](./USAGE-LEDGER.md)
