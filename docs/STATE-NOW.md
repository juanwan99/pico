# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。**  
> **编排目标（唯一）= 开源 Kimi Agent。**  
> **`run_agent_loop` = 已物理删除（KA-4 HARD #288）；从未是目标。**  
> **日常节奏：[FAST-PATH.md](./FAST-PATH.md)**（改→合→窗1装→窗4点测）。

```text
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-05 (P-POST-GLOBAL-HARDEN #299 · post #298 GLOBAL PASS)
TRUTH_ORDER: GitHub 证据 > 本页 > 聊天
```

---

## 0. 产品与目标

| 层 | 内容 |
|----|------|
| 产品 | 学校向独立 AI 工作台底座（LibreChat 壳 + Pico 账本/控制面 + Kimi HTTPS） |
| 编排目标 | **只此一个：开源 Kimi Agent 真接入** |
| 实现 | 生产默认 `pico-agent` → **Kimi Agent only**（#278+#288 HARD）；`run_agent_loop`/`runner.py` **已删**；RUNTIME=0/旧 emergency **fail-closed**；health **`legacy_loop_unavailable=true`**（#295 F）；回滚=**redeploy 旧 tip** |
| 授权 | **KA-3 已签** · **KA-4 HARD 已合** · 编排 **ENGINEERING complete** · **全球 product PASS 已签**（#298 @ `38067b82…`） |
| 禁 | Plan B；教师默认沙箱；edu-cloud；假接入；**自签重开**全球 product PASS |

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
| **main tip（写页时基线）** | **`38067b824c2e5fd5e445d7f33a20089c8f13360d`** | #295 residual mega · #297；#298 GLOBAL PASS 签于本 tip |
| health 对齐 | exact · scope=`all` · batch=`BATCH-KA3-DEFAULT` · `legacy_loop_unavailable=true` | **loopback** `/health` 或登录后 `/api/pico/health`（策略 A） |
| 历史 | `b2158a3…` / `096bbb2…` 等 | 仅考古；**勿覆盖当前 tip** |

### 1.1 窗4 tip 对齐路径（策略 A · #299 H1）

| 路径 | 谁用 | 字段 |
|------|------|------|
| 公网 `GET /health` | 探活 | 常仅 `OK` — **不**作为 git_sha 真源 |
| loopback `GET 127.0.0.1:18765/health` | 窗1 / `remote-health.sh` | **运维字段真源**（含 git_sha） |
| 登录后 `GET /api/pico/health` | **窗4 验证** | 需 JWT；JSON 含 `git_sha`（**禁止**把全量 health 无设计公网裸露） |

运维字段解读：[OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md) · [KIMI-OPERATIONS.md](./KIMI-OPERATIONS.md)。

---

## 2. 日用门禁（当前）

| 项 | 状态 |
|----|------|
| #278 P-KA3-DEFAULT | **CLOSED · OWNER ACCEPT** |
| 生产默认 runtime | **kimi-agent**（空 canary=全员） |
| bare/无效 canary | **fail-closed** |
| #284 稳定 | **CLOSED/ACCEPT** |
| #288 KA-4 HARD | **合入 main** · runner 已删 · loop unavailable |
| #290 residual R1–R9 | **合入** #292 |
| #295 residual mega | **CLOSED** · ENGINEERING complete 合同 |
| #298 GLOBAL-PASS-CLOSE | **CLOSED · OWNER ACCEPT** @ `38067b82…`（含 ENGINEERING-COMPLETE + GLOBAL-PRODUCT-PASS） |
| #299 POST-GLOBAL-HARDEN | **进行中**（四根因链加固 · 非重签 GLOBAL） |
| 全站 product PASS | **CLAIMED @ 38067b82…**（#298 业主签；本包不重开） |
| orchestration ENGINEERING complete | **CLAIMED**（#295/#298） |

**当前可以说：** 生产 tip 上 pico-agent 默认进 Kimi Agent；编排 **ENGINEERING complete**；全球 product PASS **已签**于 tip `38067b82…`；可 redeploy 回滚。  
**不能说：** 未部署 tip 上自升 PASS；密钥进 Issue；无 AUTH 实转生产密。

---

## 3. 运维已收口

| 项 | 状态 |
|----|------|
| deploy key / remote-health / prod-update | 脚本在 main |
| 登录限流 · 测密 · health 字段 | [OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md) |
| 502 持续采样 | jump 公网 cron + prod loopback · DUTY 见 runbook §7 |
| 凭据 SSOT | **密码器条目**（非仓库/Issue 明文）· 生产 seed 默认关 |
| KA-3 回滚 OFF→恢复 | #278 K6 已实测 |
| 最小测路径（无 host py3.12） | `bash scripts/run-min-tests.sh` 或 CI Python 3.12 |

---

## 4. residual / harden

| 源 | 状态 |
|----|------|
| #290 R1–R9 | 关闭（#292） |
| #295 mega | ENGINEERING complete |
| #298 G1–G8 | G1–G6/G8 关；**G7 测密实转 BLOCKED**（无 AUTH） |
| #299 H1–H10 | 本包：验证面/凭据 SSOT/移动层叠/真源文档 |

---

## 5. 节奏

见 [FAST-PATH.md](./FAST-PATH.md) KEEP/CUT。

```text
当前 tip 基线: 38067b82… · scope=all · keep-kimi · legacy_loop_unavailable=true
KA-3: OWNER ACCEPT · #278
KA-4 HARD: main · #288/#289
GLOBAL product PASS: OWNER ACCEPT · #298 @ 38067b82…
推进: #299 P-POST-GLOBAL-HARDEN（加固 · 不重开 GLOBAL）
禁: 假重签 GLOBAL · 密钥进 Issue · 无 AUTH 实转 · pe 假绿 · 回 loop · Pi/DeepSeek 默认
```

product PASS: **CLAIMED @ 38067b824c2e5fd5e445d7f33a20089c8f13360d** · orchestration: **ENGINEERING complete**
