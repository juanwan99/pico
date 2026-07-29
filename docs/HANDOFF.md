# Pico 交接文档 — 给新执行窗口

```
DOC: docs/HANDOFF.md
ROLE_OF_READER: 固定执行窗口（写入 / 调查 / 审查 按派发）
ROLE_OF_AUTHOR: Grok-Global-Control（总控；本交接不占用写入窗）
REPO: https://github.com/juanwan99/pico
DEFAULT_BRANCH: main
PLAN_STATUS: FIXED v1.2
PLAN_DOC: docs/MVP-3DAY.md
PLAN_COMMIT: 91df0d39c65848e40e7e95fa4db30a3d401bfbf2
ISSUE: https://github.com/juanwan99/pico/issues/1
RELATED_EDU: https://github.com/juanwan99/edu-cloud  (Phase 1 不联调)
DATE: 2026-07-29
```

---

## 1. 你是谁、要干什么

你接手 **Pico**：独立 **AI 底座** 仓库，目标是在约 **3 天** 内交付 **Phase 1 MVP**（见固定计划）。

| 做 | 不做 |
|---
---

## 0. HARD — 只负责 pico（业主强制 · 永久）

| 规则 | 说明 |
|------|------|
| **唯一可写仓** | `juanwan99/pico` |
| **禁止** | 克隆、修改、PR、值守 CI、合并 **edu-cloud** 或任何其它仓 |
| **Phase 3** | 只做 Pico 侧适配器 / 校验 / 钩子 / 文档；edu 实现归 edu 团队 |
| **违规** | 不是「协调」，是越界 |

本条 **高于** 下文任何「对接 / Integrate」叙述。与 `AGENTS.md` 一致。

-|------|
| 按 `docs/MVP-3DAY.md` **v1.2 FIXED** 实现 | 改计划而不升版本 |
| Pico 内 Agent + 模型 API + UI + 账本 + CI | 日常去改 edu-cloud / 联调 edu |
| 合同形状预留对接 | 重做教务 SaaS / 网盘主产品 |
| CANDIDATE → CI → 审查 → **有人值守**合并 | 无人合并 main、跳过门禁 |

总控（全局主控）只做：计划、派发、门禁、合并授权；**实现必须在独立写入窗**，且 `VERDICT_AUTHORITY: NONE`（写入不自 PASS）。

---

## 2. 前因后果（必读）

1. **edu-cloud** 是多校教育 SaaS；库为学校业务真源。  
2. 规划一度误把「教师空间」当 **网盘**；业主纠正：  
   - 产品 = **类 ChatGPT / Grok / Kimi 的 AI 空间**（体验 + **Agent 编排** + 产物）  
   - **开源 Kimi Agent** 驱动编排（薄改，不自研 Agent OS）  
   - 模型 = **HTTPS API**（Kimi / DeepSeek），不是默认自托管  
   - 业务已在 edu，**对接后置**  
3. 因此新建 **私有仓 pico**，与 edu **拆分节奏**。  
4. **v1.2 固定策略：**  
   - **Phase 1**：Pico 独立开发（**不管 edu**）  
   - **Phase 2**：对接合同  
   - **Phase 3**：再协调 edu 真联调 + **退役 edu 旧 AI**（禁止双跑）

详细计划：`docs/MVP-3DAY.md`。  
范围：`docs/SCOPE.md` · 架构：`docs/ARCHITECTURE.md` · 规则：`AGENTS.md`。

---

## 3. 仓库当前状态（接手时请再 `git fetch` 核实）

| 项 | 值 |
|----|-----|
| 远程 | `juanwan99/pico` private |
| 计划 | **FIXED v1.2** @ main `91df0d3…`（以最新 main 为准） |
| 代码 | **仅文档脚手架**（尚无应用实现） |
| CI | 可能尚未建 workflow → **D1 必须补上**（S8 强制 CI） |
| Secrets | 需业主配置 **模型 API Key**（无 key 则 S1 不能 PASS） |

```bash
gh repo clone juanwan99/pico
cd pico
git log -3 --oneline
# 必读
cat docs/MVP-3DAY.md docs/HANDOFF.md docs/SCOPE.md
```

---

## 4. Phase 1 成功标准（S1–S8）— 不可私自缩水

| ID | 必须 |
|----|------|
| S1 | **真**模型 API 流式（Kimi 优先）；密钥服务端；**mock ≠ S1** |
| S2 | **钉版本** Kimi Agent 服务端多步工具环 |
| S3 | Pico DB：**Task + Run + 有序 Event**（唯一 AI 账本） |
| S4 | 短时凭证校验；claim 形如未来 edu：`school_id/membership_id/scopes/iss/aud/exp`；Phase 1 = **测试签发器**；body/prompt 不扩权 |
| S5 | 三区 UI：历史/任务 · 流式+工具时间线 · ≥1 产物 |
| S6 | ≥2 allowlist 工具；≥1 个 **FakeEdu**（未来 edu 只读接口形状）+ 跨校拒绝记 Event |
| S7 | 提案 → 人确认 → 审计；无静默业务写入 |
| S8 | **CANDIDATE PR → CI 绿 → 独立审查 → 值守合并** |

**Agent 安全（硬）：** Shell / 主机 File / Web / MCP / 任意工具 **默认关**；仅白名单。钉住的 runtime 证不了 → **BLOCKED**，禁止自研 Agent 框架替代。

**不做（Phase 1）：** 联调 edu、网盘全文、像素抄品牌、双模型商用热切、改 edu 合并 AI。

---

## 5. 技术冻结（D1 并行写码前必须先提交）

| 项 | 固定 |
|----|------|
| API/编排 | Python 3.11+ |
| 前端 | Vue 3 + Vite |
| Agent | lock **钉死** Kimi Agent SDK/runtime version 或 commit |
| 模型 | Kimi API 优先（真 API） |
| 花费帽 | 单 Run 时长 / token / 有限重试（防夜间刷爆） |
| 合同骨架 | `docs/contracts/{delegated-auth,tools,ai-facts,change-handoff}.md` |

IA 母版：**Claude 式**（对话 + 右侧产物）；气质可参考 Kimi；可参考 edu-cloud 的 `ai-workbench` 三栏（**只读参考**，勿双写 edu）。

---

## 6. 建议目录（实现时可调，但职责清晰）

```text
pico/
  docs/                 # 计划与合同（已有）
  apps/web/             # Vue3 三区 UI
  services/api/         # FastAPI/同类：鉴权、Task/Run、stream
  services/orchestrator/# Kimi Agent 适配、allowlist 网关
  packages/contracts/   # 可选：共享类型
  tests/
  .github/workflows/ci.yml
  docker-compose.yml    # 可选 dev
  .env.example
  README.md             # make dev / 演示步骤
```

---

## 7. 三日节奏（摘要）

| 日 | 有人 | 夜间仅 |
|----|------|--------|
| D1 | 冻结 §5 + 脚手架 + Agent 钉版本 + 安全证明 + 模型 hello | 单测/依赖；有界重试 |
| D2 | 落库 + UI 接通 + FakeEdu 工具 | 集成/取消/超时（有帽） |
| D3 | 跨校 Event + 待确认 + 合同补全 + CANDIDATE + CI + 审查 + **值守合并** + DEMO.md | 全量复跑；**不合并** |

并行建议：W1 Agent/Provider/网关 · W2 API/DB/鉴权 · W3 UI；**schema + 鉴权 + allowlist 串行**。

---

## 8. 与 edu-cloud 的边界（防跑偏）

| Phase 1 | Phase 3（本窗口默认不做，除非总控新派） |
|---------|------------------------------------------|
| 不改 edu 业务 | edu 真签发 token |
| FakeEdu + 合成数据 | 真 edu 只读 API |
| 测试签发器 | 工作台嵌入/跳转 Pico |
| | **原子退役** edu AI runtime/workbench/API/worker |

参考（只读）：`https://github.com/juanwan99/edu-cloud`  
- 壳：`frontend/src/pages/ai-workbench/`  
- 事件模式：`src/edu_cloud/modules/ai_foundation/`（PR #429 已合 master）  
**禁止** Phase 1 与 edu AI 双跑写账本。

---

## 9. 质量与安全红线

- 不自 PASS；写入窗 `VERDICT_AUTHORITY: NONE`  
- Secrets 不进 git；`.env.example` 无真 key  
- 跨校 / 无凭证必须 fail-closed  
- 夜间禁止：merge main、改生产、无上限打模型  
- 改 FIXED 计划 → 必须 `MVP-3DAY` v1.3+ 与 delta说明  

---

## 10. 建议的第一枪（新窗口收到 GO 后）

1. `git pull`；确认 main 含 v1.2 与本 HANDOFF。  
2. 开分支 `feat/mvp-d1-scaffold`（或总控指定名）。  
3. 提交：Agent 版本钉死证明 + Python/Vue 骨架 + CI workflow 空绿/最小绿 + `docs/contracts/*` 骨架 + `.env.example`。  
4. 证明：Agent 配置下 Shell/File/Web/MCP **off**（日志或测试）。  
5. 真 API hello（有 key）或明确 **BLOCKED S1 缺 key**（诚实，不假绿）。  
6. 推 PR Draft；本地/CI 证据写在 PR。  
7. **不要**宣布 MVP 完成直到 S1–S8 + 审查 + 值守合并。

---

## 11. 演示脚本（验收时）

见 `docs/MVP-3DAY.md` §9。核心：测试签发 School A → 真流式 → FakeEdu 工具 Event → 产物 → 跨校拒绝 Event → 待确认 → 取消 Run。

---

## 12. 联系与升级

| 情况 | 动作 |
|------|------|
| 计划冲突 / 要砍 S1–S8 | 停写；升级总控 / 业主；出 v1.3 |
| 无 API Key | 记 BLOCKED；可继续非 S1 项 |
| Agent 无法关危险工具 | **BLOCKED MVP**；升级 |
| 被要求改 edu | 核对是否 Phase 3 派发；默认拒绝 |

---

## 13. 一页清单（打印用）

```text
[ ] 已读 MVP-3DAY v1.2 FIXED + 本 HANDOFF
[ ] Phase 1 不联调 edu
[ ] Pico 唯一 AI 账本
[ ] Kimi Agent 钉版本 + 危险工具 off
[ ] 真模型 API（S1）
[ ] 测试签发 + FakeEdu 合同形状
[ ] 三栏 UI 真接通
[ ] CI + 审查 + 值守合并
[ ] 合同四份骨架
[ ] 未自 PASS
```

---

**交接完成条件：** 新窗口确认已读本文 + `docs/MVP-3DAY.md` v1.2，并按总控 **GO / DISPATCH** 开工。  
无 GO 时：只读熟悉仓库，不强制写码。


## 整体架构与定价

- 主文档：[`docs/OVERALL-ARCHITECTURE.md`](./OVERALL-ARCHITECTURE.md)（DRAFT，待业主确认升 FIXED）

- 默认拍板快查：[`docs/ARCHITECTURE-DEFAULTS.md`](./ARCHITECTURE-DEFAULTS.md)


## 执行工作流

绑定：[`docs/WORKFLOW.md`](./WORKFLOW.md)（从 edu 模式迁入的 pico 门禁；非 edu 仓操作）。
