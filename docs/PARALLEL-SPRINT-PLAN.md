# Pico 并行推进计划（体验主路径 · Skill 薄层 · M5 筹备）

```
DOC: docs/PARALLEL-SPRINT-PLAN.md
STATUS: BINDING-v2 · 业主 2026-07-30 确认跳过二审并授权开跑
          执行从 N1 夜卡开始；ADR-SKILL 仍为 N2 硬前置（N1 不依赖）
DATE: 2026-07-30
REPO: juanwan99/pico ONLY
LAW: docs/MVP-3DAY.md v1.2 FIXED（无授权不升 v1.3）
OS: docs/ONEFLOW.md
HARD_SCOPE: AGENTS.md — 永久禁止写 edu-cloud（M5 亦不例外）
PRIOR: docs/SPRINT-3DAY-PUSH.md（底座冲刺已收口）
REVIEW: Codex REVISE on PR #37 — 本版吸收全部 P0/P1
RELATED_ADR: docs/ADR-SKILL-CATALOG.md（必先读 · 唯一 Skill 目录）
DOC_INDEX: docs/README.md（真源索引 · 禁交接 MD）
NIGHT_POLICY: docs/NIGHT-CARD-POLICY.md（加厚 · 最短工时）
DAY_PARALLEL: docs/RACI-GROK-CODEX.md §2.1（日间能并行则并行）
N3_CARD: docs/archive/completed-tasks-2026-07/NIGHT-CARD-N3-THICK.md
```

## 0. 目标与非目标

### 目标（约 7～10 自然日 · BINDING 后才执行）

1. **主路径**体验可演示：无假按钮/闪黑/主路径断线（有界对标，**非**全面像素终局）。
2. **Skill 薄层**：在 **ADR 选定的唯一目录** 上，三类纵向闭环（chat / read / write→S7）+ Run 受控快照。
3. **M5 筹备**：方案 + 接口清单；**真连仅 = Pico 调 staging edu HTTP**，**永不写 edu 仓**。
4. **证据**：矩阵覆盖率与实现率分列；发布候选可收口。

### 非目标

- 写 **edu-cloud** 任何文件/PR/CI（**永久**；M5 授权不打开此门）
- 用户任意代码 Skill / 第二套并行 Skill 产品目录
- 未授权对 edu 的 live 调用
- 宣称全站 ±2px 或「全面对标完成」
- 升 v1.3、新壳、自动化引擎大扩建

### 共用底座（禁止再造）

```text
principal → Task / Run / Event / Artifact / Change
```

**三合流点：** `principal` · `Task` · `Change(S7)`。

### 完成度三列（禁止混谈）

| 指标 | 本冲刺目标 |
|------|------------|
| **全站路由与状态矩阵覆盖率** | **100%**（每屏有行；可 NO_REF） |
| **主路径实现率** | **100%**（§3.2 六步） |
| **其余页面实现** | **backlog / NO_REF**，不计入「冲刺完成」 |

完成定义使用 **□** 直到 BINDING 执行收口时再勾；草稿阶段不用 ☑ 假装已完成。

---

## 1. 并行轨道

| 轨 | 内容 | 写？ | 与谁并行 |
|----|------|------|----------|
| **W** | 主路径 + 矩阵脚手架 | 是 | S/E 文档/Q（路径隔离下） |
| **S** | Skill 薄层（ADR 后） | 是 | W（lease 外）；E 文档 |
| **E** | M5 文档；（授权后）Pico 侧 live 客户端 | 文档始终；代码仅 pico | 文档期全并行 |
| **Q** | 截图 artifact + 只读报告 + PR 评论 | **不写** MATRIX/PIXEL-DIFF 正文 | **始终** |

### 1.1 路径隔离 + 文件 lease

#### 默认分区

| 轨 | 默认可写 | 禁止 |
|----|----------|------|
| W | `apps/librechat/client/src/components/Workbench/**`（除 CapabilityHub 见 lease）、`Chat/**` 中非 Skill 绑定条、空态/路由、闪黑相关全局样式中的 **W 标注片段** | `services/orchestrator/**` Skill 注入核；Skill schema |
| S | `docs/skills/**` 或 ADR 指定目录、`docs/ADR-SKILL-CATALOG.md`、`services/api/**` skill 相关、`services/orchestrator/**` 注入、`packages/contracts/**` skill schema、`data-provider/pico/**` 中 skill API 客户端 | 大面积视觉重构、无关 Workbench 页 |
| E | `docs/M5-*.md`、`docs/PHASE3*`；（授权后）`edu_adapter.py`、settings 中 edu live **仅 pico 仓** | **任何 edu-cloud 路径**；未授权改默认 fake |
| Q | `screenshots/**`、`output/**`、PR/Issue 评论、只读 `docs/*-REPORT.md` | `docs/WORKBUDDY-*MATRIX.md`、`docs/PIXEL-DIFF.md` **正文**（只出附件，由合流人回填） |

#### 共享文件 lease（同时只允许一个写入窗）

| 文件 | 默认归属 | 合流单写窗 |
|------|----------|------------|
| `CapabilityHubPage.tsx`（及同目录技能 UI） | **S**（N2+） | N3 若 W 需改布局 → **仅 N3 合流负责人** |
| `ChatView.tsx` | **W**；S 仅 PR 级最小挂载点 | N3 合流 |
| `ChangeConfirmBanner.tsx` | **W** 修显示；S 仅 `requires_s7` 接线补丁 | 冲突则 N3 单写 |
| `data-provider/pico/api.ts` | **S** 加 skill 方法；W 不加无关 API | 串行 commit |
| `style.css` / 全局 tokens | **W** 主路径；S 禁止大改 | N3 |
| `docs/WORKBUDDY-SCREEN-MATRIX.md` 等 | **W** 建表与回填 | Q **禁止**直接改；Q 交截图路径列表 |
| `docs/PIXEL-DIFF.md` | **W** 或 N5 合流人 | Q 只附件 |
| `run_service.py` / `openai_compat.py` / `auth.py` | 谁改谁独占整窗；另一轨 WAIT | 总管指定 |

**规则：** 开写前在 PR 描述列 `LEASES: file=track`；发现双写立即停并 rebase。

### 1.2 单 Codex 时的并行含义

```text
日间：轨 A 短刀或 E 文档或 Q 只读
夜间 6h：轨 B 深挖（一夜一主轨）
总管：审查 / 合 main / 发次日卡
```

生产部署 **仅 N1 / N3 / N5** 夜末（或显式日间），降低重复 rebuild。

---

## 2. 日历（修正节奏）

| 日 | 日间 | 夜间 6h | 部署？ |
|----|------|---------|--------|
| **N0** | **修计划升 BINDING · Skill ADR · lease 表确认** | — | 否 |
| **N1** | 矩阵脚手架；Q 只读基线截图 | **W 主路径 P0** | **是** |
| **N2** | E 文档并行；S 测补 | **S 三类 Skill 纵向闭环** | 否（除非 API-only 急修） |
| **N3** | **共享文件单写合流** | **W 二三级诚实 + 矩阵回填** | **是** |
| **N4** | E 清单终稿；业主是否授 M5 | **授权→E 只读（仅 pico）**；**否则 S 扩预设** | 否 |
| **N5** | 彩排 | **三门禁 + P0 only** | **是** |
| **N6** | 缓冲 / 业主验收 | 可选 | 否 |

---

## 3. Track W — 主路径

### 3.1 矩阵（覆盖率 100%）

- `docs/WORKBUDDY-SCREEN-MATRIX.md`
- `docs/WORKBUDDY-INTERACTION-MATRIX.md`
- `docs/PIXEL-DIFF.md`（主路径优先；由 W/合流回填）

尺寸：主路径强制 1280 + 390；1440 尽力。

### 3.2 主路径 P0（实现率 100%）

1. 首页发起任务  
2. 执行中状态  
3. 右栏产物/预览  
4. S7 横幅  
5. 文件打开/下载/历史  
6. 项目内任务与资产  

验收：无 404/白屏/假按钮；刷新不闪黑不丢任务；桌面无横滚；移动核心可用；**不**要求全站像素完成。

---

## 4. Track S — Skill（唯一目录 · 见 ADR）

**硬前置：** `docs/ADR-SKILL-CATALOG.md` 合并结论前，**禁止**新建平行 `/v1/skills` 产品面。

### 4.1 原则（ADR 摘要位）

- LibreChat 已有 Skills UI/API → **产品目录只保留一套**（复用或明确隐藏一侧）。  
- Pico 账本保存 **受控 Skill 快照**（id/名/工具子集/风险），不双写两套运行时。  
- 全局工具白名单仍是上界；Skill 只能求交收窄。

### 4.2 N2 范围（防过载）— 仅 3 个纵向闭环

| id（例） | 类型 | 证明 |
|----------|------|------|
| `skill.chat` | chat | 无工具/极少工具 · 可聊 |
| `skill.read` | read | 只读工具子集 · 有引用或产物 |
| `skill.write_s7` | write→S7 | 提案 · 横幅 · 确认/拒绝 |

其余预设 → **N4b** 扩充，不进 N2。

### 4.3 验收

- 三技能可切换；Run 含受控快照  
- write 走 S7  
- 无第二产品目录；无扩大白名单  

---

## 5. Track E — M5

### 5.1 红线（P0）

```text
M5 授权开放的是：
  Pico 进程 → staging/production edu 的 HTTP/JWT 调用

M5 授权 绝不 开放：
  对 juanwan99/edu-cloud 的 clone 写 / PR / CI / merge
```

一切 edu 侧改动由 **edu 工作流 / 其他角色** 完成；Pico 代理人只改 **本仓**。

### 5.2 未授权

仅 `docs/M5-INTEGRATION-RUNBOOK.md`、`docs/M5-API-CHECKLIST.md`；生产 `fake` + handoff off。

### 5.3 授权后（仅 Pico 仓）

- 只读两工具真数 + 降级不静默假数据  
- 再 S7 handoff；change_id 一致  
- 嵌现有工作台，不造 edu 站  

---

## 6. Track Q

| 做 | 不做 |
|----|------|
| 截图到 `screenshots/` 或 `output/` | 直接改 MATRIX/PIXEL-DIFF 正文 |
| PR 评论证据表（路径列表） | 业务大改 |
| SELFTEST / 只读冒烟 | 与 W 抢矩阵编辑 |

矩阵回填：**W 或 N3/N5 合流人**根据 Q 附件一次写入。

---

## 7. 夜间 6h 卡（可复制 · 均含时间盒）

### 7.0 通用 HARD

```text
- 仅 juanwan99/pico；禁止写 edu-cloud（即使「M5 授权」）
- OneFlow；CI 红不合；禁 PROXY=1；禁暴露 18765/27017/8080；禁打印 key
- 不自 PASS 终局；不升 v1.3
- 一夜一主轨写代码；开写前列 LEASES
- 结束：报告模板 + push；部署仅当夜卡允许
```

### 7.1 夜卡 N1 · W 主路径 P0

```text
# N1 · 6h · W 主路径 P0 · 允许部署

H0–H0.5  fetch main；枝 grok/pico-w-mainpath；列 LEASES
H0.5–H1  主路径 6 步点通表（断点列表）
H1–H4    修闪黑/假按钮/404/右栏/S7/下载/项目任务回归
H4–H5    矩阵主路径行 + 截图路径（正文 W 写；可引用 Q 附件）
H5–H5.5  相关测/构建；PR；CI
H5.5–H6  合 main；生产对齐；冒烟 6 步；## DEPLOYED；报告

强制测：agent-selftest 或等价；浏览器 6 步
停止：主路径全 Y 或 6h 满且 CANDIDATE 清晰接手
禁止：全面像素、Skill 大改、edu、扩自动化

报告：SHA / 6 步 Y/N / 矩阵路径 / 截图 / LEASES / blockers
```

### 7.2 夜卡 N2 · S 三类 Skill 闭环

```text
# N2 · 6h · S 三类 Skill · 默认不部署（api 急修除外）

前置：ADR-SKILL-CATALOG 已合或同 PR 首段合并结论

H0–H0.5  main；枝 grok/pico-skill-thin；LEASES（api.ts / hub 归 S）
H0.5–H1.5  唯一目录接线（复用 LC 或 ADR 选定）；schema/快照字段
H1.5–H3.5  仅 skill.chat / skill.read / skill.write_s7 纵向
H3.5–H4.5  Run 快照 + 测（切换/隔离/S7）
H4.5–H5.5  UI 最小可选；浏览器三技能
H5.5–H6    PR；CI；合；报告（生产部署可留 N3）

强制测：pytest skill 相关 + S7 回归
停止：三技能闭环 Y；其余预设不进本卡
禁止：6+ 预设堆量、第二目录、扩大白名单、edu

报告：ADR 结论引用 / 三技能证据 / skill 快照 / SHA
```

### 7.3 夜卡 N3 · 合流 + 二三级诚实

```text
# N3 · 6h · 共享文件单写合流 + 二三级 · 允许部署

H0–H1    指定唯一合流人；merge main；锁定 lease 共享文件
H1–H3    合流 Skill 挂载 + W 布局；解决冲突
H3–H5    二三级入口：无 404/白屏/假按钮；空态；矩阵回填（含 Q 附件）
H5–H6    PR；CI；合；生产；冒烟主路径+三技能；DEPLOYED；报告

强制测：selftest + 主路径手点 + 三技能
停止：共享文件无双头；矩阵覆盖率朝 100%
禁止：新功能、edu、像素终局宣称
```

### 7.4 夜卡 N4a · M5 只读（仅业主书面授权 · 只改 pico）

```text
# N4a · 6h · Pico→staging edu 只读 · 禁止写 edu-cloud

前置：业主授权全文；staging URL/密钥在服务器 env 非聊天粘贴

H0–H1    开关与 runbook；确认 fake 非默认误开生产
H1–H4    JWT 验签路径；2 只读工具；跨校/过期；降级测
H4–H5    文档清单勾选；pytest
H5–H6    PR；CI；staging 验证报告；生产是否启用另令

禁止：写 edu-cloud；业务写；绕过 S7；生产默认真连未令
```

### 7.5 夜卡 N4b · Skill 扩充（无 M5 授权时默认）

```text
# N4b · 6h · 预设扩充到 8–10 + 失败态

H0–H1    main；仅 S lease
H1–H4    按 ADR 目录加预设；测
H4–H5    可选：组装草稿（提示词+工具子集，无代码）
H5–H6    PR；CI；合；报告

禁止：第二目录、edu、大视觉
```

### 7.6 夜卡 N5 · 三门禁

```text
# N5 · 6h · 发布候选 · 允许部署 · 禁止新功能

H0–H1    拉齐 main=预期 tip
H1–H3    功能门禁全表 + SELFTEST
H3–H4    视觉：主路径截图齐；矩阵覆盖率检查
H4–H5    生产门禁：端口、fake/live、SHA
H5–H6    只修 P0；文档完成度三列更新；DEPLOYED；验收包

停止：完成定义 □→执行后勾选；无新需求
```

---

## 8. N0 出门条件（升 BINDING 前）

```text
□ PARALLEL-SPRINT-PLAN 本 v2 被业主接受
□ docs/ADR-SKILL-CATALOG.md 合并（唯一目录结论）
□ 文件 lease 表无异议
□ AGENTS 导航标注 DRAFT 或已改 BINDING
□ STATUS 行改为 BINDING 的专用 commit
```

---

## 9. 完成定义（执行收口时再勾）

```text
□ 矩阵覆盖率 100%（允许 NO_REF 单元格）
□ 主路径实现率 100%
□ 三类 Skill 纵向闭环 + 无第二目录
□ M5 方案+清单在 main；未授权则无 live
□ 若授权：只读真工具在 pico 侧完成且未写 edu 仓
□ main=prod · SELFTEST · 端口安全
□ 未宣称全面像素完成 · 未写 edu-cloud
```

---

## 10. 风险

| 风险 | 缓解 |
|------|------|
| 双 Skill 目录 | ADR 强制唯一 |
| W/S 文件战 | lease + N3 单写 |
| Q 改矩阵 | Q 只附件 |
| N2 过载 | 仅 3 skill |
| M5 误写 edu | HARD 永久 pico-only |
| DRAFT 误执行 | 文首 DO NOT EXECUTE |

---

## 11. 请 Codex 再审时（v2）

1. P0 红线与 ADR 是否消除 BLOCKED？  
2. lease 是否可执行？  
3. N2 三分技能是否 6h 可行？  
4. 可否建议升 BINDING？  

---

## 12. 审查记录

| 日期 | 方 | 结论 | 变更 |
|------|-----|------|------|
| 2026-07-30 | Codex | REVISE（PR#37） | → 本 v2 |
| | Codex | 待再审 v2 | |
| 2026-07-30 | 业主 | 跳过二审 · 授权 BINDING · 备 N1 夜 | |

---

## 13. 进度日志

| 日期 | 事件 | 注 |
|------|------|-----|
| 2026-07-30 | v1 DRAFT | PR#37 |
| 2026-07-30 | v2 REVISE-applied | 仍 DO NOT EXECUTE |
| 2026-07-30 | BINDING-v2 | 业主授权；开 N1 |
| 2026-07-30 | N1 完成 | PR #41 · main 54595fe · 主路径 6/6 |
| 2026-07-30 | N2 卡发布 | docs/archive/completed-tasks-2026-07/NIGHT-CARD-N2-SKILL-THIN.md |
| 2026-07-30 | N2 完成 | PR #43/#44 · 972c426 |
| 2026-07-30 | 夜卡加厚策略 | NIGHT-CARD-POLICY + N3-THICK |
| 2026-07-30 | N3 #46 合 main | 条件通过；欠截图+DEPLOYED |
| 2026-07-30 | N4-THICK 卡发布 | 先还债再加厚 |
