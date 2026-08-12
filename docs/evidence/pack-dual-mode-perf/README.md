# 双档 + 效率质量证据目录

本目录用于保留本卡的结构化证据，路径和卡内要求一致：

- MATRIX.md: 双档 / 效率质量矩阵
- PERF.md: 快速/深度性能对照表
- d-list/: 列表帧/模型列表证据（可扩展）
- fast-c1/: 快速交件样例（可扩展）
- deep-hard/: 深度任务样例（可扩展）
- chat-idle/: 空转/idle 熔断样例（可扩展）

说明：该目录是可执行证据根，后续可继续补充真实抓取截图/日志。

## 当前状态（2026-08-12 · 含 #470 true_pi 修订）

- 双档路由 / model gate 已锁定：`/v1/models` 与 UI 仅 `pico-fast` / `pico-deep`
  （**过滤**旧 SKU），底层 model 合同 `deepseek-v4-flash`。
- 熔断 + 瞬断重试已落地 **hosted + true_pi 双运行时**：
  - hosted：`provider.should_circuit_break` 经 `RunCaps.thinking_on` 接入 `pi_runtime`；
  - true_pi：`SubprocessTransport.spawn_command()` 按档 `--thinking on|off` +
    `--model deepseek-v4-flash`；`run_true_pi_agent` 读 policy +
    `caps.no_progress_seconds`（默认 180s）深度空转熔断；
  - 深度档无进展即触发 `pi.no_progress`（人类话术），快速档永不熔断；
  - 模型调用按 `caps.max_retries` 重试（`model.retry` 事件）。
- 回归：`python -m pytest tests/unit -q` → `321 passed, 4 skipped`；
  `tests/integration` → `39 passed, 1 skipped`。
- F7：PERF 真 run_id 行 PENDING（部署后回填）—— 未编造墙钟充当 Ready。

