# 测试任务 · T-P2-EXTEND

```
TYPE: TEST
PAIR: T-P2-EXTEND · docs/DAY-TASK-P2-EXTEND.md
EXEC: SOLO 执行窗内点验
MODE: 开放域 + 真 UI；禁 aivia 固定卷冒充
```

## 前置

- [ ] ## DEPLOYED 且 `default_runtime=pi-agent`
- [ ] 已登录公网工作台

## 用例

| ID | 步骤 | PASS |
|----|------|------|
| P2-T1 | health.git_sha = DEPLOYED tip | 对齐 |
| P2-T2 | default_runtime=pi-agent · scope=all · kimi off | 不回退 |
| P2-T3 | 登录工作台 | 进壳 |
| P2-T4 | **KB**：挂载/选择至少 1 份材料后提问（当场拟题） | 有答复 |
| P2-T5 | 答复含依据/摘录 **或** 诚实未命中（不装全库命中） | 诚实 |
| P2-T6 | **MCP**：白名单工具 ≥1 可触发（列表可见或 run 内 tool） | 可点/可调 |
| P2-T7 | ledger：`tool.call`/`tool.result` 有记录；runtime=pi-agent | 可审计 |
| P2-T8 | 第二 MCP 若宣称则同 T6–T7；若只做 1 个则 N/A+说明 | n=1 或 2 |
| P2-T9 | 手感：长任务可见进行中/心跳文案（或等价） | 不假死 |
| P2-T10 | 失败路径 user_message 中文可读（可造一小错） | 诚实 |
| P2-T11 | **回归**：取消仍可用 | OK |
| P2-T12 | **回归**：产物可下或 ≥3 Skill 入口仍在（抽 1） | 不回退 P1 |
| P2-T13 | 18765/27017 不公网裸露 | 关 |

## 报告（贴载体 Issue）

```text
## TEST REPORT
PAIR: T-P2-EXTEND
MODE: SOLO
SHA:
日期:

| ID | 结果 | 备注 |
|----|------|------|
| P2-T1 | | |
| P2-T2 | | |
| P2-T3 | | |
| P2-T4 | | 材料摘要： |
| P2-T5 | | |
| P2-T6 | | mcp/tool= |
| P2-T7 | | run_id= |
| P2-T8 | | n= |
| P2-T9 | | |
| P2-T10 | | |
| P2-T11 | | |
| P2-T12 | | |
| P2-T13 | | |

三行:
SHA: …
kb: OK/FAIL · mcp: n= · handfeel: OK/FAIL
stop: OK/FAIL/N/A

verdict: PASS / FAIL
CLAIM-WB-DEGREE-WEB: NO
```
