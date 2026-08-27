# ADR · 能力加载与后续开发纪律

```text
DOC: docs/ADR-CAPABILITY-LOADING.md
ID: ADR-CAPABILITY-LOADING
DATE: 2026-08-27
STATUS: Accepted · 业主令：先纪律后能力；有成熟做法不自研
CLAIM-WB: 不改签（已 YES · 本 ADR 不代签）
REPO: juanwan99/pico ONLY
LAW: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok
目录: docs/ADR-SKILL-CATALOG.md（唯一 Skill 面 = LibreChat Skills）
现况: docs/STATE-NOW.md · 本 ADR 是加载纪律真源，不是在飞卡
```

---

## 0. 一句话

```text
老师不选工具。模型看原话 + 说明自己调。
常驻少动词；Skill 先目录后全文。
有成熟上游只薄适配。禁止自研选工具核、插件墙、场景路由。
先立本页，再加结构图 / 生图档 / 润色。
```

对标 **Anthropic Agent Skills 渐进披露**、**Pi 小工具面 + 按需 Skill**、**Codex Skill 目录预算**。  
不跟 ChatGPT 第一代插件商店，不跟全量 MCP 倒进上下文，不跟飞象「一进页就做课件」。

---

## 1. 顺序（不许颠倒）

1. **本页纪律**（本 ADR）。  
2. **按第 2 节收常驻、改 Skill 加载**（薄适配，不新开核）。  
3. **再**加隐性能力：结构图、生图档、润色等。

未做 1–2 不准「尽量加很多 Skill / 插件」。

---

## 2. 加载三层（偷形状，不自研核）

| 层 | 是什么 | 对标 | Pico 怎么接 |
|----|--------|------|-------------|
| **常驻** | 每轮都在模型眼前的动词 | Anthropic：最常用 3–5 个永远加载；业界：常驻过 15 易乱调 | 目标：少数字（读/写、交 HTML/Office、出图、日后一张结构图）。润色默认不是工具。多了 **合并**，不新开调度器 |
| **Skill 目录** | 每条只挂 **名字 + 一句何时用** | Agent Skills 第一层；Codex 目录约占上下文 ≤2% | 唯一目录 = LibreChat Skills。老师可不点；`$` 是高手出口。禁止第二商店 |
| **Skill 全文** | 对上了才读 `SKILL.md` 与附件 | 渐进披露第二/三层 | Skill **只能收窄** 白名单。禁止把 `skill-deliverable` 那种长说明书每轮灌进 |

工具说明必须写 **做什么 + 何时用**。那就是路由，Pico 不写 `if 课件 then …`。

延后加载 / `tool_search` 是 Claude API 能力。Pico 的 Pi **没有**就不要自研同款核。工具未到上百，先靠「少常驻 + Skill 目录」。

---

## 3. 准入（加任何能力先过这四问）

```text
1. 老师不可见菜单？（隐性 = 默认；限额可以看见）
2. 旧动词加参数 / 一篇 SKILL.md / 不得已才新动词？
3. 新动词能进 gateway 白名单？扩名单须 ADR；禁公网 bash
4. 适配哪段上游？升级是否只改适配层？
```

| 隐性能力 | 默认长在 | 不要拆成 |
|----------|----------|----------|
| 结构图 | 一个 `generate_diagram`（或先聊天 \`\`\`mermaid） | mermaid + d2 + 脑图 三个工具 |
| 示意图 / 照片 | `generate_image`（档是参数） | 每厂一个工具 |
| 教材页 | `generate_html_document` | 壳工具 + 贴图工具 |
| 润色 | **模型自己写** | `optimize_text` |

---

## 4. 禁止

- 自研选工具核 / RAG-MCP OS / 第二套编排  
- 全量 MCP schema 每轮倒进上下文；插件市场当老师主路径  
- 第二套 Skill 浏览目录（[`ADR-SKILL-CATALOG`](./ADR-SKILL-CATALOG.md)）  
- 读正文猜任务、`force_agent`、词表焊工作流（[`DIRECTION-NOW`](./DIRECTION-NOW.md) §0-star）  
- 把 Manus「说目标就当员工做完」设成默认（问句只解释）  
- 用本 ADR 当在飞卡或替 CLAIM-WB 改签

---

## 5. 现况缺口（本页不改代码）

- 桥上常驻工具已偏多，schema 每轮全挂。  
- `skill-deliverable` 长指令每轮灌进，与渐进披露相反。  
- 仓内已有场景 Skill 苗头（教案/出题）；须保持「不自动套用」，禁止再铺成默认工作流。

收口另开实现切片，遵守本页，不另造核。

---

## 6. 冲突

```text
LAW ≥ 本 ADR ≥ 任务卡便利
北极星 §0-star 压过「必须交件」
业主当次书面 > 本文，但必须改本文或出豁免
```
