# PLAN · 大包3 详规 · T-PACK-CLAIM-MATERIALS · #449

```text
DOC: docs/PLAN-PACK3-CLAIM-MATERIALS.md
DATE: 2026-08-11
STATUS: BINDING · 大包3 专章详规
Issue: #449
前置: #448 PACKAGE READY · TRUE-PI-FINAL-MATRIX（已批）
       #447 PACKAGE READY · UX-HARDEN（已批）
终验 tip 冻结建议: 502e1f6fd5d3f5999b43303de91b16de1375f26a（= #448 终验 tip · 开工重查；若漂必须说明）
角色: 执行者装订 L1 · 主管 L2 材料审 · 业主 OWNER DECISION
法律: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
CLAIM-WB: 工程全程 NO · 禁止代签 YES
```

---

## 0. 目标与非目标

### 目标

把 #447+#448 收成 **业主 30–60 分钟能审完** 的终包：

| ID | 内容 |
|----|------|
| **M1** | Pico Web vs WorkBuddy 教程路径 **对比表**（不弱/更强/边界）· 每格证据链 |
| **M2** | **诚实限制** 一页（含 #448 黄债 Y-w4-src / Y-w5-dense · drain 非零中断 · 7 工具桥等） |
| **M3** | **业主体验 5 题**（可复制题面 · 对齐 #448 开放域方向） |
| **M4** | tip 钉死 · `docs/CLAIM-WB-PATH.md` 复核/补链 |
| **M5** | Issue 模板：`## OWNER DECISION` · CLAIM-WB YES/NO @ 40位 tip |

### 非目标

```text
工程写 CLAIM-WB: YES
再开 W 终验大测（归已过 #448）
自研核 / 新功能开发（除材料笔误热修）
混 edu-core
```

### 工程回执只允许

```text
RECOMMENDATION: YES候选 | NO
CLAIM-WB: NO
等待: ## OWNER DECISION（仅业主）
```

---

## 1. Phase 0 · CLAIM + 冻结 tip

```text
CLAIM T-PACK-CLAIM-MATERIALS · Grok
确认 #448 主管 L2 READY
tip 实查 40 位 → 必须 = #448 终验 tip 或书面说明漂移
证据根仍有效: docs/evidence/pack-final-matrix/ · pack-ux-harden/
CLAIM-WB: NO
```

---

## 2. 阶段串行

| Phase | 名 | 产出 |
|-------|-----|------|
| 0 | CLAIM + 冻 tip | Issue 评论 |
| 1 | PR-3.1 材料正文 | 对比表+限制+5 题+证据指针 |
| 2 | PR-3.2 索引与模板 | STATE-NOW / CLAIM-WB-PATH / OWNER 模板 |
| 3 | 执行者大包 L1 | §6.2 |
| 4 | 主管 L2 | PACKAGE READY · CLAIM-MATERIALS |
| 5 | **停工等业主** | OWNER DECISION |

---

## 3. PR 切分（固定 2 槽）

| 槽 | 分支建议 | 内容 | 合入 L1 |
|----|----------|------|---------|
| **PR-3.1** | `docs/claim-materials-body-449` | 见 §4 正文规格 | 无 CLAIM-WB YES · 每格有指针 |
| **PR-3.2** | `docs/claim-materials-index-449` | STATE-NOW 钉 · CLAIM-WB-PATH 链 · OWNER 模板块 | 无代签话术 |

禁止第 3 主题功能 PR。笔误可小改 3.1。

### 怎么开

```text
git fetch origin main && git checkout -b <branch> origin/main
写文档 → push → gh pr create（含 L1）
关联 #449
CI 绿 → 合
无需 prod-update（纯文档）· tip 仍以公网终验为准
```

---

## 4. 正文规格（PR-3.1 强制文件）

```text
docs/CLAIM-MATERIALS-2026-08/
  README.md                 # 索引 · tip · 怎么读
  01-COMPARE-WB.md          # M1 对比表
  02-LIMITS-HONEST.md       # M2 诚实限制
  03-OWNER-TRY-5.md         # M3 五题
  04-EVIDENCE-MAP.md        # 证据链总表 → pack-final-matrix / pack-ux-harden
docs/PLAN-PACK3-CLAIM-MATERIALS.md  # 本详规入库
```

### 4.1 对比表（M1）最低列

```text
| 维度 | WorkBuddy 教程级期望 | Pico Web 现状 | 判定（不弱/更强/边界/弱） | 证据（帧/run/路径） |
```

至少覆盖：开放派活 · 多步工具 · 真文件 · 可改一版 · 完成态诚实 · HTML 可玩 · 多文件包 · 人交付。

### 4.2 诚实限制（M2）必须写

```text
- 非桌面 workDir / 非微信连接器 / 非 Remotion 成片（若适用）
- 工具白名单有限（桥薄适配 · 非法自研 MCP 栈）
- drain 降伤 ≠ 零中断；维护仍可能中断 run
- #448 黄债: Y-w4-src · Y-w5-dense · monologue 假阳
- 真核 tip · hosted loop 回滚开关存在
- CLAIM-WB 仅业主
```

### 4.3 业主体验 5 题（M3）

1. HTML 可玩小工具  
2. 多文件办公/项目包 ≥3  
3. 改一版跟进  
4. 边界/不能做的事（诚实）  
5. 闲聊无假成品  

### 4.4 证据图（M4）

```text
终验 tip → pack-final-matrix/MATRIX.md
体验硬钉 → pack-ux-harden/MATRIX.md
法律 → LAW-NO-SELF-BUILD-THIN-ADAPTER.md
路径 → CLAIM-WB-PATH.md
```

---

## 5. PR-3.2 索引规格

| 文件 | 动作 |
|------|------|
| `docs/CLAIM-WB-PATH.md` | 补「材料包路径 + 当前 tip + 仍欠=仅业主签」 |
| `docs/STATE-NOW.md` | 钉：三包状态 · tip · CLAIM-WB NO |
| `docs/CLAIM-MATERIALS-2026-08/OWNER-DECISION-TEMPLATE.md` | 见 §6.5 |

---

## 6. 审查标准

### 6.1 每 PR · 执行者 L1

```text
## 执行者自审 · L1 · PR-3.x · #449
SHA:
1) 范围仅材料/索引 · 无运行时泥球
2) 全文无工程写出的 CLAIM-WB: YES
3) 对比表每格有证据指针
4) 黄债与限制已写 · 未藏
5) tip 与 #448 终验一致或说明
6) CLAIM-WB: NO
结论: PASS · 请求合入
```

### 6.2 大包收口 · 执行者 L1

```text
## 执行者大包自审 · L1 · T-PACK-CLAIM-MATERIALS
tip 实查:
PR-3.1 #… · PR-3.2 #…
M1–M5 路径:
RECOMMENDATION: YES候选 | NO
CLAIM-WB: NO
请求: 主管 L2 · PACKAGE READY · CLAIM-MATERIALS
（不请求业主代签）
```

### 6.3 一票否决

```text
文中出现工程 CLAIM-WB: YES
无证据链空喊不弱
藏黄债 · tip 造假 · 扩 scope 再开发大功能
```

### 6.4 主管 L2

| 查 | 标准 |
|----|------|
| tip | = #448 终验或合理说明 |
| 材料齐 | M1–M5 |
| 无代签 | 搜 CLAIM-WB YES |
| 黄债 | 限制文是否包含 #448 Y-* |
| 结论 | READY 材料包 或 REVISE |

主管 **不** 代替业主点 5 题、**不** 写 CLAIM-WB YES。

### 6.5 业主模板

见 `docs/CLAIM-MATERIALS-2026-08/OWNER-DECISION-TEMPLATE.md`（贴 #449 或 #316）。

---

## 7. 时间盒

**2–4 日**（装订 1–2 · 索引 0.5 · 自审+主管 0.5–1 · 等业主另计）。

---

## 8. 出口

```text
□ M1–M5 在仓
□ 执行者 L1 齐 · 主管 PACKAGE READY · CLAIM-MATERIALS
□ RECOMMENDATION 已写 · CLAIM-WB 仍 NO
□ 等待 OWNER DECISION
```

---

## 9. 成功总定义（产品）

```text
PACKAGE READY · CLAIM-MATERIALS
+ 业主 CLAIM-WB: YES @ tip
= 可宣称档（诚实限制内）
仅材料 READY 无 YES = 工程完成 · 产品未终局
```
