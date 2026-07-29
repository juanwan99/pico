# Pico

**Standalone AI foundation** for the 微与积 / edu product line.

Pico is **not** a second school SaaS and **not** a teacher netdisk product.  
It is the **AI space**: experience + agent orchestration + model API access.

## Product shape

| Layer | Responsibility |
|-------|----------------|
| Experience | Claude-style IA (chat + artifacts) + Kimi-like density; deep clone of mature AI UX, not a novel shell |
| Agent orchestration | **Kimi open-source Agent runtime** (thin adapters only — do not invent an agent OS) |
| Governance facts | Task / Run / Event (and later Change / Review / Commit) owned in DB; sessions are not business truth |
| Models | **HTTP APIs only** (Kimi and/or DeepSeek); thin provider adapters; keys never in the browser |
| Education SaaS | Lives in **[edu-cloud](https://github.com/juanwan99/edu-cloud)**; Pico exposes tools/APIs edu mounts |

## Relationship to edu-cloud

```
edu-cloud (schools, exams, membership, deploy)
     │  tools / auth context / review write-back
     ▼
pico (AI workspace + agent + model API)
```

- **edu-cloud** keeps multi-tenant school business and OneFlow release for the school product.
- **pico** iterates AI UX + agent + providers at higher speed; integrates via versioned API/SDK and shared auth contracts.
- Do **not** duplicate exam/grade/student domains inside Pico.

## 3-day MVP bar (initial)

1. One model API path live (Kimi **or** DeepSeek first).
2. Kimi Agent really runs multi-step tools server-side.
3. Task/Run/Event (or equivalent) persisted; school/membership injected server-side.
4. Existing-style three-pane UI connected (task + stream + one artifact type).
5. 1–2 read-only tools + cross-tenant deny.
6. Minimal human confirm path for proposed writes (full exam write-back can stay in edu-cloud later).

## Non-goals (v0)

- Full 5GB file-product contract as the product center
- Self-hosting model weights as default
- Rebuilding edu business modules inside this repo
- Skipping auth / tenant fail-closed

## Status

Repository bootstrap. Implementation slices land as Issues/PRs in this repo.
