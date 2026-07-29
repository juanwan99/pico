# Phase 1 Status (post-merge)

```
PLAN: docs/MVP-3DAY.md v1.2 FIXED
MAIN: includes PR #3 (CANDIDATE merged by owner)
WRITE_WINDOW: VERDICT_AUTHORITY NONE (this doc is evidence, not self-PASS ceremony)
```

## S1–S8 scorecard

| ID | Standard | Evidence on main | Notes |
|----|----------|------------------|-------|
| S1 | Real model API stream; key server-side | `scripts/model_hello.py`, `/v1/dev/model-hello`, multi-step runs | Requires `KIMI_API_KEY` |
| S2 | Pinned Kimi stack multi-step tool loop server-side | `kimi-agent-sdk==0.0.5` + `kimi-cli==1.12.0`; `runner.py` allowlist loop | Host tools off via `pico.yaml` |
| S3 | Task+Run+ordered Event ledger | SQLite tables + API | Unique AI ledger in Pico |
| S4 | Short-lived claims shape | `/v1/dev/token` test issuer | Phase 3: edu signs |
| S5 | Product UI live | `apps/nextchat` | NextChat full shell → Pico OpenAI-compat |
| S6 | ≥2 allowlist tools + FakeEdu + cross-school Event | `fake_edu_list_classes`, `pico_echo`, `pico_propose_change`; `/v1/demo/cross-school-deny` | |
| S7 | Propose → human confirm → audit | `/v1/changes` + confirm | No school DB write |
| S8 | CANDIDATE → CI → review → watched merge | PR #3 merged to main after CI green | Owner merge |

## How to re-verify

```bash
cp .env.example .env   # set KIMI_API_KEY
make install
make api               # terminal A
make ui                # terminal B NextChat :8080
# terminal C
make demo              # scripts/demo_e2e.py against :8000
```

## Phase 1 explicit non-goals (still)

- edu-cloud live integration
- Dual AI ledger
- Shell/File/Web/MCP enabled
- Self-hosted GPU default

## Next

- **Phase 2 contracts: FROZEN v1.0** — [`PHASE2-CONTRACTS.md`](PHASE2-CONTRACTS.md)
- **Phase 3 Integrate** — see [`PHASE3-INTEGRATION.md`](PHASE3-INTEGRATION.md)

## Note on L2 (historical)

L2 PR #24 polished **SSE/stop on the deleted `apps/web` shell**. API fix (`session_factory` in stream) remains valuable. Product surface is **NextChat**; do not reintroduce `apps/web`.
