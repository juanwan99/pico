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

## 真机对照（待部署后以 run_id 回填 · 禁止编造墙钟）

> **诚实声明（F7）**：以下「样例记录」为部署前预估/回归推导，**不是**公网 run_id
> 真值。按 #470 要求，编造墙钟不得充当 Ready 证据；部署 + 类人验收后以真 run_id
> 行替换本表。真值列占位如下（PENDING）：

| 模式 | 题型 | wall_s | steps | tool_exec | art | oom | settle | run_id | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---|:---:|
| pico-fast | C1-HTML 交件 | – | – | – | – | – | – | PENDING | 待部署 |
| pico-deep | hard-reasoning | – | – | – | – | – | – | PENDING | 待部署 |
| pico-deep | idle/no-progress | – | – | – | – | – | – | PENDING | 待部署 |

## 回归证据（tests/unit，2026-08-12 · 含 #470 true_pi 修订）

| 用例 | 断言 | 结果 |
|------|------|:---:|
| `test_runtime_policy_dual_mode_contract` | fast/deep 均钉 `deepseek-v4-flash`；thinking 相反；预算 fast<deep | PASS |
| `test_circuit_breaker_only_in_thinking_on_lane` | fast 永不熔断；deep 空转/长挂/重挂熔断；有进展不熔断 | PASS |
| `test_pi_deep_lane_circuit_breaker_bails_on_no_progress` | hosted deep 空转 ≤6 步即 BAILOUT；事件含 `circuit.breaker` + `pi.no_progress` | PASS |
| `test_pi_fast_lane_never_trips_circuit_breaker` | hosted fast 不产生 `circuit.breaker` | PASS |
| `test_spawn_command_fast_lane_thinking_off` | true_pi spawn `--thinking off` · `--model deepseek-v4-flash` | PASS |
| `test_spawn_command_deep_lane_thinking_on` | true_pi spawn `--thinking on` · `--model deepseek-v4-flash` | PASS |
| `test_true_pi_deep_lane_breaker_bails_on_no_tool_progress` | true_pi deep 空转 ≥180s（测试注入 1s）→ `circuit.breaker` + `pi.no_progress` | PASS |
| `test_true_pi_fast_lane_never_trips_breaker` | true_pi fast 不产生 `circuit.breaker` | PASS |
| `test_list_models_filters_to_dual_mode_only` | `/v1/models` 仅 `pico-fast`/`pico-deep`（旧 SKU 被过滤） | PASS |
| `test_pico_fast_and_deep_use_deepseek_v4_flash` | 底层 model 合同一致 | PASS |

跑法：`python -m pytest tests/unit/test_provider_routing.py tests/unit/test_pi_runtime.py tests/unit/test_true_pi_dual_mode.py -q`
→ 全量 `tests/unit` = `321 passed, 4 skipped` · `tests/integration` = `39 passed, 1 skipped`。

## 结论

- 快速路径：更短、步骤更紧，适合交件和轻量任务。
- 深度路径：允许 longer reasoning；在无进展/空转时强制熔断（hosted 与 true_pi 均已接入），避免长挂与 OOM 导致的假绿。
- 熔断是深度档专属：`thinking_on=False`（快速档）永不触发，避免误伤短路径。
- **F7 真 run_id 行：PENDING（部署后回填）** —— 未编造墙钟充当 Ready。
