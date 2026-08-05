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

**无 GitHub `## TEST REPORT` = 验证任务未交付**（禁止只停在本地窗口）。

**派工入口：** 总管只改 [`docs/VALIDATION-QUEUE.md`](./VALIDATION-QUEUE.md)；验证窗 heartbeat 只读该文件（见文内固定提示词），业主无需每次转贴。

## 3. 测试窗环境

优先顺序：

1. **生产**（经跳板 `pico-prod`，只读+演示账号操作）  
2. dev-ECS 本地栈（若有）  
3. 禁止：只 curl 首页 200 就报 PASS  

演示账号：`teacher@example.com` / 任务书给定；**禁止打印密钥**。

### 3.1 最小自动化测（R8 · host 可能无 py3.12）

仓库 `requires-python >= 3.12`。执行窗若只有 3.10：

```bash
# 一键：优先 python3.12 / .venv，否则 docker python:3.12-slim
bash scripts/run-min-tests.sh
# 与 CI 对齐：.github/workflows/ci.yml → setup-python 3.12 → pytest tests/unit + integration
```

Docker 镜像构建本身用 `python:3.12-slim`（`Dockerfile.pico-api`）。

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

## 6. 当前优先用例

新验证只从 `docs/VALIDATION-QUEUE.md` 的 `status: OPEN` 条目认领。
旧 Standalone A/B 用例已归档至
`docs/archive/completed-tasks-2026-07/TEST-TASK-AB-WORKSPACE.md`。

### P0 长任务刷新恢复

1. 发起一个持续时间超过 10 秒的任务，记录 `conversation_id` / `task_id` / `run_id`。
2. 在 **最新** Run 为 `queued` / `preparing` / `running` 时刷新页面，或从历史重新进入该会话。
3. 不再次发送消息；页面必须继续从 Pico 唯一账本轮询，最终显示与 Run 一致的
   `succeeded` / `failed` / `cancelled` 终态，并在产物稍晚落账时自动补齐。
4. 若同会话存在更新的终态 Task 与仍活跃的旧 Run，UI 应优先跟随仍活跃的 Run 直至终态
   （不得只因「列表最新 Task 已终态」而只做 4 次 tail 后停轮询）。
5. 若账本请求失败，页面显示可理解错误；不得以本地提交态冒充终态。
