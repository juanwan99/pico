# CLAIM 材料包 · 2026-08

```text
DOC: docs/CLAIM-MATERIALS-2026-08/
CARD: T-PACK-CLAIM-MATERIALS · #449
DATE: 2026-08-11
装订: Grok
终验 tip（冻结）: 502e1f6fd5d3f5999b43303de91b16de1375f26a
前置: #447 PACKAGE READY · UX-HARDEN
       #448 PACKAGE READY · TRUE-PI-FINAL-MATRIX
法律: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
CLAIM-WB: NO · 工程禁止代签 · 仅业主可写 YES
```

## 一句话

把 #447 + #448 收成 **业主 30–60 分钟能审完** 的终包：对比表、诚实限制、可复制 5 题、证据链、OWNER DECISION 模板。

**本目录 = 工程装订材料。不等于 `CLAIM-WB: YES`。**

## 公网 tip（须自查）

```text
GET https://pico.aivia.asia/api/pico/tip
期望 git_sha = 502e1f6fd5d3f5999b43303de91b16de1375f26a
（装订日实查 ok=true · service=pico-api · 与 #448 终验一致 · 无漂移）
```

若公网 tip 已漂：先停签、对照证据目录标注 tip、再决定是否复测。

## 怎么读（建议顺序）

| 序 | 文件 | 内容 |
|----|------|------|
| 1 | [01-COMPARE-WB.md](./01-COMPARE-WB.md) | **M1** Pico Web vs WorkBuddy 教程级对比表（每格证据） |
| 2 | [02-LIMITS-HONEST.md](./02-LIMITS-HONEST.md) | **M2** 诚实限制 + #448 黄债 |
| 3 | [03-OWNER-TRY-5.md](./03-OWNER-TRY-5.md) | **M3** 业主体验 5 题（可复制题面） |
| 4 | [04-EVIDENCE-MAP.md](./04-EVIDENCE-MAP.md) | **M4** 证据链总图 · tip · 路径 |
| 5 | [OWNER-DECISION-TEMPLATE.md](./OWNER-DECISION-TEMPLATE.md) | **M5** 业主签 CLAIM-WB 模板（仅业主） |

详规：[`docs/PLAN-PACK3-CLAIM-MATERIALS.md`](../PLAN-PACK3-CLAIM-MATERIALS.md)  
纪律：[`docs/CLAIM-WB-PATH.md`](../CLAIM-WB-PATH.md)  
状态钉：[`docs/STATE-NOW.md`](../STATE-NOW.md)

## 工程回执口径（装订方）

```text
RECOMMENDATION: YES候选 | NO
CLAIM-WB: NO
等待: ## OWNER DECISION（仅业主）
```

禁止：

```text
工程写出 CLAIM-WB: YES
CI 绿 / 账本 succeeded 冒充产品 Ready
无证据空喊「不弱 WorkBuddy」
藏黄债 · tip 造假
```

## 成功总定义（产品）

```text
PACKAGE READY · CLAIM-MATERIALS（工程）
+ 业主 CLAIM-WB: YES @ tip
= 可宣称档（诚实限制内）

仅材料 READY 无 YES = 工程完成 · 产品未终局
```

## 证据根（只读指针 · 本包不重测）

| 根 | 卡 | 说明 |
|----|-----|------|
| [`docs/evidence/pack-final-matrix/`](../evidence/pack-final-matrix/) | #448 | 真核终验 T0–T6 · W1–W5 · 人交付 · 负例 |
| [`docs/evidence/pack-ux-harden/`](../evidence/pack-ux-harden/) | #447 | U1 失败人话 · U2 双停止 · U5 回归 |

审查必须 **读图**；只读本 README = 审查无效。
