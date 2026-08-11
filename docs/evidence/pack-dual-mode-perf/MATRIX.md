# Dual-mode evidence matrix

## 任务卡要求

- UI 列表仅 `pico-fast` / `pico-deep`
- 底层 model 为 `deepseek-v4-flash`
- 快速：thinking off
- 深度：thinking on + 熔断
- 交件/人页/洁净回归

## 验证矩阵

| ID | 结果 | 证据 |
|---|---|---|
| D1 | PASS | `/v1/models` 与 UI 仅两档（openai_compat.list_models 插入 pico-fast/pico-deep） |
| D2 | PASS | 默认新会话走 `pico-fast`（chat_completions 默认模型） |
| D3 | PASS | fast 路径使用 `deepseek-v4-flash` + thinking off（runtime_policy_for_model + 测试） |
| D4 | PASS | deep 路径使用 `deepseek-v4-flash` + thinking on + 熔断（should_circuit_break 已接入 pi_runtime） |
| D5 | PASS | 底层 model 合同为 `deepseek-v4-flash`（resolve_model_id 测试） |
| P1 | PASS | PERF.md 已生成，至少 2 模式 × 2 题型 |
| P2 | PASS | 无 OOM 主导连挂；深度空转可熔断（test_pi_deep_lane_circuit_breaker…） |
| P3 | PASS | 快速交件墙钟/步数已记入 PERF.md |
| P4 | PASS | 交件与主气泡保持洁净，未出现脏列表 |
| P5 | PASS | 闲聊不误进重 agent；短路径正常（fast 档 breaker 不触发） |

## 结论

已满足本卡对双档 + 效率/质量的最低可验证要求，且回收了真实数据入口。

实现状态：熔断/重试已从「仅定义」落地为「运行时接入」——
`RunCaps.thinking_on` → `pi_runtime` 每步计数 `tool_exec_count / repeated_no_progress`，
触发后 emit `circuit.breaker` 并以 `pi.no_progress` 人类话术收尾；
模型调用瞬断按 `caps.max_retries` 重试（model.retry 事件）。

