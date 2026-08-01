# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。**  
> **编排目标（唯一）= 开源 Kimi Agent。**  
> **`run_agent_loop` = 实现债，从未是目标。**  
> **日常节奏：[FAST-PATH.md](./FAST-PATH.md)**（改→合→窗1装→窗4点测）。

```text
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-01
TRUTH_ORDER: GitHub 证据 > 本页 > 聊天
```

---

## 0. 产品与目标

| 层 | 内容 |
|----|------|
| 产品 | 学校向独立 AI 工作台底座（LibreChat 壳 + Pico 账本/控制面 + Kimi HTTPS） |
| 编排目标 | **只此一个：开源 Kimi Agent 真接入** |
| 实现债 | 默认路径仍可能经 `run_agent_loop` → 待归位；**不是目标** |
| 授权 | **KA-3 未授权**（#170 HOLD）；#159 zombie HOLD |
| 禁 | Plan B；教师默认沙箱；edu-cloud；假接入 |

## 窗口地图（BINDING）

| 窗口 | 角色 |
|------|------|
| **1** | 部署（ssh / prod-update / remote-health） |
| **2** | 写入 |
| **3** | 写入/调查（并行） |
| **4** | **独立验证**：已登录 + 视觉 + 操控网页 |

**用户成功：** 登录 → 下任务 → 过程可见 → 产物 → 能停/找回/再试 → 状态诚实。

---

## 1. SHA

| 面 | SHA | 含义 |
|----|-----|------|
| main tip（写页时） | `c37ee1eea8bd1cbb0c3a3a2e6c4e18b00114a7ad` | 含窗口地图等文档；**写页后若再合 PR 以 GitHub 为准** |
| **生产应用** | **`9a9ddba3e6a3c425c3db3e599081f8da9394e8e8`** | #175 DEPLOYED ACCEPT；含 #174 stop/sqlite |
| 历史全项烟测 | `674707dd…` | #142 PASS（旧 tip，仅历史） |

生产硬证：#175 health 三一致 + #176 窗4 点测。

---

## 2. 日用门禁（当前）

| 项 | 状态 |
|----|------|
| #175 部署 | **CLOSED · ACCEPT** @ `9a9ddba…` |
| #176 窗4 chat/stop | **CLOSED · ACCEPT PASS**（login/chat/stop cancelled；sqlite_leak none） |
| #174 stop/sqlite 修复 | **在生产**并被 #176 验证 |
| #165 旧视觉 FAIL | **CLOSED**（被 #176 覆盖） |
| 全站 product PASS | **NOT CLAIMED** |
| Kimi Agent 已接入 | **NOT CLAIMED**（flag OFF） |

**当前可以说：** 生产 `9a9ddba` 上能登录、能真聊、能停到 cancelled。  
**不能说：** 全站验收完、编排已是开源 Kimi Agent。

---

## 3. 运维已收口

| 项 | 状态 |
|----|------|
| deploy key 取码 #157 | DONE |
| UI readiness 重试 #160 | 在生产路径 |
| fetch refspec / preflight #164/#172 | 文档+脚本 |
| remote-health #171 | 脚本在 main |
| 生产 `.git` 属主 | #175 已修为部署用户；runbook 见 DEPLOY-TWO-HOST / FAST-PATH |

---

## 4. HOLD

- **#170 KA-3** — 须业主书面授权  
- **#159 zombie 清库** — 须授权  

---

## 5. 节奏（砍税后）

见 [FAST-PATH.md](./FAST-PATH.md) KEEP/CUT。

```text
日用：9a9ddba 基线曾 PASS；main 已含 canary/deny/cap/safety（flag OFF）
推进：少卡、大 PR、窗1装、窗4点；KA 放量仅授权后
HOLD：#170 切流 · #159 zombie（须授权）
```

product PASS: **NOT CLAIMED** · 编排完成: **NOT CLAIMED**
