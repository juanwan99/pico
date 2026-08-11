# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-11
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 等业主 OWNER DECISION（#449）
公网 tip（装订冻结 · 须实查）: 502e1f6fd5d3f5999b43303de91b16de1375f26a
main 文档 HEAD 写卷时: 以 origin/main 实查为准
```

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 业主方向（最新 BINDING）

见 **[docs/DIRECTION-NOW.md](./DIRECTION-NOW.md)**

```text
1) 通用开放域 · 教育仅之一
2) Pi + DeepSeek
3) 通用能力 + 复杂问题（办公优先）
4) 对标 WorkBuddy · 本阶段只打牢 Agent + UI/UX
   不做：连接器 / MCP / Skill 摊子
```

## 锁定句

```text
目标：Web 上对标 WorkBuddy 的办事能力（体验向）
方案：Pico 整车 + Pi + DeepSeek
本阶段：基础能力（Agent 优化 + 交互体验）
不做：Dify 门脸 · 场景卷对标 · 双核 · MCP/Skill/连接器铺开
验收秤：阶段一底座全优 → 阶段二加压；基建是手段
```

## 三包状态（2026-08-11）

| 大包 | 卡 | 状态 | tip | 证据 |
|------|-----|------|-----|------|
| **1** UX-HARDEN | #447 | **PACKAGE READY · UX-HARDEN** | 502e1f6… | [`evidence/pack-ux-harden/`](./evidence/pack-ux-harden/) |
| **2** TRUE-PI-FINAL-MATRIX | #448 | **PACKAGE READY · TRUE-PI-FINAL-MATRIX** | 502e1f6… | [`evidence/pack-final-matrix/`](./evidence/pack-final-matrix/) |
| **3** CLAIM-MATERIALS | #449 | **装订中 → 等主管 L2 → 停等业主** | 冻结 502e1f6… | [`CLAIM-MATERIALS-2026-08/`](./CLAIM-MATERIALS-2026-08/) |

```text
CLAIM-WB: NO · 工程禁止代签
材料: docs/CLAIM-MATERIALS-2026-08/
纪律: docs/CLAIM-WB-PATH.md
详规: docs/PLAN-PACK3-CLAIM-MATERIALS.md
```

## 主线

| 阶段 | 状态 |
|------|------|
| **一 ENABLE** | 工程三包收口中 · 材料齐后等 **业主 CLAIM-WB** |
| **二 加压** | 阶段一产品终签后 · W 题/重办公链可选 · 仍不默认开 MCP/Skill |

规划骨架：[PLAN-TWO-PHASE-WB.md](./PLAN-TWO-PHASE-WB.md)（范围以 DIRECTION-NOW 收窄为准）

## 工程快照

| 项 | 值 |
|----|-----|
| 公网 tip | `GET /api/pico/tip` → 须 40 位；材料冻结 **502e1f6fd5d3f5999b43303de91b16de1375f26a** |
| multi-step 默认 | **pi-true** |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| drain | 45s inflight · grace 60s · **≠ 零中断**（见 RUN-DRAIN-AND-STOP） |
| CLAIM-WB | **NO** |

## 错误记忆

见 MEMORY-RESET：禁止 edu 串仓；禁止用 HTML 课件单测代替复杂能力；禁止引用过期 GLOBAL PASS@38067b82；本阶段不做 MCP/Skill/连接器；**禁止工程代签 CLAIM-WB YES**。

## 真 Pi 核（#435/#436）

| 项 | 值 |
|----|-----|
| multi-step 默认 | **pi-true**（`PICO_TRUE_PI_DEFAULT=1`） |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` → pi-agent |
| 镜像 | `Dockerfile.pico-api.true-pi`（prod host compose） |
| 钉版 | `@mariozechner/pi-coding-agent@0.73.1` |
| 文档 | ADR Accepted · OPS-TRUE-PI-ROLLBACK |
| CLAIM-WB | **NO** |
