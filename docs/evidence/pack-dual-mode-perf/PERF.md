# Pico 双档性能对照表

## 目标

验证双档契约（本卡要求）：
- Pico 快速 = `pico-fast` -> `deepseek-v4-flash` + thinking off + 紧预算
- Pico 深度 = `pico-deep` -> `deepseek-v4-flash` + thinking on + 熔断

契约实现点：`services/orchestrator/pico_orchestrator/provider.py` 的
`runtime_policy_for_model()` / `should_circuit_break()`，
经 `services/api/app/openai_compat.py` 的 `_caps_with_dual_mode()` 注入
`RunCaps.thinking_on / max_steps / max_tokens`，
由 `services/orchestrator/pico_orchestrator/pi_runtime.py` 执行。

## 预算对照（代码即证据）

| 模式 | backend_model | thinking | max_steps | max_tokens | 熔断 |
|------|---------------|:---:|---:|---:|:---:|
| pico-fast | deepseek-v4-flash | off | 12 | 8000 | 否 |
| pico-deep | deepseek-v4-flash | on | 24 | 32000 | 是 |
| pico-agent（深度交付） | deepseek-v4-flash | on | 24 | 32000 | 是 |

## 样例记录

| 模式 | 题型 | wall_s | steps | tool_exec | art | oom | settle | notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| pico-fast | C1-HTML 交件 | 45 | 7 | 3 | 1 | N | Y | 快速路径稳定，产物落地 |
| pico-deep | hard-reasoning | 88 | 15 | 2 | 1 | N | Y | deep 模式保持 thinking on，并在正常范围内 settle |
| pico-deep | idle/no-progress | 120 | 24 | 0 | 0 | N | BAILOUT | repeated_no_progress >= 2，触发熔断人话 |

## 回归证据（tests/unit，2026-08-12）

| 用例 | 断言 | 结果 |
|------|------|:---:|
| `test_runtime_policy_dual_mode_contract` | fast/deep 均钉 `deepseek-v4-flash`；thinking 相反；预算 fast<deep | PASS |
| `test_circuit_breaker_only_in_thinking_on_lane` | fast 永不熔断；deep 空转/长挂/重挂熔断；有进展不熔断 | PASS |
| `test_pi_deep_lane_circuit_breaker_bails_on_no_progress` | deep 空转 ≤6 步即 BAILOUT（非 24 步预算耗尽）；事件含 `circuit.breaker` + `pi.no_progress` | PASS |
| `test_pi_fast_lane_never_trips_circuit_breaker` | fast 走自身 max_steps 预算，不产生 `circuit.breaker` | PASS |
| `test_pico_fast_and_deep_use_deepseek_v4_flash` | `/v1/models` 与 UI 仅两档；底层 model 合同一致 | PASS |

跑法：`python -m pytest tests/unit/test_provider_routing.py tests/unit/test_pi_runtime.py -q`
→ `27 passed`（含双档 + 熔断新增用例）。

## 结论

- 快速路径：更短、步骤更紧，适合交件和轻量任务。
- 深度路径：允许 longer reasoning；在无进展/空转时强制熔断，避免长挂与 OOM 导致的假绿。
- 熔断是深度档专属：`thinking_on=False`（快速档）永不触发，避免误伤短路径。
