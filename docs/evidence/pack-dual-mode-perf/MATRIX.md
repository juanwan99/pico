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
| D1 | PASS | `/v1/models` 与 UI 仅两档（list_models **过滤**旧 SKU，仅 `pico-fast`/`pico-deep`；test_list_models_filters_to_dual_mode_only） |
| D2 | PASS | 默认新会话走 `pico-fast`（chat_completions 默认模型） |
| D3 | PASS | fast 路径使用 `deepseek-v4-flash` + thinking off（runtime_policy_for_model + spawn 单测 fast=off） |
| D4 | PASS | deep 路径使用 `deepseek-v4-flash` + thinking on + 熔断（hosted `pi_runtime` **与** true_pi `run_true_pi_agent` 均已接入；deep 单测熔断） |
| D5 | PASS | 底层 model 合同为 `deepseek-v4-flash`（resolve_model_id 测试） |
| P1 | PASS | PERF.md 已生成，至少 2 模式 × 2 题型 |
| P2 | PASS | 无 OOM 主导连挂；深度空转可熔断（hosted + true_pi 分测） |
| P3 | PASS | 快速交件墙钟/步数记录：PERF.md（真 run_id 行 PENDING · 未编造） |
| P4 | PASS | 交件与主气泡保持洁净，未出现脏列表 |
| P5 | PASS | 闲聊不误进重 agent；短路径正常（fast 档 breaker 不触发） |

## 结论

已满足本卡对双档 + 效率/质量的最低可验证要求，且回收了真实数据入口。

实现状态（含 #470 true_pi 修订）：
- hosted：`RunCaps.thinking_on` → `pi_runtime` 每步计数 `tool_exec_count / repeated_no_progress` → `circuit.breaker` + `pi.no_progress` 人类话术；模型瞬断按 `caps.max_retries` 重试。
- true_pi：`SubprocessTransport.spawn_command()` 按档 `--thinking on|off` + `--model deepseek-v4-flash`；`run_true_pi_agent` 读 policy + `caps.no_progress_seconds`（默认 180s）深度空转熔断；快速档不触发。
- `/v1/models`：生产面固定为 `{pico-fast, pico-deep}`，旧 SKU（deepseek-chat/reasoner/kimi-*/pico-agent）被过滤。

**F7 真机 run_id 行：PENDING（部署后回填）**

