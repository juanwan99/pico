# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。**  
> **编排目标（唯一）= 开源 Kimi Agent。**  
> **`run_agent_loop` = 已物理删除（KA-4 HARD #288）；从未是目标。**  
> **日常节奏：[FAST-PATH.md](./FAST-PATH.md)**（改→合→窗1装→窗4点测）。

```text
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-05 (P-POST-RESIDUAL-MEGA #295)
TRUTH_ORDER: GitHub 证据 > 本页 > 聊天
```

---

## 0. 产品与目标

| 层 | 内容 |
|----|------|
| 产品 | 学校向独立 AI 工作台底座（LibreChat 壳 + Pico 账本/控制面 + Kimi HTTPS） |
| 编排目标 | **只此一个：开源 Kimi Agent 真接入** |
| 实现 | 生产默认 `pico-agent` → **Kimi Agent only**（#278+#288 HARD）；`run_agent_loop`/`runner.py` **已删**；RUNTIME=0/旧 emergency **fail-closed**；health **`legacy_loop_unavailable=true`**（#295 F，不再暴露 raw emergency）；回滚=**redeploy 旧 tip** |
| 授权 | **KA-3 已签**（#170 KA3_AUTH · #278）；**KA-4 HARD 已合**（#288/#289）；编排路径 **ENGINEERING complete**（#295 · 证据矩阵）；全球 product PASS **未宣称**（合同见 [PRODUCT-PASS-CONTRACT.md](./PRODUCT-PASS-CONTRACT.md)） |
| 禁 | Plan B；教师默认沙箱；edu-cloud；假接入；自升全球 product PASS |

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
| **main tip（写页时基线）** | **`b2158a399aab44adae26df92ee93f73cc43e0c87`** | #290 residual R1–R9 · #292；#295 本包从此 tip 起 |
| health 对齐 | exact · scope=`all` · batch=`BATCH-KA3-DEFAULT` · `legacy_loop_unavailable=true` | loopback `/health` |
| 历史 | `096bbb2…` / `18b7c2b…` 等 | 仅考古；**勿覆盖当前 tip** |

运维字段解读：[OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md) · [KIMI-OPERATIONS.md](./KIMI-OPERATIONS.md)。

---

## 2. 日用门禁（当前）

| 项 | 状态 |
|----|------|
| #278 P-KA3-DEFAULT | **CLOSED · OWNER ACCEPT** |
| 生产默认 runtime | **kimi-agent**（空 canary=全员） |
| bare/无效 canary | **fail-closed**（不得误变 scope=all） |
| #284 稳定 | **CLOSED/ACCEPT** |
| #288 KA-4 HARD | **合入 main** · runner 已删 · loop unavailable |
| #290 residual R1–R9 | **合入** #292 |
| #295 residual mega | **进行中**（ENGINEERING complete 合同 + UX/运维） |
| 全站 product PASS | **NOT CLAIMED**（定义见 PRODUCT-PASS-CONTRACT） |
| orchestration ENGINEERING complete | **允许声明**（证据齐 · **≠** product PASS） |

**当前可以说：** 生产 tip 上 pico-agent 默认进 Kimi Agent；编排路径 **ENGINEERING complete**；可 redeploy 回滚；过渡环已物理删除。  
**不能说：** 全球 product PASS。

---

## 3. 运维已收口

| 项 | 状态 |
|----|------|
| deploy key / remote-health / prod-update | 脚本在 main |
| 登录限流 · 测密 · health 字段 | [OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md) |
| KA-3 回滚 OFF→恢复 | #278 K6 已实测 |
| 最小测路径（无 host py3.12） | `bash scripts/run-min-tests.sh` 或 CI Python 3.12 |

---

## 4. residual（#290 关闭表）

见阶段 Issue #290 成果包关闭表。摘要目标：

| ID | 项 |
|----|-----|
| R1 | in-flight cancel → sticky cancelled |
| R2 | 产物 content 路径人话 |
| R3 | 公网 login 502 采样/分类 |
| R4 | 真登录 + 390 可点 |
| R5 | REST/proxy 自读路径表 |
| R6 | 双开不脏账本 + 忙态人话 |
| R7 | tip == health.git_sha exact |
| R8 | 容器/CI 一键最小测 |
| R9 | emergency 语义 no-op 诚实 |

---

## 5. 节奏

见 [FAST-PATH.md](./FAST-PATH.md) KEEP/CUT。

```text
当前 tip 基线: b2158a3… · scope=all · keep-kimi · legacy_loop_unavailable=true
KA-3: OWNER ACCEPT · #278
KA-4 HARD: main · #288/#289
推进: #295 P-POST-RESIDUAL-MEGA
禁: 假全球 product PASS · 无证 ENGINEERING · 回 loop · Pi/DeepSeek 默认
```

product PASS: **NOT CLAIMED** · orchestration: **ENGINEERING complete**（≠ product PASS）
