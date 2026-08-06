# 测试任务 · P0 Pi+DeepSeek（单窗 SOLO 内点验）

```
TYPE: TEST
PAIR: docs/DAY-TASK-P0-PI-CUTOVER.md
EXEC: 同一 SOLO 执行窗（已登录 + 视觉 + 操控）
ISSUE: #310
MODE: 非独立「窗4编制」——职责别名 only
```

## 前置

- [ ] 本窗已完成装 tip，或 #310 已有 `## DEPLOYED`
- [ ] 已读 [MEMORY-RESET.md](./MEMORY-RESET.md)（禁场景卷假绿）

## 用例

| ID | 步骤 | PASS |
|----|------|------|
| PI-T1 | health `git_sha` = DEPLOYED SHA | 对齐 |
| PI-T2 | `default_runtime=pi-agent` 或 `pi_agent_runtime_enabled=true` | true |
| PI-T3 | `pi_agent_scope=all` | all |
| PI-T4 | `kimi_agent_runtime_enabled=false`（非应急） | false |
| PI-T5 | `legacy_loop_unavailable=true` | true |
| PI-T6 | 登录公网工作台 | 进壳 |
| PI-T7 | **开放域当场题**（禁 aivia 固定卷）。例：15 分钟年级会三点准备+议程提纲 | 非空回复 |
| PI-T8 | 过程或 run 状态可见；禁空成功 | 诚实 |
| PI-T9 | 停止：cancelled/stopped 或 N/A+说明 | OK/N/A |
| PI-T10 | 失败则 user_message 可读 | 诚实 |
| PI-T11 | 能取则 `runtime=pi-agent`（run_id，勿贴 key） | pi-agent |
| PI-T12 | 18765/27017 不公网裸露 | 关 |

## 报告（贴 #310）

```text
## TEST REPORT
PAIR: DAY-TASK-P0-PI-CUTOVER
MODE: SOLO
SHA: <health.git_sha>
日期:

| ID | 结果 | 备注 |
|----|------|------|
| PI-T1 | PASS/FAIL | |
| PI-T2 | | |
| PI-T3 | | |
| PI-T4 | | |
| PI-T5 | | |
| PI-T6 | | |
| PI-T7 | | 题干摘要： |
| PI-T8 | | |
| PI-T9 | | |
| PI-T10 | | |
| PI-T11 | | run_id= |
| PI-T12 | | |

三行:
SHA: …
chat: OK/FAIL · runtime=pi-agent · model=deepseek-*
stop: OK/FAIL/N/A

verdict: PASS / FAIL
CLAIM-WB-DEGREE-WEB: NO
```

verdict PASS ≠ 六条完成。
