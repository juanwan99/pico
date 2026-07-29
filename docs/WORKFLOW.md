# Pico 执行工作流（绑定）

```
DOC: docs/WORKFLOW.md
STATUS: BINDING for pico writers
SOURCE_PATTERN: adapted from edu-cloud AGENTS.md (task isolation / CANDIDATE / review)
NOT_COPIED: edu ECS, OneFlow, A/B/C workstream letters, production paths
REPO: juanwan99/pico ONLY
```

## 0. 与 edu 的关系

| | edu-cloud | pico |
|--|-----------|------|
| 完整合同 | `AGENTS.md` 长文（隔离、ECS、OneFlow、红黄绿） | **本文 + 根 `AGENTS.md`** |
| 是否同一套「窗口名」 | `Grok-A写入/调查/审查` 等 | 可用 **写入 / 调查 / 审查**；**不强制 A/B/C 字母** |
| 共享事实 | GitHub Issue/PR/SHA/CI | **相同** |
| 禁止 | （edu 自有） | **任何 edu-cloud 写入** |

业主若只在 edu 项目里「习惯了流程」，**pico 过去文档偏薄**——不是流程只属于 edu，而是 **尚未完整迁入 pico**。本文补齐。

---

## 1. 角色与窗口

| 角色 | 可写代码？ | 职责 |
|------|------------|------|
| **写入** | 是 | 分支、实现、测试、Draft/Ready PR、同范围 CI 修复 |
| **调查** | 否 | 只读取证、风险、UNKNOWN 列表 |
| **审查** | 否 | 绑定 **完整 40 字 SHA** → `PASS` / `REVISE` / `BLOCKED` |
| **总控/业主** | 视派发 | 目标、合入授权、跨仓决策；**写入不自 PASS** |

规则：

- **一个产品切片 = 一个写入窗 = 一个分支 = 一个 PR**（可 Draft）。  
- **禁止** 两写入同分支；**禁止** 审查窗改业务代码「顺手修」。  
- 新会话默认 `CLEAR`：只信 GitHub + 本仓文档，不信外窗聊天记忆。  
- 写入窗 `VERDICT_AUTHORITY: NONE` — **不得** 自宣布 S1–S8 PASS / 产品完成。

---

## 2. 主路径（每一切片）

```text
OPEN 写入（Issue/PR 为载体）
  → 实现 + 窄测 + push
  → 评论 CANDIDATE
       · 完整 40 字 SHA
       · 验收项 → 证据映射
       · 未证项标 BLOCKED
  →（并行）CI 绿 + 独立审查（另一只读上下文）
  → Ready（若需）
  → 有人值守 merge → main
  → CLEAR 写入窗（或下一批修订再 OPEN）
```

### CANDIDATE 评论模板

```markdown
## CANDIDATE
- SHA: `<40-char>`
- PR: #
- 验收:
  - [ ] <项> → 证据: <测试/日志/截图路径>
- BLOCKED: <无 | 列表>
- 范围外: edu / 定价 FIXED / …
```

### 独立审查

- 绑定 **当前完整 SHA**；`PASS` | `REVISE` | `BLOCKED`。  
- **写入者不能给自己出具独立审查 PASS。**  
- 租户/鉴权/SSE 边界：需要审查侧或 CI 真路径证据，不能只靠字符串扫描。  
- 产品 diff 变更或手改冲突 → 旧审查作废；仅无冲突 base merge 且 diff 字节级相同可复用业务结论，但仍需当前 head 的 CI + 窄审查。

### 合并

- **禁止** 无人值守合并 main（见 MVP-3DAY S8）。  
- CI 红不得合；审查 REVISE 先回写入。  
- 本仓无 Merge Queue 时：对齐 main → CI → 审 → 值守合。

---

## 3. 风险档（pico 精简）

| 档 | 例子 | 门禁 |
|----|------|------|
| 绿 | 文案、窄 UI、单测 | CI + 自检；可薄审查 |
| 黄 | API 鉴权、membership、SSE、openai-compat、编排 | **独立 exact-SHA 审查** |
| 红 | 密钥模型、禁用安全开关、破坏唯一 AI 账本 | 独立审查 + 业主知悉 |

---

## 4. 共享事实只在 GitHub

- 进度、SHA、CI、审查结论写在 **同一 parent Issue 或 PR**。  
- 不另建「状态数据库」或长期 mailbox。  
- 不要求用户转发 CI 日志或做技术判断。

---

## 5. 与当前 polish 切片的对齐

| 切片 | 载体 | 写入 | 门禁 |
|------|------|------|------|
| L1b SSE/auth/membership | Issue #21 · PR #22 | 本窗 | 黄：CANDIDATE + CI + **独立审查** 后再值守合 |
| L2 真流式 | 续 #21 或新 PR | 写入 | 同上 |
| L3 壳收敛 | 新 PR | 写入 | 黄/产品选择需业主一句 |

**收费 FIXED / edu 联调：** 非本流程默认范围，除非业主另令。

---

## 6. 启动预检（每个写入窗）

1. `git fetch`；记录 main tip 完整 SHA  
2. 读 `AGENTS.md`、`docs/WORKFLOW.md`、`docs/HANDOFF.md`、相关 Issue/PR  
3. 同步 CI；本地 lint/相关 pytest  
4. 输出短校准（目标 / 分支 / 非目标）后动手  
5. 结束前：CANDIDATE 或明确 blocker，**不自 PASS**
