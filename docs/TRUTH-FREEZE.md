# Pico 真源冻结（TRUTH-FREEZE）

```
DOC: docs/TRUTH-FREEZE.md
STATUS: BINDING FREEZE v1.1
FROZEN_AT: 2026-08-06
PURPOSE: 固定产品/架构真源，防止聊天与旧文档再次冲掉校准结论
AUTHORITY: 业主书面确认 + HANDOFF-WB-PI + 本文件 + WHAT-IS-PICO；代码/PR 证据可更新「实现现状」，不可偷偷改「目标」
SUPERSEDES: v1.0「唯一编排 = Kimi Agent / 禁 Pi」；多窗日常碎派；一切未列入本冻结集的冲突口述、过时 README 金句、archive 旧文
RELATED: docs/HANDOFF-WB-PI.md → docs/MEMORY-RESET.md（产品目标权威）
```

---

## 0. 怎么用（防丢失）

1. **新窗 / 总管 / 执行窗（默认单窗 SOLO）** 必读顺序：  
   `HANDOFF-WB-PI` → `TRUTH-FREEZE` → `WHAT-IS-PICO` → `STATE-NOW` → `AGENTS.md` → 任务卡  
2. **改目标类句子**（产品是什么、编排唯一路径、禁项）= **升冻结小版本**（v1.2…）并走 PR，禁止只在聊天改口。  
3. **改实现现状**（生产 SHA、某门是否 PASS）= 更新 `STATE-NOW` + GitHub 证据；**不要**改写本文件的「目标」段。  
4. `docs/archive/**` = **历史**，默认 **非真源**。  
5. 进度真源永远是：**GitHub PR / exact SHA / CI / `## DEPLOYED` / `## TEST REPORT`**。

---

## 1. 冻结决策集 v1.1（目标 · 不可被执行窗改写）

### 1.1 产品是什么

| # | 冻结句 |
|---|--------|
| P1 | Pico = **任务型 AI 工作台（Web）** 底座（对话 + 办事 + 产物 + 唯一 AI 账本 + 控制面）；类 WorkBuddy 程度（六条） |
| P2 | **不是** 网盘 / 教务 SaaS / 成绩主库 / 自托管大模型默认 / Dify 门脸终局 / 场景考卷对标 |
| P3 | 用户成功 = 公网登录 → 开放派活 → 多步过程可见 → 真产物 → 能停、能找回、同会话可改 → 状态诚实 |
| P4 | 壳 = **`apps/librechat`（MIT）**；禁止回潮 web/nextchat/workbench；禁止拆闭源 WorkBuddy |
| P5 | 与 edu：Pico = **AI 过程真源**；edu-core = **业务事实真源**；对接后置；**禁止写 edu-cloud**；**禁止 Agent 写成绩/教务库** |

### 1.2 架构四层

| # | 层 | 冻结选择 |
|---|-----|----------|
| A1 | 壳 | LibreChat |
| A2 | 控制面+账本 | 仅 Pico（Task/Run/Event/Artifact/Change…） |
| A3 | 编排运行时 | **默认唯一：Pi Agent harness**（`pico_orchestrator.pi_runtime`） |
| A4 | 模型 | **DeepSeek HTTPS API 为主**（`DEEPSEEK_*`）；Kimi 可选后备密钥 |

### 1.3 编排名实（关键）

| # | 冻结句 |
|---|--------|
| O1 | **目标（默认唯一）** = **Pi** 驱动多步工具环；事件进入 Pico 账本。 |
| O2 | **模型** = **DeepSeek** 为主；产品对外脑力不以 Kimi 为叙事。 |
| O3 | `run_agent_loop` = **已移除**（KA-4 HARD）；**禁止**复活为产品目标。 |
| O4 | **Kimi Agent** = **遗产/可选回滚**（`PICO_LEGACY_KIMI_AGENT_RUNTIME`），**不再**产品唯一目标。 |
| O5 | **禁止双核并列真源**（Pi + Reasonix + Kimi 同时「官方唯一」）。默认只钉 Pi。 |
| O6 | Reasonix 等实验须 flag，不得写「唯一目标」。 |
| O7 | 刷新/历史/停止/重试 = **控制面与壳通路**，不得单独用来证明 O1 已完成。 |

### 1.4 能力边界

| # | 做 | 不做（冻结期内默认） |
|---|----|----------------------|
| C1 | 日用可靠（刷新/历史/停止/重试通路） | 教师默认 **执行沙箱**（Codex 式） |
| C2 | 租户/membership 数据隔离 | 把数据隔离叫「每校执行沙箱」并当主线 |
| C3 | 公网 HTTPS 工作台 | 以 Live Preview 为业主主路径 |
| C4 | Skill 前台可见可选（分期） | 自研 MCP 协议栈 / 自研向量库内核 |
| C5 | MCP / KB = 接入现成组件（分期） | 默认开放 Host Shell/任意脚本 |
| C6 | S7：业务变更需确认 | AI 直接改正式成绩 |
| C7 | WorkBuddy **Web 六条** | 桌面 exe / 像素 1:1 / 固定场景考卷冒充完成 |

### 1.5 协作与仓

| # | 冻结句 |
|---|--------|
| W1 | 只写 `juanwan99/pico`（产品主仓） |
| W2 | 禁 PROXY=1；禁打印密钥 |
| W3 | **单窗 SOLO** 端到端（STAGE-PACKAGE）；旧窗1/2/4 仅职责别名；无自动 E1 派工 |
| W4 | 不自 PASS；DEPLOYED ≠ 产品 PASS；禁假绿 CLAIM |
| W5 | aivia-workbench = 非产品主仓；Dify/场景卷 ≠ WB 程度完成 |

### 1.6 多仓（只读认知 · 不写 edu）

```text
Pico     → 产品主仓 · AI 执行与账本 · 门脸
aivia    → 过渡参考/水管（已降级）
edu-core → 教育业务事实（后置）
edu-cloud→ 现网服役/对账（非本仓工作区）
```

---

## 2. 冻结文档集（防丢失 · 权威序）

| 序 | 路径 | 角色 |
|----|------|------|
| **T0** | **HANDOFF-WB-PI.md** | 产品目标与六条（2026-08-06 业主拍板） |
| **T1** | **TRUTH-FREEZE.md**（本页） | 目标冻结清单 |
| **T2** | **WHAT-IS-PICO.md** | 产品定义 |
| **T3** | **STATE-NOW.md** | 运行快照：SHA、门禁、派发 |
| **T4** | **AGENTS.md** | 执行 HARD |

---

## 3. 相对 v1.0 的变更（本版）

| 旧 v1.0 | 新 v1.1 |
|---------|---------|
| 唯一编排 = 开源 Kimi Agent | **默认 = Pi** |
| 禁止预埋 Pi | **作废**；Pi 升为默认核 |
| 模型 Kimi 优先 | **DeepSeek 主模型** |
| 编排 ENGINEERING = Kimi 故事 | **产品故事 = Pi + DeepSeek**；Kimi = 回滚 |

---

## 4. 实现现状指针（非目标）

> 细节以 `STATE-NOW` + GitHub 为准。

| 项 | 摘要 |
|----|------|
| 编排默认 | Pi（`PICO_PI_AGENT_RUNTIME=1` 默认） |
| 模型默认 | DeepSeek 优先 resolve |
| 遗产 | Kimi Agent 模块仍在仓内，flag 开启才走 |
| 自研环 | 仍删除；不得回流 |

---

## 5. 版本

| 版本 | 日期 | 变更 |
|------|------|------|
| **v1.0** | 2026-08-01 | 首次冻结：Kimi Agent 唯一 / 禁 Pi |
| **v1.1** | 2026-08-06 | 对齐 HANDOFF-WB-PI：默认 Pi + DeepSeek；Kimi 遗产回滚；禁双核真源；**单窗 SOLO**（废多窗日常派） |

升版规则：任何 P1–W5 / A1–A4 / O1–O7 / C1–C7 的修改 → **v1.x** 新 PR，标题含 `TRUTH-FREEZE`。
