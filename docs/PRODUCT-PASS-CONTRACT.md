# 全球 product PASS 合同（历史定义 · 状态作废）

```
DOC: docs/PRODUCT-PASS-CONTRACT.md
STATUS: ARCHIVED / SUPERSEDED · 非现行 BINDING 签字源
DATE: 2026-08-09
SUPERSEDED_BY:
  - docs/TRUTH-FREEZE.md v1.1（Pi + DeepSeek 默认）
  - docs/HANDOFF-WB-PI.md
  - docs/PLAN-TWO-PHASE-WB.md（阶段一/二验收）
  - docs/STATE-NOW.md（实现快照）
VOID_NOTE: 文首旧句「全球 product PASS: CLAIMED @ 38067b82…」自本清源起 **作废**，
  不得再作为 BINDING 自证或 CLAIMED 真源。该 SHA 对应 Kimi-only 叙事时代的业主签字记录，
  与 v1.1 目标不一致；阶段一/二 **均不**自动继承该 GLOBAL PASS。
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签（现行）
```

> **执行窗铁律：** 本文件保留门禁表与角色定义供考古；**禁止**引用本节旧 CLAIMED 句宣称全球已 PASS。  
> **禁止自签** 全球 product PASS / CLAIM-WB。业主新签必须新 tip + 新签字句。

---

## 0. 作废头注（2026-08-09 · F0 清源）

| 旧状态（勿再用） | 现行 |
|------------------|------|
| `全球 product PASS: CLAIMED` @ `38067b824c2e5fd5e445d7f33a20089c8f13360d` | **VOID** — 过期；不得 BINDING 自称 CLAIMED |
| 默认 runtime = Kimi Agent；禁 Pi / DeepSeek 默认 | **作废** — 见 TRUTH-FREEZE v1.1：默认 **Pi + DeepSeek** |
| ENGINEERING complete = Kimi-only multi-step 故事 | 遗产可记；**产品故事 = Pi + DeepSeek** |
| 本文件 STATUS: BINDING contract | **ARCHIVED** — 定义残留；签字权仅在业主新句 |

**历史记录（非现行 BINDING）：**  
#298 曾有 `OWNER ACCEPT: P-GLOBAL-PASS-CLOSE` 覆盖当时 ENGINEERING-COMPLETE + GLOBAL-PRODUCT-PASS，锚定 tip `38067b82…`。  
该签字**不**覆盖 v1.1 纠偏后的产品目标，**不**免除阶段一/二证据，**不**等于 CLAIM-WB。

---

## 1. 范围（历史「全球」定义 · 仅参考）

| 维度 | 曾纳入全球 product PASS | 不纳入（另 STAGE） |
|------|----------------------|-------------------|
| Persona | 演示教师 / 演示管理员（seed 号）在公网工作台完整日用 | 全量学校租户迁移、edu-core 业务对接 |
| 表面 | `https://pico.aivia.asia` 登录 → 任务 → 过程 → 产物 → 停/重跑 | Live Preview 专属路径、未上线功能开关 |
| 功能面 | 多步 Agent、direct 短聊不误走 agent、账本 Task/Run/Artifact | 定价/商业 FIXED、教师执行沙箱 |
| 视口 | 桌面 + 移动 **390** 主路径可点（非 pe 绕过唯一证据） | 全矩阵像素回归 |
| 运行时（**现行覆盖**） | **默认 Pi + DeepSeek**（v1.1） | 旧表「kimi-only 默认」已废 |

---

## 2. 门禁表（P0 必须项 · 定义保留）

| ID | 门禁 | 通过标准 |
|----|------|----------|
| P0-1 | 公网登录 | 错密拒绝；对密进入工作台 |
| P0-2 | 短任务 | multi-step 成功终态；过程/终态可见 |
| P0-3 | 停或重跑 | ≥1 类动作与账本一致（cancelled sticky 或 rerun 新 run） |
| P0-4 | 真产物 | html\|docx\|pptx 至少 1 类非空 + `content_sha256` + content 下载成功 |
| P0-5 | 390 主路径 | 已登录视口可点任务/结果入口（禁 pe 绕过作为唯一证据） |
| P0-6 | 默认核 | 默认 multi-step = **Pi**（v1.1）；health/事件可核；非双核并列 |
| P0-7 | 无 loop | 树无 `run_agent_loop`/`runner.py`；禁止复活自研环 |
| P0-8 | tip=prod | 公网 tip / health `git_sha` exact 等于声明 tip（40 位） |
| P0-9 | 无假绿 | 禁止用 mock 唯一证明、禁止密钥进 Issue、禁止自签 |

**任一项 FAIL → 全球 product PASS 不可签。**  
**现行验收载体：** 阶段一见 PLAN-TWO-PHASE-WB；阶段二见 W1–W5。本表不单独构成 CLAIMED。

---

## 3. 证据形态

| 角色 | 证据 |
|------|------|
| 执行窗 | Issue 内 run id 指纹、tip/health JSON 字段（无密钥）、截图路径、下载 SHA 前缀 |
| 独立验证 | 已登录 + 视觉 + 浏览器操控；390 截图或录像 |
| 禁止 | 仅 curl health 当 product PASS；仅 unit 绿当 product PASS；散文无锚点；引用 §0 旧 CLAIMED |

---

## 4. 角色与签字句

| 角色 | 权责 |
|------|------|
| 执行窗 | 测、写证据、**禁止**自签全球 product PASS / CLAIM-WB |
| 审查 | 独立复测关键门禁 |
| 业主 | 唯一可签全球 product PASS / CLAIM-WB |

**业主签字句式（仅当门禁全绿且 tip=prod exact，且目标与 v1.1 一致）：**

```text
OWNER ACCEPT: GLOBAL-PRODUCT-PASS @ <full-40-char-sha>
```

**非全球、仅工程：**

```text
OWNER ACCEPT: ENGINEERING-COMPLETE @ <full-40-char-sha>
```

（ENGINEERING 签字 **不** 隐含全球 product PASS，**不** 隐含 CLAIM-WB。）

---

## 5. ENGINEERING complete ≠ product PASS

| 标签 | 含义 | 本仓库允许条件 |
|------|------|----------------|
| **ENGINEERING complete** | 编排工程路径闭合：默认 Pi multi-step、无 transitional loop、Wire/账本/cancel/产物可验证 | 证据矩阵齐 + 文档句冻结 |
| **全球 product PASS** | 公网日用门禁全集业主验收 | **仅** 业主新 `GLOBAL-PRODUCT-PASS` 句 @ 现行 tip |
| **CLAIM-WB-DEGREE-WEB** | WorkBuddy 六条 Web 程度 | **仅** 业主书面；阶段一二全优亦不自动签 |

允许文档句（工程，示例）：

> Orchestration path is **ENGINEERING complete** at tip \<sha\> (default Pi multi-step; DeepSeek primary). **Global product PASS: NOT CLAIMED.** **CLAIM-WB: NO.**

---

## 6. 禁区

假全球 product PASS · 复活旧 CLAIMED@38067b82 · 无证 ENGINEERING complete · 回 loop · 双核并列真源 · 密钥进 Issue · 用 DEPLOYED 冒充 product PASS · 定向题词 if / 假绿
