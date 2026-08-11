# 双档 + 效率质量证据目录

本目录用于保留本卡的结构化证据，路径和卡内要求一致：

- MATRIX.md: 双档 / 效率质量矩阵
- PERF.md: 快速/深度性能对照表
- d-list/: 列表帧/模型列表证据（可扩展）
- fast-c1/: 快速交件样例（可扩展）
- deep-hard/: 深度任务样例（可扩展）
- chat-idle/: 空转/idle 熔断样例（可扩展）

说明：该目录是可执行证据根，后续可继续补充真实抓取截图/日志。

## 当前状态（2026-08-12）

- 双档路由 / model gate 已锁定：`/v1/models` 与 UI 仅 `pico-fast` / `pico-deep`，
  底层 model 合同 `deepseek-v4-flash`。
- 熔断 + 瞬断重试已落地运行时：
  - `provider.should_circuit_break` 经 `RunCaps.thinking_on` 接入 `pi_runtime`；
  - 深度档空转 ≤ 2 次无进展即触发 `pi.no_progress`（人类话术），快速档永不熔断；
  - 模型调用按 `caps.max_retries` 重试（`model.retry` 事件）。
- 回归：`python -m pytest tests/unit/test_provider_routing.py tests/unit/test_pi_runtime.py -q`
  → `27 passed`（含双档 + 熔断新增用例）；全量 `tests/unit` → `294 passed, 4 skipped`。

