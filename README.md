# Pico

**Standalone AI foundation** for the 微与积 / edu product line.

Pico is **not** a second school SaaS and **not** a teacher netdisk product.  
It is the **AI space**: experience + agent orchestration + model API access.

## Product shape

| Layer | Responsibility |
|-------|----------------|
| Experience | Claude-style IA (chat + artifacts) + Kimi-like density |
| Agent orchestration | **Kimi open-source Agent runtime** (thin adapters only) |
| Governance facts | Task / Run / Event owned in Pico DB (unique AI ledger) |
| Models | **HTTP APIs only** (Kimi / DeepSeek); keys never in the browser |
| Education SaaS | **[edu-cloud](https://github.com/juanwan99/edu-cloud)** — Phase 3 wire-up |

## Status

**3-Day MVP plan: FIXED v1.2** — [`docs/MVP-3DAY.md`](docs/MVP-3DAY.md)

| Phase | Goal |
|-------|------|
| **1 (this repo now)** | Independent Pico: Agent + model API + UI + ledger + CI |
| **2** | Integration contracts |
| **3** | edu-cloud wire-up + retire edu AI |

Handoff: [`docs/HANDOFF.md`](docs/HANDOFF.md)  
D1 freeze: [`docs/D1-FREEZE.md`](docs/D1-FREEZE.md)  
Demo: [`docs/DEMO.md`](docs/DEMO.md)  
Phase 1 status: [`docs/PHASE1-STATUS.md`](docs/PHASE1-STATUS.md)  
Phase 2 contracts: [`docs/PHASE2-CONTRACTS.md`](docs/PHASE2-CONTRACTS.md) **FROZEN v1.0**  
Phase 3 integrate: [`docs/PHASE3-INTEGRATION.md`](docs/PHASE3-INTEGRATION.md)

## Layout

```text
apps/web/                 Vue 3 + Vite three-zone shell
services/api/             FastAPI control plane
services/orchestrator/    Kimi Agent pin + allowlist gateway
docs/contracts/           Phase 2 contract skeletons
tests/security/           Shell/File/Web/MCP-off proofs
```

## Prerequisites

- **Python 3.12+** (kimi-agent-sdk requires ≥3.12; plan floor was 3.11+)
- Node 20+ (22 recommended)
- Optional: `KIMI_API_KEY` for S1 real-model streaming

## Quick start — 今日独立原型

```bash
cp .env.example .env   # set KIMI_API_KEY
make proto             # API :8000 + Web :5173
# open http://127.0.0.1:5173
make demo              # headless S4→S7 proof
```

Demo script: [`docs/DEMO.md`](docs/DEMO.md)

### Manual two-terminal

```bash
make install
make api    # terminal A
make web    # terminal B
```

### Useful commands

```bash
make test            # unit + security
make security-check  # agent tools OFF proof
make freeze-check    # pinned SDK/runtime versions
make hello           # real model hello or honest S1 BLOCKED
```

## Agent pin (D1)

| Package | Version |
|---------|---------|
| `kimi-agent-sdk` | **0.0.5** |
| `kimi-cli` | **1.12.0** |

Dangerous host tools (Shell / File / Web / MCP) are **off** in  
`services/orchestrator/agents/pico.yaml`. See CI job + `tests/security`.

## Phase 1 success criteria

S1–S8 are defined in [`docs/MVP-3DAY.md`](docs/MVP-3DAY.md).  
Write windows have **`VERDICT_AUTHORITY: NONE`** — do not self-PASS.

## Non-goals (Phase 1)

- Daily edu-cloud integration / dual AI ledger
- Netdisk product center
- Custom agent OS
- Unattended merge to `main`
