# STATE-NOW · Pico（本窗真源）

> **新窗交接（2026-08-11）：** [`HANDOFF-NEW-WINDOW-2026-08-11.md`](./HANDOFF-NEW-WINDOW-2026-08-11.md) · 主线 **#470**


```text
DATE: 2026-08-11
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 等业主 OWNER DECISION（#449）
公网 tip（现网实查）: c6186d2dcf5c5ec27a4589112a0cb0ff2cc3409c
材料装订冻结 tip（#449 对比表）: 502e1f6fd5d3f5999b43303de91b16de1375f26a
  · 冻结 tip 不等于现网 tip · 签 CLAIM 前必须 curl 实查
卫生: #471 看板清理完成一批 · 活动主线见下
```

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线（卫生后 · 2026-08-11）

| 优先级 | Issue | 说明 |
|--------|-------|------|
| **P0** | [#470](https://github.com/juanwan99/pico/issues/470) | 双档 true_pi 按档 thinking/熔断 + 列表两档 + 类人（收 #468 REVISE） |
| P0 父 | [#468](https://github.com/juanwan99/pico/issues/468) · PR [#469](https://github.com/juanwan99/pico/pull/469) | 双档大包 · L2 REVISE · **勿当完成合入** |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | CLAIM 材料等**业主** · 工程禁代签 |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) · [#159](https://github.com/juanwan99/pico/issues/159) | 须业主授权 · 未执行 |
| 卫生 | [#471](https://github.com/juanwan99/pico/issues/471) | 看板/文档清理本轮 |

```text
已归档（close）: P1–P5、UX、真核切流、三轴夜包、HDS 等多张历史卡 → 见 #471
禁止把已 close 卡当活动主线
```

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

## 三包状态（工程 · 2026-08-11）

| 大包 | 卡 | 状态 | tip | 证据 |
|------|-----|------|-----|------|
| **1** UX-HARDEN | #447 | PACKAGE READY · Issue 已卫生关闭 | 502e1f6… | evidence/pack-ux-harden/ |
| **2** TRUE-PI-FINAL-MATRIX | #448 | PACKAGE READY · Issue 已卫生关闭 | 502e1f6… | evidence/pack-final-matrix/ |
| **3** CLAIM-MATERIALS | #449 | 材料齐 · **等业主 CLAIM-WB**（仍 open） | 冻结 502e1f6… | CLAIM-MATERIALS-2026-08/ |

```text
CLAIM-WB: NO · 工程禁止代签
材料: docs/CLAIM-MATERIALS-2026-08/
纪律: docs/CLAIM-WB-PATH.md
```

## 主线

| 阶段 | 状态 |
|------|------|
| **一 ENABLE** | 工程底座多包已 READY · CLAIM 等业主 · **功能主线=双档 #470** |
| **二 加压** | 阶段一产品终签后 · 仍不默认开 MCP/Skill |

## 工程快照

| 项 | 值 |
|----|-----|
| 公网 tip | `GET /api/pico/tip` → 须 40 位实查 |
| multi-step 默认 | **pi-true** |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| drain | 45s inflight · grace 60s · **≠ 零中断** |
| CLAIM-WB | **NO** |

## 错误记忆

见 MEMORY-RESET：禁止 edu 串仓；禁止工程代签 CLAIM-WB YES；禁止把冻结 tip 当现网 tip。

## 真 Pi 核

| 项 | 值 |
|----|-----|
| multi-step 默认 | **pi-true**（`PICO_TRUE_PI_DEFAULT=1`） |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| 钉版 | `@mariozechner/pi-coding-agent@0.73.1` |
| CLAIM-WB | **NO** |
