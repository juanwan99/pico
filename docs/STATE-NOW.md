# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。**  
> **编排目标（唯一）= 开源 Kimi Agent。**  
> **`run_agent_loop` = 实现债，从未是目标。**  
> **日常节奏：[FAST-PATH.md](./FAST-PATH.md)**（改→合→窗1装→窗4点测）。

```text
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-05
TRUTH_ORDER: GitHub 证据 > 本页 > 聊天
```

---

## 0. 产品与目标

| 层 | 内容 |
|----|------|
| 产品 | 学校向独立 AI 工作台底座（LibreChat 壳 + Pico 账本/控制面 + Kimi HTTPS） |
| 编排目标 | **只此一个：开源 Kimi Agent 真接入** |
| 实现现状 | 生产默认 `pico-agent` → **Kimi Agent**（#278 OWNER ACCEPT · tip/`health.git_sha` `18b7c2b…` · scope=**all** · emergency **false**） |
| 实现债 | `runner.py` / `run_agent_loop` **仍在仓**；默认路径**不可达**（仅 RUNTIME=0 或 emergency）；**KA-4 软**见 [KA4-SOFT.md](./KA4-SOFT.md) · #284 |
| 授权 | **KA-3 已签**（#170 KA3_AUTH · #278）；全球 product PASS **未宣称**；orchestration complete **未宣称** |
| 禁 | Plan B；教师默认沙箱；edu-cloud；假接入；硬删 runner 当完成证据 |

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
| **main tip / 生产应用（写页时）** | **`18b7c2b161bc0424f309ecb2b88f3db001990b8f`** | #282 bare fail-closed + #280 KA-3 default · #278 ACCEPT |
| health 对齐 | exact · scope=`all` · batch=`BATCH-KA3-DEFAULT` | loopback `/health` |
| 历史 | `9a9ddba…` / `5baf0cf…` 等 | 仅考古；**勿覆盖当前 tip** |

运维字段解读：[OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md)。

---

## 2. 日用门禁（当前）

| 项 | 状态 |
|----|------|
| #278 P-KA3-DEFAULT | **CLOSED · OWNER ACCEPT** @ `18b7c2b…` |
| 生产默认 runtime | **kimi-agent**（空 canary=全员） |
| bare/无效 canary | **fail-closed**（不得误变 scope=all） |
| #284 冻 tip 稳定包 | **进行中 / 见 Issue**（复审 · residual 软 · KA-4 软 · 不写 complete） |
| 全站 product PASS | **NOT CLAIMED** |
| orchestration complete | **NOT CLAIMED** |

**当前可以说：** 生产 tip `18b7c2b…` 上 pico-agent 默认进 Kimi Agent；可回滚；runner 文件保留。  
**不能说：** 全球 product PASS、编排 complete、自研环已物理删除。

---

## 3. 运维已收口

| 项 | 状态 |
|----|------|
| deploy key / remote-health / prod-update | 脚本在 main |
| 登录限流 · 测密 · health 字段 | [OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md) |
| KA-3 回滚 OFF→恢复 | #278 K6 已实测 |

---

## 4. HOLD / residual（软 · 不阻断 #278）

- 全球 product PASS / orchestration complete — **须业主另句**  
- in-flight cancel 弱（终态 cancel→409）  
- REST 自读路径易混（正确：`/v1/artifacts/{id}/content`）  
- **#159 zombie 清库** — 须授权  
- KA-4 **硬删 runner** — **不做**（软交付即可）  

---

## 5. 节奏

见 [FAST-PATH.md](./FAST-PATH.md) KEEP/CUT。

```text
当前 tip/prod: 18b7c2b… · scope=all · keep-kimi
KA-3: OWNER ACCEPT · #278
推进: #284 稳定包（只测/文档/软断言；部署≤1 仅必要）
禁: 假 PASS · complete 自升 · 删 runner · Pi/DeepSeek 默认
```

product PASS: **NOT CLAIMED** · 编排完成: **NOT CLAIMED**
