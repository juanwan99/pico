# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-13
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 等业主 OWNER DECISION（#449）
公网 tip（派卡时 / 本卡 BASE）: 7608a45cb3d5264bc31a8ddd882f2a2aae8a6942
材料装订冻结 tip（#449 对比表）: 502e1f6fd5d3f5999b43303de91b16de1375f26a
  · 冻结 tip 不等于现网 tip · 签 CLAIM 前必须 curl 实查
活动主线: 计量 + 搜索 + 沙箱（#506 / #507 / #508 已装 · 本卡 #513）
```

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线（卫生后 · 2026-08-13）

| 优先级 | Issue | 说明 |
|--------|-------|------|
| **P0 进行中** | [#513](https://github.com/juanwan99/pico/issues/513) | T-HYGIENE-SEARCH-UX-SANDBOX-S2：板面卫生 + 搜索来源人眼可见 + S2 看页光栅 |
| 已装 | [#506](https://github.com/juanwan99/pico/issues/506) | 用量账本 `usage_events`（统计/管理 · 不做钱） |
| 已装 | [#507](https://github.com/juanwan99/pico/issues/507) | DeepSeek `web_search` + gateway `web_fetch`（来源或诚实未检索） |
| 已装 | [#508](https://github.com/juanwan99/pico/issues/508) | S1 隔离工作区 + title/h1 看页（进程级 · 非微 VM） |
| 规划仍开 | [#505](https://github.com/juanwan99/pico/issues/505) | 沙箱规划稿 · **勿关** · 本卡只升 S2 一档 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | CLAIM 材料等**业主** · 工程禁代签 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) · [#159](https://github.com/juanwan99/pico/issues/159) | 须业主授权 · 未执行 · **勿关** |
| 讨论稿 | [#498](https://github.com/juanwan99/pico/issues/498) · [#475](https://github.com/juanwan99/pico/issues/475) | edu 嵌入 / 讨论 · **勿关 · 本卡不做 #498** |

```text
已装功能在 tip 7608a45c… ：用量账本 · DS 搜/读页 · S1 隔离+title/h1
空壳已关（GitHub closed · 勿再当主线）:
  #468 #470 #476 #479 #474
  诚实句：双档等功能在 tip，PERF 对比未做满
禁止把已 close 卡当活动主线
禁止误关：#316 #449 #498 #505 #170 #159 #475
```

## 业主方向（最新 BINDING）

见 **[docs/DIRECTION-NOW.md](./DIRECTION-NOW.md)**（四条目标收窄；**不是** #470 派工卡）。

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
CLAIM-WB-DEGREE-WEB: NO
```

## 三包状态（工程）

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
| **一 ENABLE** | 工程底座多包 READY · CLAIM 等业主 · **功能主线 = 计量 + 搜索 + 沙箱** |
| **二 加压** | 阶段一产品终签后 · 仍不默认开 MCP/Skill |

## 工程快照

| 项 | 值 |
|----|-----|
| 公网 tip | `GET /api/pico/tip` → 须 40 位实查（派卡时 `7608a45c…`） |
| multi-step 默认 | **pi-true** |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| drain | 45s inflight · grace 60s · **≠ 零中断** |
| 搜索 | gateway `web_search` / `web_fetch` · 老师可见来源链接或「未检索到可用来源」 |
| 沙箱 | S1 隔离+title/h1 · S2 同页光栅 PNG（[#513](https://github.com/juanwan99/pico/issues/513)） |
| CLAIM-WB | **NO** |

## 错误记忆

见 MEMORY-RESET：禁止 edu 串仓；禁止工程代签 CLAIM-WB YES；禁止把冻结 tip 当现网 tip；禁止把已关空壳 #468/#470 当现行双档主线。

## 真 Pi 核

| 项 | 值 |
|----|-----|
| multi-step 默认 | **pi-true**（`PICO_TRUE_PI_DEFAULT=1`） |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| 钉版 | `@mariozechner/pi-coding-agent@0.73.1` |
| CLAIM-WB | **NO** |
