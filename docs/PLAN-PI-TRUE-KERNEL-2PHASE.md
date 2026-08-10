# 计划 · 换真 Pi 核 · 两阶段

```text
DOC: docs/PLAN-PI-TRUE-KERNEL-2PHASE.md
STATUS: SUPERSEDED · 2026-08-10 · 阶段完成见 ADR Accepted / #435 CUTOVER / #436 HYGIENE
NOTE: 勿再以本文为默认=hosted 的施工真源；默认=pi-true · 回滚=HOSTED_LOOP
DATE: 2026-08-10
STATUS: 计划 · 阶段1执行中（#431）
基线 tip: 27954b2a59a5dcf8f5c57c1d51b176d205ff9e50
调查: docs/INVESTIGATE-PI-TRUE-KERNEL-2026-08-10.md · #430
讨论: #429
P5: PACKAGE READY · CLAIM-WB 与换核脱钩
CLAIM-WB: NO
```

---

## 目标

```text
生产 multi-step 从自研 pi_runtime（hosted loop）
→ 真 Pi harness（RPC sidecar）
Pico 保留：账本 · 门闩 · 人包 · 工具白名单 · 门脸
```

## 两阶段总览

| 阶段 | 卡 | 目标 | 默认路径 | 工期量级 |
|------|-----|------|----------|----------|
| **0** | 可并入阶段1 前序 | 正名 hosted loop | 不变 | 0.5–2 日 |
| **1** | **T-PACK-PI-TRUE-KERNEL-P1** (#431) | 薄桥 + 旁路双跑 | **仍 hosted** | 2–5 周 |
| **2** | T-PACK-PI-TRUE-KERNEL-P2（阶段1 READY 后派） | 切主 + 回归 + 退役 | **真核** | 2–5 周 |

## 不变量（两阶段共用）

I1 账本唯一 · I2 门闩不降级 · I3 人包 · I4 无公网 bash · I5 cancel/timeout 可测 · I6 可回滚 · I7 桥必须薄 · I8 密钥/端口纪律

## 阶段1 出口（摘要）

旁路交件绿 · 双跑无假绿 · 默认路径零回退 · 桥职责清单

## 阶段2 出口（摘要）

default 真核 · F 集无 P0 · 回滚演练通过 · 旧环 flag 退役

## 禁

讨论期/阶段1 切主 · 开放 shell · 桥内再造 agent OS · 自签 CLAIM-WB
