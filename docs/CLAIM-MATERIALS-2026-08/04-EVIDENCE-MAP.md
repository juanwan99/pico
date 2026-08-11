# M4 · 证据链总图

```text
DOC: docs/CLAIM-MATERIALS-2026-08/04-EVIDENCE-MAP.md
DATE: 2026-08-11
终验 tip: 502e1f6fd5d3f5999b43303de91b16de1375f26a
CLAIM-WB: NO
```

## 1. tip 钉死

| 源 | 值 |
|----|-----|
| **公网 tip 装订日实查** | `502e1f6fd5d3f5999b43303de91b16de1375f26a` |
| tip URL | `https://pico.aivia.asia/api/pico/tip` |
| 响应摘要 | `ok=true` · `service=pico-api` · `git_sha=502e1f6…` |
| **#448 终验 tip** | `502e1f6fd5d3f5999b43303de91b16de1375f26a` |
| **对齐** | **一致 · 无漂移** |
| main 文档 tip 时 HEAD | `5f118b31a51365b3c15ebb6f886adb0e772e6fbd`（#453 证据合入；**行为 tip 仍以公网 502e1f6… 为准**） |

```text
材料包冻结 tip = #448 终验 tip = 公网装订日 tip
业主签 CLAIM-WB 时必须自己再查一次 40 位
```

---

## 2. 证据根

| 根 | 卡 | 主管结论 | MATRIX |
|----|-----|----------|--------|
| [`docs/evidence/pack-final-matrix/`](../evidence/pack-final-matrix/) | #448 T-PACK-TRUE-PI-FINAL-MATRIX | **PACKAGE READY · TRUE-PI-FINAL-MATRIX** | [MATRIX.md](../evidence/pack-final-matrix/MATRIX.md) |
| [`docs/evidence/pack-ux-harden/`](../evidence/pack-ux-harden/) | #447 T-PACK-UX-HARDEN | **PACKAGE READY · UX-HARDEN** | [MATRIX.md](../evidence/pack-ux-harden/MATRIX.md) |

---

## 3. 场景 → 路径速查

| 用途 | 路径 |
|------|------|
| T0 真核 | `pack-final-matrix/T0-env/` · `health-safe.json` |
| 六条 S1–S6 | `pack-final-matrix/six/1-open/` … `6-honest/` |
| W1 HTML | `pack-final-matrix/w1/` · **V3-open-product.png** |
| W2 写作多件 | `pack-final-matrix/w2/` |
| W3 办公表 | `pack-final-matrix/w3/` |
| W4 边界 | `pack-final-matrix/w4/` |
| W5 多文件 | `pack-final-matrix/w5/` · **V2-final.png** |
| 人交付 A1–A4 | `pack-final-matrix/human/` |
| 负例 | `pack-final-matrix/neg/under-deliver/` |
| 轻长链 ≥8 | `pack-final-matrix/long-or-session/` |
| 回潮 U1/U2 | `pack-final-matrix/regress-u1u2/` |
| 失败人话 | `pack-ux-harden/u1-fail-human/` |
| 双停止 | `pack-ux-harden/u2-dual-stop/` |
| U5 HTML/多文件/闲聊 | `pack-ux-harden/u5-*` |

---

## 4. 法律 / 路径 / 运维文档

| 文档 | 作用 |
|------|------|
| [`docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](../LAW-NO-SELF-BUILD-THIN-ADAPTER.md) | 禁自研 · 薄适配 |
| [`docs/TRUE-PI-BRIDGE-DUTIES.md`](../TRUE-PI-BRIDGE-DUTIES.md) | 7 工具桥职责 |
| [`docs/OPS-TRUE-PI-ROLLBACK.md`](../OPS-TRUE-PI-ROLLBACK.md) | HOSTED_LOOP 回滚 |
| [`docs/RUN-DRAIN-AND-STOP.md`](../RUN-DRAIN-AND-STOP.md) | drain 45s · 双停止 · 非零中断 |
| [`docs/CLAIM-WB-PATH.md`](../CLAIM-WB-PATH.md) | 谁能签 CLAIM-WB |
| [`docs/HANDOFF-WB-PI.md`](../HANDOFF-WB-PI.md) | 六条硬标准 |
| [`docs/PLAN-PACK3-CLAIM-MATERIALS.md`](../PLAN-PACK3-CLAIM-MATERIALS.md) | 本大包详规 |

---

## 5. PR 闭环（材料包依赖的已合工程）

| 卡 | PR | 说明 |
|----|-----|------|
| #447 | #450 RUN-DRAIN · #451 证据 | UX-HARDEN |
| #448 | #452 骨架 · #453 满配帧 | TRUE-PI-FINAL-MATRIX · 2.2–2.4 SKIP |
| #449 | PR-3.1 正文 · PR-3.2 索引 | 本材料包（纯文档） |

---

## 6. 工程仍欠（≠ 材料缺失）

```text
仅业主可签 CLAIM-WB YES
黄债未清零（Y-w4-src / Y-w5-dense / Y-mono / Y-summary）
B2 断点续跑 / 连接器 / MCP 市场 = 后置非本包
drain ≠ 零中断
```

```text
CLAIM-WB: NO
```
