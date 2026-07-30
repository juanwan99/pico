# Pico 主线校准（深度排查 · 剔除过时记忆）

```
DOC: docs/CALIBRATION-NOW.md
STATUS: CALIBRATION SNAPSHOT（写入窗自查，非 PASS）
DATE: 2026-07-30
BRANCH: grok/pico-preview-librechat-p0
TIP: 7f63ec78d8df9c06dc21b4b9d75e787810109359
MAIN: 4b92a83…（本分支领先 main 约 36 commits，未值守合入）
REPO: juanwan99/pico ONLY
PLAN: docs/MVP-3DAY.md v1.2 FIXED（无授权不升 v1.3）
AUTHORITY: VERDICT_AUTHORITY NONE — 本页不自 PASS
```

> **用法：** 本页覆盖会话碎片记忆与部分旧交接句。  
> 与 `CORRECTED-GOALS.md` / `AGENTS.md` 冲突时 → **HARD 范围与 v1.2 成功标准仍以 FIXED 文档为准**；  
> 与 `HANDOFF.md` 冲突时 → **以本页 + CORRECTED-GOALS 为准**（HANDOFF §3/§5/§6 多处已过时）。

---

## 1. 主线一句话（仍有效）

**Pico = 学校场景可用的 AI 工作台底座**  
（对话 + Agent 编排 + 产物 + **唯一 AI 账本** + 模型 HTTPS API）

| 是 | 不是 |
|----|------|
| WorkBuddy / Claude / Codex **品类**任务台 | 网盘主产品 |
| LibreChat MIT 壳 + Pico 核 | 自研三栏 / NextChat 默认壳 |
| Kimi API + 钉版本 Kimi Agent | 自研 Agent OS / 默认本地 GPU |
| Phase 1 独立交付 | 本窗写 edu-cloud / 以联调 edu 为门禁 |

---

## 2. HARD 边界（永久 · 勿淡化）

1. **只写** `juanwan99/pico`；禁止 edu-cloud 任何写/PR/CI/合。  
2. **唯一 AI 真源** = Pico 账本；禁止与 edu AI **双跑**。  
3. **壳** = `apps/librechat`；**已删且禁止回潮**：`apps/web` / `apps/nextchat` / `apps/workbench`。  
4. **禁止**拆闭源 WorkBuddy；只可 clean-room 参考公开 IA。  
5. **不自 PASS**；CANDIDATE + 40 字 SHA → CI → 审 → **值守**合 main。  
6. **计划** v1.2 FIXED；无业主授权不升 v1.3。  
7. Shell/File/Web/MCP **默认关**（allowlist 白名单）。  
8. 商业定价 **未 FIXED**；勿锁死单价叙事。

---

## 3. 运行拓扑（本沙箱实测 · 2026-07-30）

| 面 | 绑定 | 实测 |
|----|------|------|
| 产品 UI | **0.0.0.0:8080**（mirror → LibreChat :3080） | **200** HTML，`lang=zh-CN`，含「Pico 正在加载…」 |
| LibreChat | :3080 | **200** /health |
| Pico API | **127.0.0.1:18765 only** | health ok；`git_sha` 与 tip 一致 |
| Mongo | 127.0.0.1:27017 | 连通（LibreChat 会话） |
| 预览代理 | :6014 | **403 + body 长度 0**（无 preview-auth 时） |
| 控制面 pin | :6015 | 端点行为因版本而异；须 pin **8080** |

**白屏正确记忆（再确认）：**

| 对照 | 结论 |
|------|------|
| 直连 8080 | 产品 UI **正常** |
| 走 6014 无鉴权 | **空 body = 纯白** → **Preview 层**，非「API 没写」 |
| **禁止** | 因白屏立刻换壳；只 curl 8080 就对用户说「预览好了」；设 `PROXY=1` |

演示登录：`teacher@example.com` / `pico-demo-123`

---

## 4. 架构真源（避免双账本误读）

```text
用户 Live Preview
  → (平台) preview-proxy :6014  [鉴权/空 body 风险]
  → 产品 :8080 mirror → LibreChat :3080 (React SPA + Mongo 会话)
       │
       ├─ 聊天补全：OPENAI_REVERSE_PROXY → Pico :18765/v1
       │              （Kimi HTTPS / pico-agent 工具环）
       └─ /api/pico/*（需 LibreChat JWT）→ Pico 账本 API
              → SQLite data/pico.db：Task/Run/Event/Artifact/Workspace/Automation
```

| 存储 | 存什么 | 是否「AI 业务真源」 |
|------|--------|-------------------|
| **Pico SQLite** | Task/Run/Event/Artifact… | **是（唯一 AI 账本）** |
| LibreChat Mongo | 会话气泡、用户、UI 状态 | **会话呈现**；不得当成第二套 AI 业务账本长期双写业务真相 |

---

## 5. Phase 1 成功标准 S1–S8（对照现状 · 非 PASS）

| ID | 要求（摘要） | 现状 | 判断 |
|----|--------------|------|------|
| **S1** | 真模型 API + 流式；密钥服务端 | Kimi 直连可回「校准OK」；流式路径存在；key 在 `.env` | **大体满足**（演示级） |
| **S2** | 钉版本 Kimi Agent 多步工具环 | pins `kimi-agent-sdk==0.0.5` / `kimi-cli==1.12.0` 已装；默认直连 Kimi 聊天，**agent 路径需显式 `pico-agent`** | **部分**（钉版本在；默认路径偏 chat 非多步） |
| **S3** | Task/Run/有序 Event | 表齐全；对话入账 + 摘要/文件产物 | **大体满足** |
| **S4** | 短时凭证 + school/membership 形 | JWT 测试签发 + proxy key；membership 头/`【Pico-User】` | **部分**（演示代理键 ≠ 生产短时凭证完整故事） |
| **S5** | 产品级 UI 真接通 | LibreChat 任务台 IA + 结果区；非空 JSON 根页 | **大体满足**（像素/全业务未齐） |
| **S6** | ≥2 allowlist + FakeEdu + 跨校 | 工具：`pico_echo` / `fake_edu_list_classes` / `pico_propose_change` | **部分**（有白名单；端到端 FakeEdu 演示密度不足） |
| **S7** | 提案→人确认→审计 | `pico_propose_change` 存在；产品 UI 确认流未闭环 | **缺口** |
| **S8** | CANDIDATE→CI→审→值守合 | 有 CI workflow；本分支 **未合 main**；写入窗不自 PASS | **流程未走完** |

**结论：** 主线方向正确；**不是**「从零文档仓」；也**不是**「WorkBuddy 对等完成」。  
相对 v1.2：核心「能聊 + 有账本 + 有壳」已在；S2 默认路径、S7、S8、安全生产化仍是门禁。

---

## 6. 必须剔除的错误 / 过时记忆

| # | 过时或错误 | 正确（以代码+本校准为准） |
|---|------------|---------------------------|
| 1 | HANDOFF：代码「仅文档脚手架」 | 已有 `apps/librechat` + `services/*` + 36+ commits 分支 |
| 2 | HANDOFF/MVP：前端 **Vue 3** | **LibreChat React**（CORRECTED-GOALS 已更；MVP 正文未改版） |
| 3 | HANDOFF 目录 `apps/nextchat` | **已删**；默认 **`apps/librechat`** |
| 4 | PRODUCT-UI 仍写 nextchat 启动 | 废句；启动看 `scripts/run-product.sh` |
| 5 | HAZARD R4：自动化无 scheduler | **已有** `automation_service.start_scheduler` |
| 6 | HAZARD R3：首条消息完全无绑定 | 已有 **pending_*** + rebind；仍可能竞态，非「零」 |
| 7 | Codex 审计时：自动化恒 401 | 已修 JWT `getTokenHeader`；**旧部署站可能未更新** |
| 8 | 用户消息必见 Pico-User 前缀 | 展示层已 strip；旧缓存/旧包可能仍见 |
| 9 | 结果区只有概览 | 代码有三视图；**非空文件**依赖产物链路 |
| 10 | 白屏 = 产品挂 | **先 8080 vs 6014** |
| 11 | curl API JSON = 产品成功 | 产品 = **8080 HTML 工作台** |
| 12 | 本窗可自 PASS / 合 main | **禁止** |
| 13 | 网盘 / edu SaaS 主线 | **否** |
| 14 | 恢复 web/nextchat/workbench | **禁止** |
| 15 | 拆 WorkBuddy 提速 | **禁止**；仅 clean-room |
| 16 | 双 AI 账本可长期 | **禁止** |
| 17 | PROXY=1 修预览 | **禁止**（崩 undici） |
| 18 | GOALS-NOW 写自动化「scheduler 后置」 | **已上服务端 tick**；字段/推送仍后置 |
| 19 | 评分 44% = 聊天也不可用 | 44% 是 **WorkBuddy 对等**尺；主聊路径可用 |
| 20 | phase health 文案 `3-integrate` = Phase3 已完成 | 仅服务标签；**edu 联调仍后置** |

---

## 7. 当前真实能力清单（诚实）

### 已可用（演示级）

- 中文品牌 Pico；登录；任务台首页；六入口导航  
- Kimi 真回复 + 中文失败映射  
- Task/Run 入账、rebind、产物（回复摘要 + 可合成 `hello.txt`）  
- 结果区概览/文件/浏览器（浏览器 iframe 预览）  
- 工作空间选择；项目创建/任务关联/动态·计划·指令  
- 自动化 CRUD + 服务端调度骨架  
- `/api/pico` 需登录；membership 隔离头  

### 半成品 / 壳

- 能力中心（专家/技能/连接器）多为导航壳  
- 项目资产 = 任务标题索引，非真文件库  
- Run 条：模型/耗时有，token 消耗卡弱  
- 像素未完全对齐 WorkBuddy（侧栏 263 已调，仍有差）  
- S7 人确认 UI 未产品化  

### 明确后置

- edu 真联调 / 退役 edu AI  
- 定价 FIXED  
- 本地全盘工作空间 / 桌面保活自动化  
- 腾讯文档/邮箱等授权墙  
- 换 Chat-UI（仅当证明纯 SPA 白 **且** 6014 已正确命中 8080）  

---

## 8. 文档索引（读哪些 · 哪些降权）

| 文档 | 地位 |
|------|------|
| `AGENTS.md` | **HARD 流程与仓界** |
| `docs/CORRECTED-GOALS.md` | **目标校正 + 错误记忆** |
| `docs/MVP-3DAY.md` v1.2 | **计划 FIXED**（技术栈句 Vue 等以 CORRECTED 覆盖） |
| `docs/PREVIEW-WHITE-SCREEN.md` | 白屏证据 |
| `docs/OSS-SHELL.md` | 壳选型 |
| `docs/CALIBRATION-NOW.md`（本页） | **工程现状快照** |
| `docs/GOALS-NOW.md` | 执行窗口径（部分 P2 句可能旧） |
| `docs/HAZARD-AUDIT.md` | 安全；**R3/R4 部分过时** |
| `docs/HANDOFF.md` | 历史交接；**§3 脚手架 / §5 Vue / §6 nextchat 过时** |

---

## 9. 建议主线（校准后 · 仍不升 v1.3）

> **执行蓝图：** [`docs/ORCHESTRATION-PLAN.md`](./ORCHESTRATION-PLAN.md) · 回归清单 [`docs/REGRESSION-MAINPATH.md`](./REGRESSION-MAINPATH.md)


按 **门禁收益** 而非「再堆 WorkBuddy 像素」：

1. **预览诚实**：6014 空 body 机制写清；用户 Live Preview 不谎称已通。  
2. **主路径稳定**：登录→发任务→账本→结果区产物（含文件）→失败中文（已大部分有，回归锁住）。  
3. **S2 默认叙事**：要么默认 pico-agent 工具环可演示，要么文档写明「默认直连 Kimi、agent 为显式模型」。  
4. **S7 最小闭环**：提案工具 → UI 确认 → Event。  
5. **S8**：独立 PR/CANDIDATE，不在写入窗自合 main。  
6. WorkBuddy 像素 / 九字段自动化 / 能力真绑定 → **在 1–5 不回退后**再排。

---

## 10. 给任何下一动作前的 10 行（替换碎片记忆）

```text
1. 只写 pico；永不写 edu-cloud。
2. 产品 = AI 工作台；壳 = apps/librechat；核 = :18765 + orchestrator + SQLite 账本。
3. 禁 web/nextchat/workbench 回潮；禁拆 WorkBuddy。
4. tip 在 grok/pico-preview-librechat-p0（领先 main）；不自 PASS、不无人合 main。
5. 8080 = 产品 HTML；18765 = API；6014 无鉴权常 403 空 body = 白屏根因之一。
6. S1/S3/S5 演示级大体有；S2 默认路径/S7/S8 仍是真门禁。
7. LibreChat Mongo ≠ 第二 AI 业务真源；业务 AI 真相在 Pico 账本。
8. 自动化已有服务端 scheduler；HAZARD「无调度」过时。
9. 计划仍 v1.2；Vue/nextchat 字样是文档债，不是回滚指令。
10. 下一刀先锁主路径与门禁，勿用像素冲淡 S7/S8/预览诚实。
```
