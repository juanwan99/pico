# Pico 执行工作流（绑定）

```
DOC: docs/WORKFLOW.md
STATUS: BINDING v0.2
SOURCE: edu-cloud AGENTS.md 内核吸收 + pico 边界改写
COMPARE: docs/WORKFLOW-COMPARE-EDU.md
VERSIONING: docs/VERSIONING.md
REPO: juanwan99/pico ONLY
```

> **工作模式与 edu 相同**（切片隔离、CANDIDATE、独立审查、GitHub 唯一事实）。  
> **运行时合同不同**（无 ECS/OneFlow/edu 生产端口）— 见对照文，勿整份复制 edu AGENTS。

禁止再造：自动调度器、mailbox、lease、平行状态库、与 GitHub 重复的「进度协议」。

---

## 1. 硬范围

| 允许 | 禁止 |
|------|------|
| 读写 **pico** | 写 **edu-cloud** 或任何外仓 |
| 只读参考 edu 文档/模式 | 在 edu 开 PR、值守 edu CI、改 edu AI |
| Phase 2/3 **Pico 侧**合同与适配 | 双 AI 账本 / dual-run |

代码、测试、GitHub、已验证运行配置 **高于** 散文。

---

## 2. 角色窗口（与 edu 同构）

| 窗口名（建议） | 写代码 | 职责 |
|----------------|--------|------|
| `Grok-Pico写入` | 是 | 一分支一 PR；实现；窄测；同范围 CI 修；CANDIDATE |
| `Grok-Pico调查` | 否 | 只读；90s 初报；TOP 风险；UNKNOWN |
| `Grok-Pico审查` | 否 | **完整 40 字 SHA** → `PASS` / `REVISE` / `BLOCKED` |
| 总控 / 业主 | 派发 | 目标、合入授权、跨仓；**不替写入自签审查 PASS** |

可选：`Grok-Pico-A/B/…` 字母流 — **仅当** 多切片并行且总控点名时使用；默认单流即可。

### 窗口态

| 态 | 含义 |
|----|------|
| `OPEN` | 现在执行所指任务 |
| `KEEP` | 继续原任务 |
| `WAIT` | 故意不跑（依赖未就绪） |
| `CLEAR` | 上下文丢弃；再开须从 GitHub 重建 |

- **一切片 = 一写入窗 = 一分支 = 一 PR**（可 Draft）。  
- 禁止两写入同分支；单文件单写入；共享文件串行。  
- 审查 **禁止** 审移动中的 tip；只审冻结 SHA。  
- 写入窗 `VERDICT_AUTHORITY: NONE` — 不自 PASS S1–S8 / 「产品完成」。  
- 连贯 push 后 **关闭写入**；仅在接受的 REVISE 批次再 OPEN。  
- 新会话默认 `CLEAR`：不信外窗记忆。

### 15 分钟 ACK

`OPEN`/`KEEP` 后 15 分钟内至少回报：已读范围、计划或 blocker、下一证据点。  
**ACK ≠ 完成证据。**

---

## 3. 主路径

```text
总控/业主：目标 + Issue/PR 号唤醒
  → 写入 OPEN：预检 → 实现 → 窄测 → push
  → PR 评论 CANDIDATE（全 SHA + 验收映射 + BLOCKED）
  → 并行：CI ∥ 独立审查 ∥（若 UI）UI QA
  → Ready（如需）
  → 有人值守 merge main
  → CLEAR 写入
```

### CANDIDATE 模板

```markdown
## CANDIDATE
- SHA: `<40-char lowercase hex>`
- PR: #
- 风险档: 绿 | 黄 | 红
- 验收:
  - [ ] <项> → 证据: <pytest / Actions run / 截图路径>
- BLOCKED: <无 | 列表>
- 范围外: …
```

### 独立审查

- 只读上下文；**写入者不得自签** `PASS`。  
- 输出：`PASS` | `REVISE` | `BLOCKED`（BLOCKED = 缺证据/能力，非口味不同意）。  
- 租户 / 鉴权 / Agent 工具 / 唯一账本：要 **真路径** 证据（审查侧执行或等价 CI），禁止仅靠源码字符串或自报。  
- 同一架构原因连续两次 REVISE → **停止打补丁**，重定范围或改设计。  
- 修订审可看增量；**最终 PASS 必须绑当前完整 SHA**。  
- 产品 diff 或手解冲突 → 旧审/旧 UI QA 作废。  
- 仅无冲突 base merge 且对 base 产品 diff 字节级相同：可复用业务结论，仍需当前 head CI + 未参与写入的窄 SHA 审。

### UI QA（用户可见变更）

- `UI QA: PASS` | `REVISE` | `BLOCKED`，绑全 SHA。  
- 覆盖改动旅程 + console/network；高风险补否定/空态。  
- 非每个 PR 全站回归。

### 合并

- **禁止** 无人值守合 main（MVP S8）。  
- 黄/红：CI 绿 + 独立审查 PASS 后值守合。  
- 绿：CI 绿 + 自检；薄审查可选。  
- 对齐 main：先 sync 再 CI，再审当前 SHA（禁「先审后 sync」）。

---

## 4. 工作规则（吸收 edu Working rules）

1. 最小正确机制；证实的生产/安全/外合同边界才保留兼容。  
2. 否则修根因并 **删** 双轨/ croft 适配器，不叠平行控制。  
3. 黄/红改信任或数据边界前：写下边界、待删旧路径、相称否定用例；边界未决则 **写入阻塞**。  
4. 行为变则补测；优先现有库与普通 Git。  
5. 只读调查：5 分钟封顶首轮（90s 初报 → TOP3 → 其余 UNKNOWN）。  
6. 先读后改；不吞并他人 WIP；不改他人分支躲冲突。  
7. 不 reset/clean/stash/force-push/覆盖/删除非己工作。  
8. 报 **决策、终局证据、阻塞**；少日常流水账。  
9. 允许绑定计划文档（MVP/HANDOFF/WORKFLOW）；**禁止**每窗新建「状态包」浪文档。  
10. 可恢复本地 commit → 窄检 → 连贯 push；CI 修复成批；push 不作心跳。

---

## 5. 风险档（pico 路径）

| 档 | 含义 | 门禁 |
|----|------|------|
| **绿** | 小、可逆、单区 | CI + 自检 |
| **黄** | 跨模块、鉴权/租户、SSE、openai-compat、编排、重要数据行为 | **独立 exact-SHA 审查** |
| **红** | 见下表 | 独立审查 + 任务授权；涉密钥/禁安开关键注意外宣 |

### 红路径（pico）

- `services/api/app/auth.py`、openai-compat 升 principal  
- membership / school 隔离语义  
- `agents/pico.yaml`、危险工具开关  
- 密钥与 `Settings` 敏感默认  
- `AGENTS.md` / `docs/WORKFLOW.md` / `.github/workflows/**`  
- Task/Run/Event **破坏性** 模型变更  
- 任何「与 edu 双 AI 真源」设计  

风险与授权分离：只读调查/审查/跑测 **不需** 额外授权。  
**一项任务授权** 覆盖其分支/PR/commit/push/同范围 CI 修/评论/Ready；用户授权目标，不逐技术步骤追问。  
仅当需要 **产品二选一、用户独有账号、或扩大 forbidden scope** 时再问人。

---

## 6. 环境（pico，非 edu 端口）

| 用途 | 约定 |
|------|------|
| 产品预览 UI | `0.0.0.0:8080`（如 NextChat / web） |
| API | `127.0.0.1:8000` 或同机 compose |
| 开发数据 | 本地 SQLite / 最小 seed；**不用** 生产数据 |
| CI | GitHub Actions = 常规门禁证据 |
| 发布 | 当前 **无** OneFlow；合 main ≠ 自动生产，除非另建轨 |

写入禁止：把生产密钥写进仓、打开危险工具默认、在文档外另立 AI 账本。

---

## 7. 启动预检（每个写入窗）

1. `git fetch`；记录 **main 完整 SHA** 与任务 PR tip  
2. 读 `AGENTS.md`、`docs/WORKFLOW.md`、载体 Issue/PR、相关 FIXED 计划  
3. 同步 CI；本地 ruff + 相关 pytest  
4. 短校准：目标 / 分支 / 风险档 / 非目标  
5. 结束：`CANDIDATE` 或明确 `BLOCKED` — **不自 PASS**

---

## 8. Draft PR 一次写清（勿在评论重复长文）

- 目标与完成条件  
- 预计改动路径  
- 禁止范围（尤其 edu / 定价 FIXED）  
- 风险档  

---

## 9. 当前 polish 对齐

| 切片 | 载体 | 档 | 门禁 |
|------|------|----|------|
| L1b SSE/auth/membership | #21 · #22 | 黄 | CANDIDATE 已发 → 待 **独立审查** → 值守合 |
| 工作流文档 | #23 | 绿/黄 | 对照吸收后审查可选 |
| L2 真流式 | 续 #21 | 黄 | 同主路径 |
| 定价 FIXED | — | — | **业主另令前不做** |

---

## 10. 修订本文件

工作流变更须 **替换或删除** 旧句，禁止只追加冲突层。  
仅当新的、有证据的安全边界时加长。


---

版本管理专章：[`VERSIONING.md`](./VERSIONING.md)（edu 内核吸收 + pico 发布边界）。
