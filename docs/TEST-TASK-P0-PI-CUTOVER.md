# 测试任务 · P0 Pi+DeepSeek 落地

```
TYPE: TEST
PAIR: docs/DAY-TASK-P0-PI-CUTOVER.md
EXEC: 窗4 · 验证（已登录 + 视觉 + 操控网页）
ISSUE: #310
```

## 前置

- [ ] #310 有 `## DEPLOYED` 且 SHA 已知
- [ ] 公网工作台可登录（凭据走密码器，不写本文件）

## 用例（部署后）

| ID | 步骤 | PASS |
|----|------|------|
| PI-T1 | loopback 或登录后 health：`git_sha` = DEPLOYED SHA | 对齐 |
| PI-T2 | health：`default_runtime=pi-agent` **或** `pi_agent_runtime_enabled=true` | true |
| PI-T3 | health：`pi_agent_scope=all` | all |
| PI-T4 | health：`kimi_agent_runtime_enabled=false`（非应急回滚） | false |
| PI-T5 | health：`legacy_loop_unavailable=true` | true |
| PI-T6 | 登录公网工作台 | 进壳 |
| PI-T7 | **开放域当场题**（禁止背固定 G/C/U 卷）。例：「用三条要点说明今天如何准备一场 15 分钟年级会，并给可复制议程提纲。」 | 有非空回复 |
| PI-T8 | 过程可见：step / tool / run 状态至少一类；或诚实短答+终态 | 不假绿 |
| PI-T9 | 点「停止」：不再狂奔；终态 cancelled/stopped 诚实（若当次已结束则记 N/A+说明） | OK/N/A |
| PI-T10 | 若失败：`user_message` 可读，不装成功 | 诚实 |
| PI-T11 | 能取则核对事件/run：`runtime=pi-agent`（贴 run_id，勿贴 key） | pi-agent |
| PI-T12 | 端口抽查：18765/27017 不公网裸露 | 关 |

## 开放域题规则

- 当场拟题，可换题，**禁止** aivia 固定场景卷当对标
- 短答可不强塞文件；**禁止空成功**

## 报告（贴 #310）

```text
## TEST REPORT
PAIR: DAY-TASK-P0-PI-CUTOVER
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

**verdict PASS** 仅表示 P0 落地可继续；**≠** WorkBuddy 六条完成。
