# D1 Freeze Record

```
DOC: docs/D1-FREEZE.md
STATUS: SUBMITTED
PLAN: docs/MVP-3DAY.md v1.2 FIXED
BRANCH: feat/mvp-d1-scaffold
DATE: 2026-07-29
VERDICT_AUTHORITY: NONE  (write window — do not self-PASS S1–S8)
```

## 1. Frozen choices (binding for Phase 1)

| Item | Value | Evidence |
|------|-------|----------|
| API / orchestrator language | **Python ≥ 3.12** (plan says 3.11+; **kimi-agent-sdk requires ≥3.12**) | `pyproject.toml` `requires-python` |
| Frontend | **LibreChat (product shell)** | `apps/librechat` — legacy shells removed |
| Agent SDK | **`kimi-agent-sdk==0.0.5`** | `requirements.txt` |
| Agent runtime | **`kimi-cli==1.12.0`** (SDK pin range `>=1.12,<1.13`) | `requirements.txt` |
| Agent config file | `services/orchestrator/agents/pico.yaml` | empty dangerous tools; allowlist only |
| Primary model API | **Kimi / Moonshot HTTPS API** | `KIMI_*` in `.env.example` |
| Fallback model | DeepSeek HTTPS API only if Kimi unavailable (still real API) | `.env.example` |
| Spend caps | `PICO_RUN_MAX_SECONDS=120`, `PICO_RUN_MAX_TOKENS=8000`, `PICO_RUN_MAX_RETRIES=2` | `.env.example` + settings |
| Contract skeletons | four files under `docs/contracts/` | this PR |

## 2. Agent safety proof (D1 exit)

Non-test Agent runtime **must not** expose:

| Capability | Status in `pico.yaml` |
|------------|------------------------|
| Shell (`kimi_cli.tools.shell:Shell`) | **OFF** — not in `tools` |
| Host File (Read/Write/Glob/Grep/StrReplace/…) | **OFF** — not in `tools` |
| Web (SearchWeb / FetchURL) | **OFF** — not in `tools` |
| MCP servers | **OFF** — no MCP config; gateway rejects unknown tools |
| Arbitrary tools | **OFF** — only Pico allowlist gateway |

**Proof mechanism:** `tests/security/test_agent_tools_off.py` loads the agent spec via `kimi_cli.agentspec.load_agent_spec` and asserts zero dangerous tool paths. CI runs this job.

If a future pin cannot prove these boundaries → **MVP BLOCKED** (no home-grown agent framework).

## 3. S1 model hello status

| Condition | Result |
|-----------|--------|
| `KIMI_API_KEY` set | `scripts/model_hello.py` must stream a real completion |
| Key missing | **BLOCKED S1** (honest; not fake green) — non-S1 work continues |

D1 does **not** self-declare S1 PASS.

## 4. Spend / night guardrails

- Bounded retries (`PICO_RUN_MAX_RETRIES`)
- Per-run wall clock + token caps
- Night: no merge main, no unlimited model burn

## 5. Pin change policy

Changing `kimi-agent-sdk` / `kimi-cli` versions requires:

1. Update this freeze table + `requirements.txt`
2. Re-run `tests/security` + `scripts/check_agent_pin.py`
3. Re-prove tool boundary


## D2/D3 runtime addendum

Implemented on same freeze pins without changing Agent versions:

- Task/Run/Event/Artifact/ChangeProposal ledger (SQLite)
- Server multi-step tool loop via Kimi HTTPS tool-calling + allowlist gateway
- Tool names use `_` (Kimi rejects `.` in function names)
- UI streams Event timeline; S7 confirm + audit; cross-school `auth.deny` Event
- See `docs/DEMO.md`
