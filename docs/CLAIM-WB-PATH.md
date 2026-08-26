# CLAIM-WB 路径（诚实 · 禁止代签）

```text
DOC: docs/CLAIM-WB-PATH.md
STATUS: BINDING 纪律
DATE: 2026-08-26
Issue: #449 CLAIM 材料 · #316 签章卡
业主签: YES · 2026-08-26 · tip dcb47c0059311c836960499b6f5d54207b9500bf
工程: 仍禁代签改口 · 本文不替业主再签
```

## 谁能签

| 角色 | CLAIM-WB |
|------|----------|
| **仅业主** | 可签 YES / 拒绝 / REVISE |
| 总管 / 写入 / 审查 / 测试窗 / 装订 | **禁止** 代签 YES |

## 材料包路径（#449）

| 项 | 路径 |
|----|------|
| **材料根** | [`docs/CLAIM-MATERIALS-2026-08/`](./CLAIM-MATERIALS-2026-08/) |
| 对比表 M1 | [`01-COMPARE-WB.md`](./CLAIM-MATERIALS-2026-08/01-COMPARE-WB.md) |
| 诚实限制 M2 | [`02-LIMITS-HONEST.md`](./CLAIM-MATERIALS-2026-08/02-LIMITS-HONEST.md) |
| 业主 5 题 M3 | [`03-OWNER-TRY-5.md`](./CLAIM-MATERIALS-2026-08/03-OWNER-TRY-5.md) |
| 证据图 M4 | [`04-EVIDENCE-MAP.md`](./CLAIM-MATERIALS-2026-08/04-EVIDENCE-MAP.md) |
| OWNER 模板 M5 | [`OWNER-DECISION-TEMPLATE.md`](./CLAIM-MATERIALS-2026-08/OWNER-DECISION-TEMPLATE.md) |
| 详规 | [`PLAN-PACK3-CLAIM-MATERIALS.md`](./PLAN-PACK3-CLAIM-MATERIALS.md) |
| 任务卡 | https://github.com/juanwan99/pico/issues/449 |

## 当前公网 tip（写文时须实查）

```text
业主 YES 绑 tip: dcb47c0059311c836960499b6f5d54207b9500bf
装订冻结 tip（= #448 终验 · 史料）: 502e1f6fd5d3f5999b43303de91b16de1375f26a
实查: GET https://pico.aivia.asia/api/pico/tip → git_sha 40 位
禁止死抄旧文
```

## 工程前置（已批 · 材料依据）

| 卡 | 结论 | 证据 |
|----|------|------|
| #447 | PACKAGE READY · UX-HARDEN | `docs/evidence/pack-ux-harden/` |
| #448 | PACKAGE READY · TRUE-PI-FINAL-MATRIX | `docs/evidence/pack-final-matrix/` |
| #449 | 装订 CLAIM 材料 · 业主 YES | 本路径 · OWNER DECISION 2026-08-26 |

## 仍欠项（材料装订后 · 产品终局）

```text
☑ 业主 ## OWNER DECISION · YES @ dcb47c00…（2026-08-26）
☑ CLAIM-WB-DEGREE-WEB: YES（诚实限制内 · 不等于桌面/连接器/MCP栈/跨会话记忆）
□ 挂起：记忆 · 人视角日用（业主令后面再做）
□ 黄债知情仍在：Y-w4-src · Y-w5-dense · Y-mono · Y-summary
□ drain ≠ 零中断 · 7 工具白名单 · 非桌面/非连接器
```

## 禁止句

```text
禁止: 工程 CI 绿 ⇒ CLAIM-WB YES
禁止: 账本 succeeded ⇒ 产品 Ready
禁止: 代理人写 CLAIM-WB: YES
禁止: PACKAGE READY · CLAIM-MATERIALS ⇒ 对外 100% WorkBuddy
```

## 允许句

```text
PACKAGE READY · CLAIM-MATERIALS（工程）
业主 OWNER DECISION YES @ 绑 tip（见上）
工程仍禁改口 / 再代签 YES
```
