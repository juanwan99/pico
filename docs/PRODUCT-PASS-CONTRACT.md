# 全球 product PASS 合同（BINDING）

```
DOC: docs/PRODUCT-PASS-CONTRACT.md
STATUS: BINDING contract
STAGE: #295 / #298 GLOBAL 已签 / #299 harden
DATE: 2026-08-05
SCOPE: 定义 + 已签状态句；本文件不自动重跑全球 PASS 实测全集
```

**全球 product PASS: CLAIMED** @ `38067b824c2e5fd5e445d7f33a20089c8f13360d`  
（#298 `OWNER ACCEPT: P-GLOBAL-PASS-CLOSE` 同时覆盖 ENGINEERING-COMPLETE + GLOBAL-PRODUCT-PASS。）  
**ENGINEERING complete ≠ product PASS**（见 §5）；**禁止执行窗自签重开**。

---

## 1. 范围（什么叫「全球」）

| 维度 | 纳入全球 product PASS | 不纳入（另 STAGE） |
|------|----------------------|-------------------|
| Persona | 演示教师 / 演示管理员（seed 号）在公网工作台完整日用 | 全量学校租户迁移、edu-core 业务对接 |
| 表面 | `https://pico.aivia.asia` 登录 → 任务 → 过程 → 产物 → 停/重跑 | Live Preview 专属路径、未上线功能开关 |
| 功能面 | pico-agent 多步（Kimi Agent）、direct 短聊不误走 agent、账本 Task/Run/Artifact | 定价/商业 FIXED、教师执行沙箱 |
| 视口 | 桌面 + 移动 **390** 主路径可点（非 pe 绕过唯一证据） | 全矩阵像素回归 |
| 运行时 | 默认 `runtime=kimi-agent`（或 kimi-only 等价）；无 loop | Pi / DeepSeek 默认 |

---

## 2. 门禁表（P0 必须项）

| ID | 门禁 | 通过标准 |
|----|------|----------|
| P0-1 | 公网登录 | 错密拒绝；对密进入工作台 |
| P0-2 | 短任务 | pico-agent 成功终态；过程/终态可见 |
| P0-3 | 停或重跑 | ≥1 类动作与账本一致（cancelled sticky 或 rerun 新 run） |
| P0-4 | 真产物 | html\|docx\|pptx 至少 1 类非空 + `content_sha256` + content 下载成功 |
| P0-5 | 390 主路径 | 已登录视口可点任务/结果入口（禁 pe 绕过作为唯一证据） |
| P0-6 | kimi-only | 默认 multi-step = Kimi Agent；health scope 合理 |
| P0-7 | 无 loop | 树无 `run_agent_loop`/`runner.py`；health `legacy_loop_unavailable=true` |
| P0-8 | tip=prod | `health.git_sha` exact 等于声明 tip（40 位） |
| P0-9 | 无假绿 | 禁止用 mock 唯一证明、禁止密钥进 Issue、禁止自签 |

**任一项 FAIL → 全球 product PASS 不可签。**

---

## 3. 证据形态

| 角色 | 证据 |
|------|------|
| 执行窗 | Issue 内 run id 指纹、health JSON 字段（无密钥）、截图路径、下载 SHA 前缀 |
| 独立验证（窗4） | 已登录 + 视觉 + 浏览器操控；390 截图或录像 |
| 禁止 | 仅 curl health 当 product PASS；仅 unit 绿当 product PASS；散文无锚点 |

---

## 4. 角色与签字句

| 角色 | 权责 |
|------|------|
| 执行窗 | 测、写证据、**禁止**自签全球 product PASS |
| 审查/窗4 | 独立复测关键门禁 |
| 业主 | 唯一可签全球 product PASS |

**业主签字句式（仅当 §2 全绿且 tip=prod exact）：**

```text
OWNER ACCEPT: GLOBAL-PRODUCT-PASS @ <full-40-char-sha>
```

**非全球、仅工程：**

```text
OWNER ACCEPT: ENGINEERING-COMPLETE @ <full-40-char-sha>
```

（ENGINEERING 签字 **不** 隐含全球 product PASS。）

---

## 5. ENGINEERING complete ≠ product PASS

| 标签 | 含义 | 本仓库允许条件 |
|------|------|----------------|
| **ENGINEERING complete** | 编排工程路径闭合：Kimi-only multi-step、无 transitional loop、Wire/账本/cancel/产物可验证 | 证据矩阵齐 + 文档句冻结（见 `docs/KIMI-AGENT-GAP.md` / `docs/STATE-NOW.md`） |
| **全球 product PASS** | 公网日用门禁全集业主验收 | **仅** 本合 + 业主 `GLOBAL-PRODUCT-PASS` 句 |

允许文档句（工程）：

> Orchestration path is **ENGINEERING complete** at tip \<sha\> (Kimi-only multi-step; no transitional loop). **Global product PASS: NOT CLAIMED.**

---

## 6. 本包子集（#295）

| 项 | 本包是否执行 |
|----|----------------|
| 合同本文 6 节 | **是**（本文件） |
| 冻 tip 复审 / cancel / 产物抽测 | **是**（A/E/D 证据，支撑 ENGINEERING，**不**签全球 PASS） |
| 全球 PASS 实测全集（§2 全角色+窗4 全矩阵） | **否** — 定义 only · 实测另 STAGE |
| 自签全球 product PASS | **禁止** |

---

## 7. 禁区

假全球 product PASS · 无证 ENGINEERING complete · 回 loop · Pi · DeepSeek 默认 · 密钥进 Issue · 用 DEPLOYED 冒充 product PASS
