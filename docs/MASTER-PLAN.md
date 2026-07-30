# Pico 总体规划（MASTER PLAN）

```
DOC: docs/MASTER-PLAN.md
STATUS: WORKING · 执行导航（不升格替代 MVP-3DAY v1.2）
DATE: 2026-07-30
REPO: juanwan99/pico ONLY
PLAN_LAW: docs/MVP-3DAY.md v1.2 FIXED（无业主授权不升 v1.3）
BRANCH: grok/pico-preview-librechat-p0 → main（CANDIDATE · 不自 PASS · 值守合）
RELATED:
  - docs/ONEFLOW.md（执行操作系统）
  - docs/SPRINT-3DAY-PUSH.md（3 日加速收口）
  - docs/CORRECTED-GOALS.md
  - docs/MVP-3DAY.md
  - docs/PHASE2-CONTRACTS.md / docs/PHASE3-INTEGRATION.md
  - docs/OVERALL-ARCHITECTURE.md
  - docs/PIXEL-FIRST.md / docs/PIXEL-DIFF.md
SOURCE_READ (edu, read-only):
  - edu-cloud docs/SYSTEM-REQUIREMENT.md §0（AI 底座设计锚点）
  - 业主口径：edu 原通用 AI 代码几乎全部废除；Pico 接棒 AI 底座
```

---

## 0. 一页结论

| 项 | 拍板 |
|----|------|
| **产品** | 学校场景可用的 **AI 工作台**（对话 + Agent + 产物 + 唯一 AI 账本 + 模型 HTTPS） |
| **壳** | `apps/librechat`（MIT）；禁止恢复 web/nextchat/workbench；禁止拆闭源 WorkBuddy |
| **底座主权** | **Pico = 唯一 AI 过程真源**；**edu = 唯一业务数据真源** |
| **edu AI** | 原通用 AI 路线 **废除**；对接后 edu 侧旧 AI 入口/平行账本 **退役**，禁止双跑 |
| **前端像素** | **冻结为演示可用**；仅 bugfix + 业主定点观感；不宣称 100% 叠图完成 |
| **当前生产** | https://pico.aivia.asia · 热更新已通 · 登录/真聊/产物已验 |
| **工程主线** | 冻体验 → 清残留 → **钉底座主链** → 对接桩 → CI/审查/值守合 →（授权后）真联调 edu |
| **不做** | 写 edu-cloud；自 PASS；无人合 main；PROXY=1；公网暴露 18765/27017/8080 |

**一句话：**  
Pico 已具备可演示工作台；后续以 **AI 底座契约与账本主链** 为中心，把 edu 设计中的「执行底座」做成 **唯一实现**，而不是继续堆 UI。

---

## 1. 双系统终局分工（设计）

来自 edu `SYSTEM-REQUIREMENT` §0 + Pico CORRECTED-GOALS：

```text
┌─────────────────────────────────────────────────────────┐
│  教师 / 管理者                                            │
│  工作台 UI（Pico · LibreChat 等）                          │
└───────────────────────────┬─────────────────────────────┘
                            │ JWT principal + HTTPS
┌───────────────────────────▼─────────────────────────────┐
│  PICO = AI 底座                                           │
│  · Task / Run / Event / Artifact（唯一 AI 账本）          │
│  · OpenAI 兼容 + pico-agent 工具环 + Kimi HTTPS           │
│  · S7 Change 提案（不静默写业务）                         │
│  · 白名单工具 / FakeEdu→live 适配位                       │
└───────────┬─────────────────────────────┬───────────────┘
            │ 只读/受控 Capability          │ 已确认 Change
            ▼                             ▼
┌───────────────────────┐   ┌─────────────────────────────┐
│  EDU = 业务操作系统    │   │  EDU Review / Commit        │
│  学籍班课考成绩权限…  │   │  业务库原子写入 + 审计       │
│  唯一业务真源          │   │  （Pico 不落成绩主库）       │
└───────────────────────┘   └─────────────────────────────┘
```

### 1.1 协作主线（必须同一条链）

```text
目标 → Context → Task/Run/Event → Change → Review/Checks → Commit → History
```

### 1.2 底座最小验收闭环（edu 设计口径 · 在 Pico 落地）

```text
带 membership 的身份
  → 受控读（工具/引用）
  → AI 执行并记账（Pico）
  → 可见产物 / 可见变更提案
  → 人确认
  → （对接后）edu 原子提交业务
  → 可查询历史
```

---

## 2. 现状快照（2026-07-30 · 诚实）

### 2.1 已具备（演示级 · 非 PASS）

| 域 | 状态 |
|----|------|
| 公网 HTTPS 产品入口 | 有（Nginx → LibreChat；API/Mongo 不暴露） |
| 登录 + 真聊（Kimi） | 有 |
| 产物进结果区 | 有（含流式 finalize 修复） |
| 工作台 IA / 二级入口 | 有（clean-room；像素未 100% 叠图） |
| Task/Run/Artifact/S7 API | M2 已收口；流式终态、幂等、下载、隔离与同 change id 路径有测并经生产抽检 |
| M3 对接桩 | 已就绪；默认 fake、handoff 关闭，live 缺配置 fail-closed |
| Phase2 合同文档 | FROZEN v1.0 |
| 热更新 / 生产 SHA stamp | 有 |
| edu 真联调 | **无**（edu tip 亦未见 pico 桥代码） |
| S8 合 main | **未**（CANDIDATE 纪律） |

### 2.2 已知张力

1. **双 AI 账本风险：** edu 仓内仍有过渡性 `ai_foundation` 等实现；终局必须 **Pico 独占 AI 过程账本**，edu 通用 AI **废**。  
2. **壳 vs 核：** LibreChat Mongo 会话 ≠ 业务/AI 真源；必须持续 rebind 到 Pico Task。  
3. **像素：** 无业主同尺寸参考图则不得宣称 ±2px 完成。  
4. **计划法：** 本 MASTER 只导航执行，**不修改** MVP v1.2 成功标准字母（S1–S8）。

---

## 3. 阶段总览

| 阶段 | 名称 | 目标 | 出门标准（摘要） |
|------|------|------|------------------|
| **M0** | 体验冻结 | 停止无界 UI 扩张 | 冻结声明 + 仅 bugfix |
| **M1** | 清残留 | 单一产品叙事与死代码清扫 | DEAD-CODE-SWEEP + 构建/自测绿 |
| **M2** | 底座主链 | 租户→Task→Run→Artifact→S7 硬 | 回归矩阵 + 自测扩展全绿 |
| **M3** | 对接桩 | pico 侧合同可插 edu | fake/live 边界清晰；无真连依赖 |
| **M4** | 候选发布 | CI + 审查 + 值守合 main | S8；不自 PASS |
| **M5** | 真联调 edu | 授权后双仓 | token/工具/Change/退役；**另窗** |

**当前快照：M2（含 S7）与 M3 对接桩已完成 3 日冲刺收口；不代表产品终局 PASS。**
M5 **禁止**在本规划下自动开工（需业主点名 + 可能升计划）。

---

## 4. 阶段细则

### M0 — 体验冻结（立即）

| 项 | 内容 |
|----|------|
| 允许 | 登录/聊天/产物/安全/横滚等 **P0 bug**；业主点名的单屏观感 |
| 禁止 | 新模块、自动化引擎膨胀、全面像素战役、换壳 |
| 文档 | PIXEL-DIFF 保留缺口诚实段；不写「100% 完成」 |
| 生产 | tip 与 health git_sha 一致；rebuild 前端纪律不变 |

### M1 — 清残留

| 清扫类 | 示例 |
|--------|------|
| 旧壳回潮 | apps/web、nextchat、workbench 路径/文档/脚本 |
| 错误拓扑 | 27017 当产品、API 当首页、废隧道 URL |
| 双叙事 | Mongo=AI 真源、edu 双跑鼓励语 |
| 死代码 | 无路由组件、无引用脚本、过期 HANDOFF 冲突段 |

**纪律：** 先 `rg` 断引用 → 删 → `scripts/agent-selftest` / unit。  
**产出：** `docs/DEAD-CODE-SWEEP.md`。

### M2 — 底座主链（工程核心）

按优先级（不可颠倒重要性）：

| ID | 能力 | 完成定义 |
|----|------|----------|
| **B1** | Membership 隔离 | 跨校/跨人读写 fail-closed；claims 同形 |
| **B2** | Task↔Convo 绑定 | pending rebind 可靠；UI 状态读 Pico Task |
| **B3** | Run 生命周期 | 流式/非流式同一 finalize；状态条一致 |
| **B4** | Artifact | 右栏 + 我的文件；打开/下载 |
| **B5** | S7 | 提案→确认/拒绝→审计与 UI 同对象 |
| **B6** | 工具白名单 + FakeEdu | 形状稳定；跨校拒绝 |
| **B7** | 模型通道 | 密钥仅服务端；chat vs pico-agent 诚实 |

**M2 出门门禁（建议）：**

```bash
# 本地/CI
bash scripts/agent-selftest.sh   # 含 S1/S2/S7/artifact/isolation
pytest -q tests/unit
# 生产抽检（Codex/值守）
登录 · 真聊 · 产物 · S7 横幅路径 · 端口安全
```

### M3 — 对接桩（仍只写 pico）

| 项 | 说明 |
|----|------|
| JWT | 验 edu 同形 claims；测试签发与生产开关分离 |
| `PICO_EDU_MODE` | fake 默认；live 仅配置，不默认真连 |
| Change 外发形状 | 对齐 `contracts/change-handoff.md`（可先空适配/记审计） |
| 文档 | PHASE3 checklist 与现网 env 一致 |
| **禁止** | 改 edu 仓；把 edu 当日常 CI 依赖 |

M3 桩已就绪：Pico 默认 fake，live 配置缺失时 fail-closed；真实 edu 联调后置。

### M4 — 候选发布（S8）

```text
CANDIDATE + 40字 SHA → CI 全绿 → 独立审查 → 值守合 main
```

- 不自 PASS  
- 合并说明引用本 MASTER 阶段完成证据  
- 生产继续 host 网络安全绑定（API 127.0.0.1）

### M5 — 真联调 edu（后置 · 需授权）

| 步 | 内容 | 仓 |
|----|------|-----|
| 1 | edu 签发 Pico token | edu |
| 2 | live 班级等工具 | 双 |
| 3 | Change → edu Review 队列 + callback | 双 |
| 4 | `PICO_AI_PRIMARY`：edu 旧 AI **410/退役** | edu |
| 5 | 关闭 Pico 测试签发器（生产） | pico |

**成功：** 无双 AI 账本；一条业务链可演示「提案→教务确认→库事实」。

---

## 5. 工作流与角色

**操作系统：** 自 2026-07-30 起默认走 **Pico OneFlow** — [`docs/ONEFLOW.md`](./ONEFLOW.md)  
（CANDIDATE→CI→审查→MERGED→DEPLOYED 闭环；禁止 CI 红合 main。）


| 角色 | 职责 |
|------|------|
| **业主** | 目标、例外授权、视觉终裁、是否开 M5/升 v1.3 |
| **Grok-Pico（本类窗）** | 规划、底座/API/自测、文档、分支推送；**不写 edu** |
| **Codex（本机/VPS）** | 公网验收、热更新、截图、生产 rebuild |
| **独立审查** | PASS/REVISE/BLOCKED；写入者不可自签 |

**窗口纪律（吸收 edu AGENTS 内核）：**

- 一切片一分支一 PR 意图；CANDIDATE；不自 PASS  
- GitHub 为代码事实；运行事实 digests/自测/公网抽检  

---

## 6. 风险与红线

| 红线 | 说明 |
|------|------|
| 双 AI 真源 | 禁止 Pico + edu 同时长期写 Run 账本 |
| 静默写业务 | 禁止无 S7/无 edu Commit 改成绩等 |
| 密钥 | 禁止聊天/日志打印 Kimi key；建议轮换曾暴露 key |
| 网络 | 禁 PROXY=1；禁公网 DB/API |
| 范围 | 禁 edu 写；禁换壳；禁拆 WorkBuddy |
| 计划 | 禁擅自升 v1.3 |

| 风险 | 缓解 |
|------|------|
| LibreChat 升级冲掉定制 | 窄 diff；关键路径有测/文档 |
| 流式产物回归 | finalize 单测 + 公网抽检 |
| 合同漂移 | Phase2 FROZEN；破字段要 version bump |
| 像素争论拖死底座 | M0 冻结；观感争议单开定点 |

---

## 7. 近端切片队列（派工用）

| 序 | 切片 | 建议执行方 | 出门 |
|----|------|------------|------|
| 1 | M0 冻结声明 + 分支 tip 记录 | 文档/任一 | 本文 + CANDIDATE 注记 |
| 2 | M1 死代码/文档清扫 | Grok 或 Codex | DEAD-CODE-SWEEP |
| 3 | M2-B2/B3/B4 绑定与产物矩阵 | Grok 主 + Codex 公网 | selftest 扩项 |
| 4 | M2-B5 S7 UI↔API | Grok | 确认/拒绝证据 |
| 5 | M2-B1 隔离加固 | Grok | isolation 测 |
| 6 | M3 对接桩与文档 | Grok | 无真连仍可 demo |
| 7 | M4 CI/审查/值守合 | 人 + CI | main 前进 |
| 8 | M5 真联调 | **授权后** 双仓 | 退役 edu 通用 AI |

---

## 8. 成功标准映射（不改 v1.2 字母）

| v1.2 | 与本 MASTER |
|------|-------------|
| S1 真模型流式 | 保持；生产持续抽检 |
| S2 pico-agent 工具环 | M2-B6/B7 |
| S3 唯一 AI 账本 | M2 全章 + 反双跑 |
| S4 短时凭证同形 | M3 JWT |
| S5 产品 UI 接通 | **M0 冻结为已演示**；其后仅回归 |
| S6 ≥2 工具 + FakeEdu | M2-B6 |
| S7 人确认 | M2-B5 |
| S8 CI+审+合 | M4 |

---

## 9. 明确不在本规划主线

- 全面像素 100% / 无参考图叠图认证  
- 企微遥控、桌面全盘、排课 OR-Tools 引擎  
- 定价点池完整计费工程（方案在 OVERALL-ARCHITECTURE，工程后置）  
- 多校 Dedicated 单元  
- 在 edu 继续扩建通用 Agent  

---

## 10. 维护规则

1. **MVP-3DAY v1.2** 仍是计划法；本文件是 **执行导航**，冲突时以 v1.2 HARD + CORRECTED-GOALS 为准。  
2. 阶段完成时在本文件 §2 现状表追加一行日期与 tip SHA（短更新，不另起浪潮文档）。  
3. 升 v1.3 或开 M5 真联调：**仅业主书面/当轮明确授权**。  
4. 不自 PASS；合并须值守。

---

## 11. 当前建议「下一刀」

**若处于 3 日冲刺：** 以 [`docs/SPRINT-3DAY-PUSH.md`](./SPRINT-3DAY-PUSH.md) 为准，覆盖本节默认下一刀。

## 11b. 默认下一刀（非冲刺时）

1. **采纳本 MASTER 为执行导航**（本文入库）。  
2. 执行 **M1 清残留**（小 PR/连续 commit）。  
3. 并行或紧随 **M2-B2～B4**（绑定 + Run + 产物）压实。  
4. 前端除 P0 外 **停手**。  
5. **不**启动 edu 联调，直至 M2 出门 + 业主点 M5。

```
未合 main · 未自 PASS · 前端不宣称像素 100% · 不写 edu-cloud
```
