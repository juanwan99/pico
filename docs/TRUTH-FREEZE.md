# Pico 真源冻结（TRUTH-FREEZE）

```
DOC: docs/TRUTH-FREEZE.md
STATUS: BINDING FREEZE v1.0
FROZEN_AT: 2026-08-01
PURPOSE: 固定产品/架构真源，防止聊天与旧文档再次冲掉校准结论
AUTHORITY: 业主书面确认 + 本文件 + WHAT-IS-PICO；代码/PR 证据可更新「实现现状」，不可偷偷改「目标」
SUPERSEDES: 一切未列入本冻结集的冲突口述、过时 README 金句、archive 旧文
```

---

## 0. 怎么用（防丢失）

1. **新窗 / 总管 / 执行窗** 必读顺序：  
   `TRUTH-FREEZE` → `WHAT-IS-PICO` → `STATE-NOW` → `CORRECTED-GOALS` → `AGENTS.md` → 任务卡  
2. **改目标类句子**（产品是什么、编排唯一路径、禁项）= **升冻结小版本**（v1.1…）并走 PR，禁止只在聊天改口。  
3. **改实现现状**（生产 SHA、某门是否 PASS）= 更新 `STATE-NOW` + GitHub 证据；**不要**改写本文件的「目标」段。  
4. `docs/archive/**` = **历史**，默认 **非真源**。  
5. 进度真源永远是：**GitHub PR / exact SHA / CI / `## DEPLOYED` / `## TEST REPORT`**。

---

## 1. 冻结决策集 v1.0（目标 · 不可被执行窗改写）

### 1.1 产品是什么

| # | 冻结句 |
|---|--------|
| P1 | Pico = 学校向 **独立 AI 工作台底座**（对话 + 办事 + 产物 + 唯一 AI 账本 + 控制面） |
| P2 | **不是** 网盘 / 教务 SaaS / 成绩主库 / 自托管大模型默认 / 迷你 Codex |
| P3 | 用户成功 = 公网登录 → 下任务 → 过程可见 → 产物可用 → 能停、能找回、失败能再试 → 状态诚实 |
| P4 | 壳 = **`apps/librechat`（MIT）**；禁止回潮 web/nextchat/workbench；禁止拆闭源 WorkBuddy |
| P5 | 与 edu：Pico = **AI 过程真源**；edu-core = **业务事实真源**；对接后置；**禁止写 edu-cloud** |

### 1.2 架构四层

| # | 层 | 冻结选择 |
|---|-----|----------|
| A1 | 壳 | LibreChat |
| A2 | 控制面+账本 | 仅 Pico（Task/Run/Event/Artifact/Change…） |
| A3 | 编排运行时 | **唯一路径：开源 Kimi Agent 真接入**（钉版本薄改） |
| A4 | 模型 | **Kimi / Moonshot HTTPS API**（锁定优先；可兼容其它 provider 配置） |

### 1.3 编排名实（关键 · 防再假完成）

| # | 冻结句 |
|---|--------|
| O1 | **目标** = 开源 **Kimi Agent** 驱动多步；事件进入 Pico 账本 |
| O2 | **现状（至冻结日）** = 主路径仍为 **AsyncOpenAI 自研工具环**；kimi-cli/sdk 多为 pin + 读 yaml；**不得宣传已接入** |
| O3 | 自研环 = **TRANSITIONAL 债**；归位前 **禁止再扩「小 OS」能力** |
| O4 | **禁止预埋** Plan B / Pi / OpenCode 等其它运行时进真源；**走不通 → 停工交业主再议** |
| O5 | 刷新/历史/停止/重试 = **控制面与壳通路**，不得用来证明 O1 已完成 |

### 1.4 能力边界

| # | 做 | 不做（冻结期内默认） |
|---|----|----------------------|
| C1 | 日用可靠（刷新/历史/停止/重试通路） | 教师默认 **执行沙箱**（Codex 式） |
| C2 | 租户/membership 数据隔离 | 把数据隔离叫「每校执行沙箱」并当主线 |
| C3 | 公网 HTTPS 工作台 | 以 Live Preview 为业主主路径 |
| C4 | 公网分享若做：真链接 + **限时失效/可撤**（防违规长期挂网） | 万能 PaaS / 教师任意跑程序 |
| C5 | 受控业务自动化（提醒、开关链接等） | 默认开放 Host Shell/任意脚本 |
| C6 | S7：业务变更需确认 | AI 直接改正式成绩 |

### 1.5 协作与仓

| # | 冻结句 |
|---|--------|
| W1 | 只写 `juanwan99/pico` |
| W2 | 禁 PROXY=1；禁打印密钥 |
| W3 | 窗口 1/2/3 手动派卡；无自动触发当可靠机制 |
| W4 | 不自 PASS；DEPLOYED ≠ 产品 PASS |
| W5 | 计划法 MVP **v1.2 FIXED**；无授权不升 v1.3 |

### 1.6 多仓（只读认知 · 不写 edu）

```text
OneFlow  → 变化纪律
Pico     → AI 执行与账本
edu-core → 教育业务事实（RLS/租户隔离，非执行沙箱）
edu-cloud→ 现网服役/对账（非本仓工作区）
```

---

## 2. 冻结文档集（防丢失 · 权威序）

| 序 | 路径 | 角色 | 可改什么 |
|----|------|------|----------|
| **T0** | **[TRUTH-FREEZE.md](./TRUTH-FREEZE.md)**（本页） | 目标冻结清单 | 仅升版本 PR |
| **T1** | **[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)** | 产品定义 + 编排目标/现状 | 与 T0 冲突时以 T0 为准并回写 |
| **T2** | **[STATE-NOW.md](./STATE-NOW.md)** | 运行快照：SHA、门禁、派发 | 现状/SHA 常改 |
| **T3** | **[CORRECTED-GOALS.md](./CORRECTED-GOALS.md)** | 目标校正表 | 须与 T0/T1 一致 |
| **T4** | **[AGENTS.md](../AGENTS.md)** | 执行 HARD | 指针指向 T0–T3 |
| **T5** | **[DEBT-BACKLOG.md](./DEBT-BACKLOG.md)** | 债（含 D8 编排） | 可增行；不改 T0 目标 |
| **T6** | **[ONEFLOW.md](./ONEFLOW.md)** + **[SPRINT-FAST.md](./SPRINT-FAST.md)** | 交付纪律 | 流程，不改产品定义 |
| **T7** | **[ADR-SKILL-CATALOG.md](./ADR-SKILL-CATALOG.md)** | 技能唯一目录=LibreChat Skills | 保持 ACCEPTED A |

**非冻结（参考/历史，冲突丢弃）：**

- `docs/archive/**`（含旧 HANDOFF、UNDERLYING-AGENT 完成态话术）  
- 过期 `DAY-TASK-*`、已 COMPLETE 的 sprint 日记  
- 聊天、口头「完成」  

---

## 3. 污染源清单与处置（清理 · 第一刀文档）

| ID | 污染 | 处置（本 PR） |
|----|------|----------------|
| X1 | README 写「编排 \| 开源 Kimi Agent」像已完成 | **改为目标+现状指针** |
| X2 | ARCHITECTURE 写「Orchestration — Kimi Agent SDK/runtime」像已落地 | **改为目标；注明现状过渡环** |
| X3 | OVERALL-ARCHITECTURE 旧 DRAFT 易被当 FIXED | **文首加：从属于 T0/T1；编排见 TRUTH-FREEZE** |
| X4 | archive 旧文「已接入/驱动编排」 | **保持 archive；索引标明非真源** |
| X5 | 聊天 Plan B / Pi | **禁止回写真源**（T0 O4） |
| X6 | 自研环路径依赖 | **D8 路线 P0**；代码清理另窗，本 PR 只钉真源 |
| X7 | 执行沙箱/开发者 narrative 混进教师主路径 | **T0 C1：默认不做** |

**代码污染（登记，本 PR 不删业务代码）：**

- `services/orchestrator/pico_orchestrator/runner.py` 自研环 = 过渡执行器  
- `kimi-agent-sdk` / `kimi-cli` pin 而无主路径调用 = 装饰依赖（归位时处理）  

---

## 4. 实现现状指针（非目标 · 以免冻结日丢失上下文）

> 细节以 `STATE-NOW` + GitHub 为准；此处仅冻结日摘要。

| 项 | 冻结日摘要 |
|----|------------|
| 产品壳 | LibreChat 公网可登录 |
| 模型 | Kimi API 已用 |
| 编排 | **未归位**（自研环） |
| 日用 | 刷新/历史/停止等曾有验收；失败重跑曾卡代理类问题 → 以最新 TEST REPORT 为准 |
| 教师沙箱 | **不做** |
| 限时公网链接 | **方向已定**（合规）；实现可后 |

---

## 5. 版本

| 版本 | 日期 | 变更 |
|------|------|------|
| **v1.0** | 2026-08-01 | 首次冻结：产品/四层/编排唯一 Kimi Agent/禁 Plan B/禁教师执行沙箱/文档权威序/污染处置 |

升版规则：任何 P1–W5 / A1–A4 / O1–O5 / C1–C6 的修改 → **v1.x** 新 PR，标题含 `TRUTH-FREEZE`。
