# edu-cloud AGENTS vs pico 工作流 — 深度对照（只读吸收分析）

```
DOC: docs/WORKFLOW-COMPARE-EDU.md
STATUS: ANALYSIS (binding decisions land in WORKFLOW.md / AGENTS.md)
DATE: 2026-07-29
SOURCE_READ: edu-cloud AGENTS.md (218 lines) — **read-only, no edu edits**
PICO_TARGET: docs/WORKFLOW.md + AGENTS.md
```

## 1. 结论先讲

| 问题 | 结论 |
|------|------|
| 工作模式是否一样？ | **一样**（切片隔离、CANDIDATE、独立审查、GitHub 唯一事实、不自 PASS） |
| 是否应整份复制 edu AGENTS？ | **否** — 含 ECS / OneFlow / 1908x / 生产红权，会污染 pico 边界 |
| 是否应吸收内核？ | **是** — 门禁与窗口语义必须对齐，否则双仓执行习惯分裂 |
| pico 过去缺口 | 根 AGENTS 过短 → 写入窗易「写完就 PR」跳过 CANDIDATE/审查叙事 |

**推荐：** 吸收 **Task isolation + Verification + Working rules + 精简 Risk**；  
**拒绝** 环境合同里的 edu 运行时专属段；  
**改写** 红路径与 Preview 端口为 pico 实体。

---

## 2. 逐段：吸收 / 改写 / 拒绝

### 2.1 Task isolation（edu §1）

| 条款 | 处置 | 理由 |
|------|------|------|
| 开工先读 parent Issue/PR/SHA/CI | **吸收** | 同模式；防臆测 |
| GitHub 读不到 → stale/BLOCKED | **吸收** | 同 |
| 用户只唤醒、不转发执行结果 | **吸收** | 同 |
| 总控拆解并行、接受结果 | **改写** | pico 总控可以是业主/会话总控，不强制「web Codex + ECS Grok」二元 |
| A/B/C 工作流字母 | **可选不强制** | 模式可同；pico 单仓并行度低，强制字母增加空窗成本 |
| `Grok-*写入/调查/审查` | **吸收角色语义**；窗口名可用 `Grok-Pico写入` | 业主已用 Grok-Pico 前缀 |
| 一切片一写入一分支一 PR | **吸收** | 核心 |
| 路径不重叠、单文件单写入 | **吸收** | 核心 |
| 审查绑死完整 SHA、不审移动 tip | **吸收** | 核心 |
| OPEN/KEEP/CLEAR/WAIT | **吸收** | 核心窗口态 |
| 15 分钟内 ACK（读范围/计划/证据点） | **吸收** | 防静默 |
| 连贯 push 后 CANDIDATE + 证据映射 | **吸收** | 核心 |
| CI∥审查∥UI QA | **吸收** | 核心 |
| 目标冻在 phase；45min 收口 | **吸收（软）** | 防 scope creep |
| Draft PR 一次写清 goal/paths/forbidden | **吸收** | 核心 |
| 结果只写回同一 Issue/PR + 全 SHA | **吸收** | 核心 |
| parent Issue 为 workstream 概览 | **吸收** | 已有 #1/#21 |
| 禁止再造 coordinator/mailbox/状态库 | **吸收** | edu 明文；pico 也曾堆文档风险 |
| 评论不唤醒总控；靠 wake 时同步 | **吸收（软）** | 无自动调度器 |

### 2.2 Environment contract（edu §2）

| 条款 | 处置 | 理由 |
|------|------|------|
| ECS 隔离 checkout | **拒绝** | pico 当前无 ECS 合同 |
| 19081 Preview / 19080 UAT / mcu.asia | **拒绝并改写** | pico：`0.0.0.0:8080` UI、`8000` API；无生产 mcu |
| Actions = 唯一 UAT/prod 操作者 | **部分** | pico 用 Actions 做 CI；**无 OneFlow 发布轨**则不写 OneFlow |
| 写入禁止动生产/Secrets | **吸收精神** | pico：禁止动 edu 生产；本仓 Secrets 变更 = 红 |

### 2.3 Working rules（edu §3）

| 条款 | 处置 |
|------|------|
| 最小正确机制；删双轨/适配器 croft | **吸收**（与「唯一 AI 账本」一致） |
| 黄/红先记边界与否定用例 | **吸收** |
| 5 分钟只读调查（90s 初报、TOP3、UNKNOWN） | **吸收** |
| 不吃别人 WIP、不改别人分支 | **吸收** |
| 不 force-push/删他人工作 | **吸收** |
| 报决策/证据/阻塞，少流水账 | **吸收** |
| 不建 durable handoff 浪潮文档 | **改写** | pico **允许** HANDOFF/MVP 计划类绑定文档；禁止「每窗新建状态包」 |
| 无 listener 轮询唤醒 | **吸收** |
| 可恢复 commit、批 CI 修、禁噪声 push | **吸收** |

### 2.4 Verification and review（edu §4）

| 条款 | 处置 |
|------|------|
| 最窄相关测 + format + diff --check | **吸收** |
| 用户可见 UI → 真浏览器抽检 | **吸收**（Playwright/预览） |
| UI QA: PASS/REVISE/BLOCKED + 全 SHA | **吸收** |
| 独立审查 PASS/REVISE/BLOCKED；写入不能自签 PASS | **吸收** |
| 租户/安全/AI 工具边界需真路径证据 | **吸收**（L1b 正是黄档） |
| 同一架构原因拒两次 → 停改重定范围 | **吸收** |
| 无冲突 base merge 复用业务审 + 窄 SHA 审 | **吸收** |
| Merge Queue | **可选** | pico 未启则写「对齐 main」 |

### 2.5 Risk and red gates（edu §5）

| 条款 | 处置 |
|------|------|
| 绿/黄/红定义 | **吸收** |
| 红路径列表 | **改写为 pico 路径**（见 WORKFLOW） |
| 任务授权覆盖同范围技术步 | **吸收** |
| OneFlow / 生产库 core auth | **拒绝** | 无对等发布/库降级轨则不抄 |
| 工作流改文件须替换不堆叠 | **吸收** |

---

## 3. 吸收后 pico 红路径（映射）

| 红 | pico 路径/行为 |
|----|----------------|
| 鉴权/租户 | `services/api/app/auth.py`, `openai_compat` principal, membership 过滤 |
| Agent 安全 | `agents/pico.yaml`, `PICO_DANGEROUS_TOOLS_ENABLED`, gateway |
| 密钥 | `.env*`, Settings 密钥字段, CI secrets |
| 工作流合同 | `AGENTS.md`, `docs/WORKFLOW.md` |
| CI 门禁 | `.github/workflows/**` |
| 唯一账本语义 | Task/Run/Event 模型破坏性变更 |
| 禁 edu 双 AI | 任何「edu 内再开一套 AI 账本」设计 |

---

## 4. 执行差距（本窗曾犯 vs 合同）

| 应做 | 曾出现 | 纠偏 |
|------|--------|------|
| CANDIDATE 全 SHA | 先 PR 后补 | #22 已补 CANDIDATE |
| 独立审查后再合 | 倾向「CI 绿就可合」 | 明确写入不自合黄/红 |
| 15min ACK | 直接开写 | WORKFLOW 预检 |
| 结果落 Issue | 聊天摘要为主 | Issue #21 / PR 评论 |

---

## 5. 最终建议（给业主）

1. **工作模式对齐 edu：吸收内核（已写入 WORKFLOW v0.2）。**  
2. **不要**把 edu Environment/OneFlow 原样贴进 pico。  
3. 窗口命名建议统一：`Grok-Pico写入` / `Grok-Pico调查` / `Grok-Pico审查`（可选字母流）。  
4. 黄/红 PR（含 #22 L1b）必须 **CANDIDATE → CI → 独立审查 → 值守合**。


## 版本管理补记

详见 [`VERSIONING.md`](./VERSIONING.md)：门禁/SHA **已吸收**；OneFlow/生产 digest **未照搬**；运行自证 **约定中**。
