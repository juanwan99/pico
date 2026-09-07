> **真源 = GitHub Issue/PR/SHA/CI + 公网 tip。[`STATE-NOW.md`](./STATE-NOW.md) 三行与 [#634](https://github.com/juanwan99/pico/issues/634) 是索引。本页其余 = 目录。禁止新交接长文。**

**项目最高法律（禁止自搞一套 / 禁止重体系 / 只允许薄适配）：** [LAW-NO-SELF-BUILD-THIN-ADAPTER.md](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md) §0-supreme

# Pico documentation index

```
STATUS: BINDING navigation · 现况不在本页
TRUTH: GitHub (Issue/PR/SHA/CI/DEPLOY) + 公网 tip outrank all prose
NOW: GitHub 执行卡（最多 1）· docs/STATE-NOW.md 是索引
FREEZE: docs/TRUTH-FREEZE.md v1.8
```

## 现行层（2026-09-08 · 开窗只认这些句）

冲突时：**LAW ≥ 北极星 v1.4 ≥ TRUTH-FREEZE v1.8 ≥ 本页此表 ≥ 其它 md。** GitHub + tip 压过一切散文。

| 句 | 现行 | 作废（禁止再当现网） |
|----|------|----------------------|
| 产品 | 通用 LLM，用法 = Grok。主线 = 真 Word/Excel/HTML/PPT | 编程产品；教务 SaaS；场景考卷 |
| 编排 | 默认真 Pi（`health.default_runtime=pi-true`） | hosted `pi_runtime` 是默认；Kimi Agent 是唯一核 |
| 模型 | 聊天/出图统一 New API（`openai-responses` / Gemini 渠道）；对外只叫 Pico | 「DeepSeek 聊天核」当现网；为厂牌再造直连核 |
| 计量 | New API 管渠道/密钥/统计；Pico 记 `usage_events`→积分；edu 钱包只认 export | Pico 做钱；edu 另接模型第二账 |
| 办公天花板 | 隔离 `sandbox_office_lib`（python-docx / openpyxl / python-pptx）+ `read_office_skill` | spec / `generate_*` 是真源或上限 |
| 办公快路 | `generate_*` 仍常驻，**未退役** | 把调用面 PASS 说成老师聊天已走沙箱 |
| Pico 自己 | 账本、授权、门闩、人包、门脸 | 第二套 Agent OS / 办公 OS / PDF 核 / 发布通道 / 计费 OS |
| 工作法 | 本窗合一 · 只写 pico · live = origin/main | 主管/执行者编制 · docs-only 不部 |

`CORRECTED-GOALS.md`、`DAY-TASK-*`、`docs/archive/**`、过期 HANDOFF = 考古。CLAIMS 的 7 工具表是 2026-08-26 装订形状，不是现网 CORE。

## Do not

- Create extra **handoff / wave / status diary** Markdown. 现况入口 = [`STATE-NOW.md`](./STATE-NOW.md) + [#634 冻结令](https://github.com/juanwan99/pico/issues/634)。`HANDOFF-NEW-WINDOW-2026-08-23.md` **SUPERSEDED**。#573 已关。
- Treat anything under `docs/archive/` as current.
- Treat **#121 harness / multi-runtime** drafts as accepted architecture.
- Treat `DAY-TASK-*` / #310 / #627 / #628 / **#646** as current dispatch.
- Grow [`MEMORY-RESET.md`](./MEMORY-RESET.md) past archaeology; 经验只认 [`EXPERIENCE.md`](./EXPERIENCE.md)。
- Treat **`juanwan99/oneflow`** as BINDING（已 Archive）.
- Invent parallel `TRUTH.md` / `STEWARD.md` / 第二工具表文件名（逻辑认 edu，物理不复制）。

## Active documents (read in order when unsure)

| Priority | Path | Role |
|----------|------|------|
| **NOW** | **[STATE-NOW.md](./STATE-NOW.md)** | **开窗索引三行**（对不上以 GitHub + tip 为准） |
| **NOW** | **[#634](https://github.com/juanwan99/pico/issues/634)** | **冻结令** · 可钉现况三行评论 |
| 0 | **[DIRECTION-NOW.md](./DIRECTION-NOW.md)** | 北极星 §0-star v1.4 · 用法 = Grok · 办公主线 · 能力并列 · 办公计算机交成熟上游 |
| 0 | **[TRUTH-FREEZE.md](./TRUTH-FREEZE.md)** | 目标冻结 v1.8（真 Pi · New API 脑 · 办公快路未退役） |
| — | **[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)** | 产品定义（§4 实现以 tip 为准） |
| — | **[PLAN-WORKENV-UPSTREAM.md](./PLAN-WORKENV-UPSTREAM.md)** | 阶段方案：办公计算机交成熟上游 · 不要 bash · Pico 薄适配 · 验收看减法 |
| 0 | **[LAW-NO-SELF-BUILD-THIN-ADAPTER.md](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)** | 禁止自研 |
| 0 | **[ADR-CAPABILITY-LOADING.md](./ADR-CAPABILITY-LOADING.md)** | 能力加载纪律（少常驻 · Skill 渐进披露 · 禁自研选工具核）· 不当在飞 |
| 0 | **[EXPERIENCE.md](./EXPERIENCE.md)** | 经验唯一 · 按域 · 派发点名 ≤3 · 不是产品规格 |
| 0 | **[TOOLING-CATALOG.md](./TOOLING-CATALOG.md)** | 工具唯一 ID 表 |
| — | **[ADR-OFFICE-DOC-PIPELINE.md](./ADR-OFFICE-DOC-PIPELINE.md)** | 办公文档选型 · **spec 不是天花板**（v1.4 压过 8-26「spec 是真源」）· 不当在飞 |
| — | [MEMORY-RESET.md](./MEMORY-RESET.md) | 考古错误记忆 · 不当经验真源 |
| — | [HANDOFF-NEW-WINDOW-2026-08-23.md](./HANDOFF-NEW-WINDOW-2026-08-23.md) | **SUPERSEDED** · 不当现况 |
| — | [TASK-CARD-STANDARD.md](./TASK-CARD-STANDARD.md) | 卡面冻结 · 禁改形状 |
| — | [templates/dispatch-slip.md](./templates/dispatch-slip.md) | 派发条 |
| — | [ONEFLOW.md](./ONEFLOW.md) | 仓内适配 · 形状冻结 |
| — | GitHub PR/Issue/Actions | Task state & evidence |
| — | [AGENTS.md](../AGENTS.md) | 顶上冻结框为准；余为索引 |

下表旧文件全部 **索引/考古**，不当派工。TRUTH-FREEZE / WHAT-IS-PICO / FAST-PATH / VISUAL-GATE 仍可查，冲突时 **GitHub + 公网 tip 赢**。

## Historical (do not dispatch from)

| Path | Note |
|------|------|
| [SPRINT-3DAY-PUSH.md](./SPRINT-3DAY-PUSH.md) | COMPLETED |
| [DAY-TASK-2026-07-30-SKILL-UX.md](./DAY-TASK-2026-07-30-SKILL-UX.md) | completed |
| [DAY-TASK-P0-PI-CUTOVER.md](./DAY-TASK-P0-PI-CUTOVER.md) | **不当现况** |
| [EXECUTION-QUEUE.md](./EXECUTION-QUEUE.md) | SUPERSEDED |
| [CORRECTED-GOALS.md](./CORRECTED-GOALS.md) | 考古快照 · 文中 Kimi 优先句已废 · **勿当当前目标** |
| [HANDOFF-NEW-WINDOW-2026-08-23.md](./HANDOFF-NEW-WINDOW-2026-08-23.md) | SUPERSEDED |
| [archive/](./archive/) | Retired |

## Hygiene rule

禁止新交接长文。禁止把本索引当现况。三行跟本卡 PR 顺手刷，禁止只改 STATE-NOW 的独立 PR。

## Owner entry (2026-08-26)

**现况:** [STATE-NOW.md](./STATE-NOW.md)  
**冻结令:** [#634](https://github.com/juanwan99/pico/issues/634)  
**在飞:** 无  
**经验 / 工具:** [EXPERIENCE.md](./EXPERIENCE.md) · [TOOLING-CATALOG.md](./TOOLING-CATALOG.md)  
**北极星:** [DIRECTION-NOW.md](./DIRECTION-NOW.md) §0-star v1.4  
**冻结:** [TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.8  
**不当下一张:** #627 / #628 / #646 / 任何 DAY-TASK · 无业主点头不开办公减法卡
