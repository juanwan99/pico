# KA-4 HARD（物理收敛）

```
DOC: docs/KA4-HARD.md
STATUS: BINDING · #288
DATE: 2026-08-05
AUTH: KA4_HARD_AUTH
```

## 做

| 项 | 说明 |
|----|------|
| 方案 | **A** — 删除 `services/orchestrator/pico_orchestrator/runner.py` 与 `run_agent_loop` |
| 共享类型 | `run_types.py`（`RunCaps` / `RunResult` / `EventEmitter` / `provider_label`） |
| 路由 | 仅 `run_kimi_agent`；非 KA 选择 → **fail-closed** 明确错误 |
| emergency | `PICO_LEGACY_AGENT_LOOP_EMERGENCY` **永久 no-op**（env 可留，不改路由） |
| RUNTIME=0 | multi-step **fail-closed**（不再回 loop） |
| 回滚 | **redeploy 旧 tip**（非双核） |

## 不做

假删 · dual-run · Pi · DeepSeek 默认 · 自 product PASS / orchestration complete

## 删除清单

- `services/orchestrator/pico_orchestrator/runner.py`（整文件）
- `tests/unit/test_runner_workspace_tools.py`（依赖已删 loop）
