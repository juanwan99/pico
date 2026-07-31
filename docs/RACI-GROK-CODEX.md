**Execution queue:** [docs/EXECUTION-QUEUE.md](docs/EXECUTION-QUEUE.md)

# 总控（Grok）× 执行（Codex）工作流

```
DOC: docs/RACI-GROK-CODEX.md
STATUS: BINDING
FAST: docs/SPRINT-FAST.md（7 日黄档代合 · 见该文 END）
DATE: 2026-07-30
TRUTH: GitHub PR/SHA/CI/DEPLOYED（OneFlow）
PAIRS: docs/ONEFLOW.md（角色名以 ONEFLOW 为准；本文件是映射与派工细则）
REVISE: Codex 审查 PR#52 意见已吸收
```

## 0. 与 ONEFLOW 角色映射（消除冲突）

ONEFLOW 三角色 **不变**：`总管` · `写入` · `审查`。

| ONEFLOW 角色 | 默认由谁扮演 | 说明 |
|--------------|--------------|------|
| **总管** | **Grok 总控**（对话侧规划/门禁会话） | 拆解、派工、**合 main 门禁**、节奏；可点名他人代总管 |
| **写入** | **Codex 执行窗**（常云端，有 VPS/浏览器） | 实现、测、PR、CANDIDATE、**部署回写** |
| **审查** | **未写入该 SHA 的会话** | 默认由 **Grok 总控**只读审；或另一 Codex/只读窗。写入者 **禁止**自审自合 |

历史文案里的「网页 Codex 总管 / Grok-Pico写入」= 旧双轨命名；**新默认以上表为准**。  
若某窗 Grok 亲自写入代码，则该 SHA 的 **审查** 必须换人（另一上下文），且 **合 main 仍走总管职责**（可业主代合）。

**禁止：** 同一上下文既当写入又给自己写 PASS 再合 main。

---

## 1. 职责边界

| 角色 | 做 | 不做 |
|------|-----|------|
| **总管（Grok）** | 优先级、任务书入库、lease/并行轨、审查、**CI 绿后合 main**、宣布下一切 | 默认不写生产热更；不把实现细节甩给业主；不自 PASS 产品终局 |
| **写入（Codex）** | 按任务书实现、测、开 PR、CANDIDATE、修 CI、**总管合入后**部署、DEPLOYED | 不写 edu-cloud；不自审 PASS；**默认不合自己的功能 PR**；不升 v1.3 无授权 |
| **审查** | exact SHA → PASS/REVISE/BLOCKED | 写业务代码；审移动 tip |
| **测试** | **独立测试窗**（业主已开专用窗） | 真环境用例、## TEST REPORT、FAIL 复测 | 冒充写入大改；用 CI 代替行为验收 |
| **业主** | 拍板、M5 授权、开 Codex/测试窗、必要时代合 | 不负责实现细节 |

**规划默认：** 写入有服务器与浏览器；总管与写入 **不共享沙箱**。

---

## 1.1 交接信道（硬：只走 GitHub）

| 允许 | 禁止 |
|------|------|
| Issue / PR 正文与评论 | 仅聊天长文当任务真源 |
| `## CANDIDATE` / `## DEPLOYED` / 审查结论评论 | HANDOFF.md 当进度库 |
| main SHA、Actions | 「好了」无 PR |
| 任务书在 **main docs/** 或 **Issue/PR** | 只存在于对话草稿 |

---

## 1.2 标准环（顺序硬 · 禁止颠倒）

```text
[1] 总管：任务书 → 合入 main 的 docs/ 或 GitHub Issue/PR 正文
       （验收、HARD、lease、日间/夜间、并行轨）

[2] 业主：新 Codex 窗只给 GitHub 指针（路径/Issue 号）+「执行」

[3] 写入（Codex）：分支实现 → 开 PR → ## CANDIDATE + 40字 SHA
       → 修到 CI 绿（红禁止进入合并）

[3b] 测试窗：按任务书用例真跑（可与 CI 并行准备；**合并后/部署后必出 ## TEST REPORT**）
       FAIL → 回写入修复 → 复测（不得跳过）

[4] 审查：只读 exact SHA + 必要时对照 TEST → 评论 PASS | REVISE | BLOCKED
       （REVISE → 回 [3]；BLOCKED → 总管改派）

[5] 总管：确认 CI 绿 +（黄/红风险时）审查 PASS → **合并 PR 入 main**
       写入默认不点 Merge；仅当总管在任务书/评论写明
       「授权写入合 main（限绿/文档）」时例外

[6] 写入：pull main → 生产部署（若动运行时）→ ## DEPLOYED + health.git_sha

[7] 总管：核对 GitHub 证据 → 下一任务书入库
```

**禁止的错误顺序：** 写入先合 main / 先部署，总管事后再审查。  
**允许的并行：** 审查可与写入修 CI 交错，但 **Merge 必须在审查结论之后**（绿低风险文档 PR 可由总管在任务书声明「免独立审」）。

风险与合并门禁细节以 `docs/ONEFLOW.md` §5–6 为准；本文件不降级那些门禁。

---

## 1.3 合 main 权责（唯一说法）

| 风险（见 ONEFLOW） | 谁合 main | 前置 |
|--------------------|-----------|------|
| 绿（文档/注释/测） | **总管**（或总管书面授权写入代合） | CI 绿 |
| 黄 | **总管** | CI 绿 + 独立审查 PASS 同 SHA |
| 红 | **总管** + 业主红例外（若需要） | CI 绿 + 审查 PASS + 红例外记录 |

写入 **永不** 在无总管授权时合并 **自己的** 黄/红 PR。
**例外：** `docs/SPRINT-FAST.md` 生效期内，**黄档**可由 ② 代合（须 CI 绿 + FAST 标记）；**红档仍禁止自合。**

---


## 1.4 任务完成 = GitHub 回写（硬 · 禁止静默停工）

执行窗 / 验证窗 **不得**「做完只停在本地/聊天」。无回写 = **任务未完成**。

| 角色 | 必须回写到 GitHub | 最少内容 |
|------|-------------------|----------|
| ② 执行 | 开 PR 或在任务 PR 评论 | `## CANDIDATE` / 进度 / BLOCKED 原因 / `## DEPLOYED` |
| ③ 验证 | 实现 PR 或测试 Issue 评论 | `## TEST REPORT`（PASS/FAIL/BLOCKED） |
| ① 总管 | PR 评论 | `## REVIEW` · 合 main 记录 |

**停工规则：**

- 进行中超过约定节奏：至少每阶段一条 **进度评论**（不必等完美）
- 卡住：必须 `## BLOCKED` + 缺什么（SSH/密钥/依赖）+ 已尝试
- 做完：必须 CANDIDATE 或 TEST REPORT，**禁止**只说「好了」在聊天
- 总管派工文案必须含一句：**「完成以 GitHub 回写为准；无评论视为未交付」**

## 2. 日间任务

- 称呼：**任务书 / 派工**（不叫夜卡）。  
- 体量：单窗约 **0.5～2h**；更大则拆或「加厚日间」。  
- 交付：PR + CI +（运行时）DEPLOYED。  
- 模板：`docs/templates/DAY-TASK-ISSUE.md`

### 2.1 日间并行（能并行则并行）

| 原则 | 说明 |
|------|------|
| 默认并行 | 多 Codex 窗 / 多 PR |
| lease | 每轨可写/禁止路径；共享文件单写或 WAIT |
| 合流最少 | principal / Task / Change / 发布 |
| 总控自并行 | 审查、法条、不撞 lease 小 PR |
| 不假并行 | 同文件双写 → 总管改串行并说明 |

分支/rebase 规则见 §6。

---

## 3. 夜间长任务（打满约 6h）

| 要求 | 统一口径（以本表为准） |
|------|------------------------|
| **目标工时** | 设计负载 **约 6h** 有效工作 |
| **结构** | **1 主目标 + ≥3 强制加厚包** + **储备包**（主包提前完成则继续储备，避免早停） |
| **停工** | 强制包全完成（或逐项 BLOCKED+原因）**且** 已尝试储备包或 hours≈6；禁止最小闭环交卷 |
| **与 NIGHT-CARD-POLICY** | POLICY 中旧「≥3h 或先完成先停」**废止**；以本表 + 更新后 POLICY 为准 |
| **风险** | 须含可控风险包；PR 写 `RISK:` |
| **部署** | 动运行时 → 总管合 main 后写入 DEPLOYED |
| **HARD** | 只 pico；禁写 edu-cloud；禁 PROXY=1；禁公网 18765/27017/8080；禁打印 key |

---

## 4. 总管发任务前自检

```text
□ 任务书已在 GitHub（云端 Codex 仅 git/Issue 可取）
□ 日间 vs 夜间已标明
□ 日间：并行轨 + lease 或串行原因
□ 夜间：约 6h 负载 + ≥3 强制包 + 储备包 + 风险包
□ 合 main 权责指向 §1.3（总管合）
□ 环顺序为 实现→CANDIDATE→CI→审查→合并→部署
□ HARD / 非目标写清
□ 是否附带测试窗任务与 ## TEST REPORT 要求？
□ 是否写明「无 GitHub 回写 = 未交付」？
```

---

## 5. 模板与证据

| 模板 | 路径 |
|------|------|
| 日间任务 Issue | `docs/templates/DAY-TASK-ISSUE.md` |
| 审查评论 | `docs/templates/REVIEW-COMMENT.md` |
| 写入交卷评论 | `docs/templates/CANDIDATE-DEPLOYED.md` |

阶段 A 生产证据仍为 **写入手工 DEPLOYED + health SHA**（非 Actions 独占发布）。  
总管验收以 GitHub 评论与可复查命令输出为准；**阶段 B** 再做自动门禁（见 ONEFLOW），本阶段不假装已自动化。

---

## 6. 多窗分支 / rebase / lease

| 规则 | 说明 |
|------|------|
| 分支名 | `grok/pico-<track>-<topic>` 或 `codex/<track>-<topic>` |
| 一窗一主分支 | 禁止两窗推同一分支 tip |
| 开写前 | `git fetch && rebase/merge origin/main` |
| lease | 任务书写 `LEASES: path=track`；共享文件写 `SINGLE_WRITER=track@window` |
| 冲突 | 后到者 WAIT 或总管改派；禁止强推覆盖他窗 |
| PR | 针对 main；落后 main 先 rebase 再要审查 |
| 审查绑定 | 评论必须绑 **完整 40 字 SHA**；tip 一动须重审 |

---

## 7. 相关文档

- `docs/ONEFLOW.md` — 门禁与风险等级权威  
- `docs/NIGHT-CARD-POLICY.md` — 夜间加厚（已与 §3 对齐）  
- `docs/PARALLEL-SPRINT-PLAN.md` — 产品并行轨  
- `docs/README.md` — 索引

- `docs/DEPLOY-TWO-HOST.md` — 写代码 ECS 跳板部署生产

- `docs/TEST-WINDOW.md` — 独立测试窗与派工必带测试
