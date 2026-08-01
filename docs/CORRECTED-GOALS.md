# Pico 目标校正（清除错误记忆）

```
DOC: docs/CORRECTED-GOALS.md
STATUS: OWNER-ALIGNED SNAPSHOT
DATE: 2026-07-29
REPO: juanwan99/pico ONLY
PLAN: docs/MVP-3DAY.md v1.2 FIXED（无授权不升 v1.3）
```

> 本页用于**校正执行窗错误记忆**。与 HANDOFF / MVP-3DAY / AGENTS 冲突时：  
> **HARD 范围与 v1.2 成功标准以原 FIXED 文档为准**；UI 壳选型以本节「当前产品壳」为准（业主已改方向）。

---

## 1. Pico 是什么（固定）

| 是 | 不是 |
|----|------|
| **独立 AI 底座 / AI 产品** | 网盘 / 5GB 文件主产品 |
| **类 Claude / Codex / Grok / WorkBuddy 品类** 的 AI 工作空间 | 自研教务 SaaS、考试系统 |
| **对话 + Agent 编排 + 产物 + AI 账本** | 重做学生/考试/成绩业务 |
| **模型 = HTTPS API**（Kimi 优先，可 DeepSeek） | 默认自托管 GPU 大模型 |
| **编排 = 开源 Kimi Agent 薄改**（钉版本） | 自研 Agent OS |
| **唯一 AI 事实账本**（Task/Run/Event/Artifact…） | 与 edu 双 AI 真源并行 |
| **Phase 1 独立交付** | 日常改 edu-cloud / 以联调 edu 为 Phase1 门禁 |

**一句话：**  
Pico = 学校场景可用的 **AI 工作台产品**（壳 + 服务端 Agent + 模型 API + 租户账本），业务数据仍归 edu；对接后置。

---

## 2. 边界（永久 HARD）

| 规则 | |
|------|---|
| **唯一可写仓** | `juanwan99/pico` |
| **禁止** | 写/PR/CI/合 **edu-cloud**；在 edu 当 SaaS 总控 |
| **edu** | 只读参考 AI 壳/事件形状；Phase 3 再真联调 |
| **账本** | Pico 独占 AI 账本；禁止双跑 |
| **工具默认** | Shell/File/Web/MCP **默认关**（allowlist 白名单） |
| **流程** | CANDIDATE → CI → 独立审查 → **有人值守**合 main；**不自 PASS** |
| **计划** | MVP v1.2 FIXED；改计划须升 v1.3+ 业主授权 |

---

## 3. 成功标准（Phase 1 · S1–S8 仍有效）

| ID | 含义（摘要） |
|----|----------------|
| S1 | 真模型 API 端到端 + 流式 UI；密钥仅服务端 |
| S2 | 钉版本 Kimi Agent 服务端多步工具环 |
| S3 | Task/Run/有序 Event 持久化 = 唯一 AI 账本 |
| S4 | 短时凭证（school_id/membership_id 同形）；Phase1 测试签发 |
| S5 | **产品级 UI 真接通**（见下节壳） |
| S6 | ≥2 allowlist 工具 + FakeEdu 形状；跨校拒绝 |
| S7 | 提案→人确认→审计；禁静默写业务 |
| S8 | CI + 审查 + 值守合并 |

---

## 4. 产品壳（业主迭代后的正确记忆）

### 4.1 目标体验（业主方向）

业主要的是 **WorkBuddy / Codex / Claude 级「任务工作台」手感**，不是：

- 自研橙色三栏 `apps/web`（**已禁、不得回潮**）
- 简陋 Chat 气泡列表当终局
- 拆闭源 WorkBuddy 安装包（**禁止**）

目标 IA 参考（合法：开源魔改 + 自有品牌）：

- 新建任务 / 助理 / 项目 / 专家·技能·连接器 / 自动化  
- 模式 + 能力 chip + 大输入  
- 流式对话 + 工具步骤 + 产物  

### 4.2 当前默认壳（2026-07-29）

| 状态 | 路径 | 说明 |
|------|------|------|
| **当前产品壳** | `apps/librechat` | MIT LibreChat，接 Pico OpenAI 兼容 API |
| **已删除** | `apps/web` | 自研三栏，污染版本，禁止回归 |
| **已删除** | `apps/nextchat` | 过渡 Chat 壳，已卸 |
| **已删除** | `apps/workbench` | 临时自研任务首页，已卸 |
| **禁止** | LobeChat 商用分发风险壳 | 许可不适合直接魔改售卖 |
| **禁止** | 逆向 WorkBuddy | 只可参考公开 IA / 开源 clean-room |

**壳与核的边界：**

```text
LibreChat（或后续更贴 WorkBuddy 的 MIT 壳）
  = 产品 UI / 会话呈现
Pico API + orchestrator + DB
  = 唯一 AI 账本 / 租户 / 工具环 / 模型密钥
禁止：LibreChat Mongo 会话变成「第二套 AI 业务真源」长期双账本
```

### 4.3 预览（Grok 沙箱）正确记忆

| 正确 | 错误 |
|------|------|
| 产品页应在 **0.0.0.0:8080**（LibreChat） | 把 **Pico API JSON** 当产品页 |
| API 仅 **127.0.0.1:18765**（内网） | API 绑公网 8080 抢预览 |
| 预览代理会发现多端口；须 **pin 8080** | 以为「本机 curl 通 = 用户预览通」 |
| 用户主要靠 **Grok Live Preview** | 让用户去外部浏览器开 sandbox 域名（常 404） |
| 白屏 ≠ 产品逻辑一定挂；常为 **代理鉴权/空 body** | 只回「我这边 200」不修预览路径；或立刻换壳 |

### 4.4 Live Preview 白屏 — 已证实根因（必记）

**根因：Grok Preview 代理层（约 :6014），不是 LibreChat / Pico API 主流程没写出来。**

| 对照 | 现象 | 含义 |
|------|------|------|
| 直连 **:8080** | 200 HTML；Playwright 见 **Welcome back** | 产品 UI **正常** |
| 走 **:6014** 无 preview-auth | **403**（或 302→鉴权）+ **body 长度 0** | 面板拿到 **空页 = 纯白** |
| pin target | 必须 **8080** | 避免代理粘到 API/Mongo 端口 |
| proxy 版本 | 本环境约 **0.1.11**（无 `--version` flag） | 远早于 changelog 0.2.90/0.2.96 修复 |

**下次禁止再犯：**

1. **不要**因用户说白屏就立刻换壳 / 重写前端。  
2. **不要**只 curl :8080 就对用户说「预览好了」。  
3. **必须**对比：8080 vs 6014 的 status/body 长度 + Playwright 两边截图。  
4. **不要**设 `PROXY=1`（弄崩 LibreChat undici）。  
5. 首屏保留无 JS 可见「Pico 正在加载…」；若 10 秒内连这句都没有 → **面板没吃到 8080 HTML**。  
6. 证据写 `docs/archive/PREVIEW-WHITE-SCREEN.md`，诚实：本机绿 ≠ Live Preview 绿。

**演示登录（LibreChat）：** 管理员临时创建并通过安全渠道提供；仓库不保存固定密码。
详见 `docs/archive/PREVIEW-WHITE-SCREEN.md`。

---

## 5. 技术冻结（仍有效）

- Python **3.11+**（kimi-agent-sdk 实际要求 **≥3.12**）
- 前端壳：当前 **LibreChat (React)**；历史文档中的 Vue3 叙述以壳选型更新为准（不强制改回 Vue）
- **钉死** Kimi Agent 版本（见 `agent_pins` / requirements）
- Kimi API 优先

---

## 6. 必须清除的错误记忆（执行窗）

| # | 错误记忆 | 正确 |
|---|----------|------|
| 1 | Pico = 网盘 / 文件空间 | AI 工作台 + Agent + 账本 |
| 2 | 日常要去改 edu / 跑 edu | **只写 pico**；edu 只读参考 |
| 3 | Phase 3 = 本窗接管 edu SaaS | Phase 3 只做 Pico 侧适配；edu 归 edu 团队 |
| 4 | 自研三栏 `apps/web` 是产品 | **污染版本，已禁** |
| 5 | NextChat / workbench 仍是默认壳 | **已卸**；默认 **LibreChat** |
| 6 | 从零画壳最快 | **开源壳魔改**；禁拆 WorkBuddy |
| 7 | 双 AI 账本过渡可长期 | **禁止**双真源 |
| 8 | 预览 = localhost 链接给用户 | 用户只有 **Live Preview**；agent 在容器内验证 |
| 9 | curl API 根 JSON = 产品可用 | JSON 是 API；产品是 **HTML 工作台** |
| 10 | L2 优化过自研三栏就算产品打磨 | L2 若打在已删壳上 = 无效产品路径 |
| 11 | 收费 1 点=1000 token 已 FIXED | 商业 **REVISE 未 FIXED**；勿锁死 |
| 12 | Shell/File/Web/MCP 默认全开 | **默认关** |
| 13 | 写入窗可自 PASS / 无人合 main | **不自 PASS**；值守合并 |
| 14 | 计划可随口改 | 须升 **v1.3+** 授权 |
| 15 | **用户白屏 = 产品壳/API 挂了** | **先查 6014 鉴权/空 body vs 8080 HTML**；常是 Preview 层 |
| 16 | **本机 8080 200 = Live Preview 好了** | 必须 Playwright 8080 **且** 理解 6014 门禁；用户侧看面板 |
| 17 | **白屏就换 NextChat/自研壳** | 6014 不转发 8080 时 **任何前端都白** |
| 18 | **设 PROXY=1 修代理** | **禁止**；崩 LibreChat undici |

---

## 7. 当前工程事实（校正时点）

> 更新快照：[`docs/README.md`](./README.md)（分支 tip / S1–S8 对照 / 过时记忆表）。

| 项 | 值 |
|----|-----|
| 产品 UI | `apps/librechat` → 公网预览 **:8080** |
| Pico API | `127.0.0.1:18765`（OpenAI 兼容 `/v1/chat/completions` 等） |
| 账本 / Agent | `services/api` + `services/orchestrator` |
| 启动 | `scripts/run-product.sh` + pin 预览到 8080 |
| 演示账号 | 默认关闭播种；临时凭据须使用 12 位以上随机密码并在演示后关闭 |
| 已知风险 | Grok preview-proxy 鉴权空 body；版本约 0.1.11；in-container 可绿但 Live Preview 依赖平台会话 |

---

## 8. 近期正确优先级（不升计划版本前提下）

1. **预览稳定出 LibreChat 登录/聊天**（用户可见，非仅本机 200）  
2. 中文 + 去 LibreChat 品牌 → Pico  
3. 真流式 + 失败可读（Pico API）  
4. 首页/IA 向 WorkBuddy 任务台收敛（LibreChat 主题魔改，不从零）  
5. 账本/membership/安全项按既有 L1b 清单巩固  
6. edu 真联调 / 定价 FIXED → **后置**，非本窗主线  

---

## 9. 给下一窗的 10 行校准

```text
1. 只写 juanwan99/pico；永不写 edu-cloud。
2. 产品 = AI 工作台，不是网盘/教务。
3. 唯一 AI 账本在 Pico；禁止双跑。
4. 壳 = apps/librechat（MIT 魔改）；禁 apps/web / 禁拆 WorkBuddy。
5. 核 = Pico API + Kimi Agent 钉版本 + 模型 HTTPS API。
6. 公网预览只应是 UI :8080；API 仅 loopback；pin target 8080。
7. 白屏先查 6014 空 body vs 8080 Welcome back；勿误判换壳。
8. S1–S8 仍是 Phase1 标尺；商业定价未 FIXED。
9. 流程：CANDIDATE+SHA → CI → 审 → 值守合；不自 PASS。
10. 无授权不改 MVP v1.2 计划正文。
```

---

## 执行导航

总体规划（阶段/底座/冻结）：[`docs/MASTER-PLAN.md`](./MASTER-PLAN.md)


## 执行操作系统

Pico 适配版 OneFlow（闭环）：[`docs/ONEFLOW.md`](./ONEFLOW.md)
