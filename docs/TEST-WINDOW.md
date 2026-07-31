# 测试窗（独立验收 · 与写入分离）

```
DOC: docs/TEST-WINDOW.md
STATUS: BINDING
DATE: 2026-07-30
PAIRS: docs/RACI-GROK-CODEX.md · docs/ONEFLOW.md
```

## 1. 为什么要有

**仅有代码 PR / CI 绿 ≠ 用户可用。**  
写入窗负责实现；**测试窗**负责在真实（或准真实）环境做 **行为验证** 并把结果写回 GitHub。

| 角色 | 做 | 不做 |
|------|-----|------|
| **写入** | 实现、单测、PR、CANDIDATE | 不自签「产品可用」 |
| **测试** | 按用例真跑、截图/日志、**TEST REPORT** | 大改业务（小热修可另开写入 PR） |
| **总管** | 派任务时 **必带测试验收**；审代码+审测试报告后合/收口 | 用聊天代替测试报告 |

## 2. 总管派工硬规则

以后 **每个功能派工** 必须包含：

1. **实现任务书**（写入 · 可多轨）  
2. **测试任务书**（测试窗 · 可与实现并行准备，**合 main 或部署后必跑**）  
3. 完成定义里写清：`CODE` / `TEST` / `DEPLOY` 三态  

无测试反馈 → **不得**宣布切片完成或写假 DEPLOYED。

## 3. 测试窗环境

优先顺序：

1. **生产**（经跳板 `pico-prod`，只读+演示账号操作）  
2. dev-ECS 本地栈（若有）  
3. 禁止：只 curl 首页 200 就报 PASS  

演示账号：`teacher@example.com` / 任务书给定；**禁止打印密钥**。

## 4. 标准 TEST REPORT（贴 PR 或 Issue）

```text
## TEST REPORT
- task: （任务书路径或 Issue）
- env: production | dev-ecs | other
- against SHA: （health.git_sha 或 main）
- cases:
  - [ ] case_id: PASS|FAIL|BLOCKED — 简述 + 证据
- regressions: 登录/真聊/S7/下载/端口
- blockers:
- verdict: PASS | FAIL | BLOCKED
- 声明: 未写 edu-cloud · 未 PROXY=1 · 未打印 key · 非写入自测冒充
```

FAIL → 总管开 **修复写入任务**，测试窗 **复测** 闭环。

## 5. 与 OneFlow 关系

- CI 绿 = 机器门禁  
- **TEST REPORT PASS** = 行为门禁（人/脚本在真环境）  
- DEPLOYED = 生产 SHA + **关键用例 TEST 过**（或明确 BLOCKED 原因）

## 6. 当前优先用例（Standalone A/B）

见 `docs/TEST-TASK-AB-WORKSPACE.md`（随本变更入库）。
