# 执行窗任务队列（总管直派 · 三窗轮值 · 无需业主转贴）

```
DOC: docs/EXECUTION-QUEUE.md
STATUS: BINDING
ROLE: ② 执行窗 ×3（ECS Codex）**唯一派工入口**
WRITER: ① 总管更新本文件并合 main
PAIR: docs/VALIDATION-QUEUE.md（验证）· docs/SPRINT-FAST.md · docs/RACI-GROK-CODEX.md
```

## 0. 机制

```text
总管改本文件 → 合 main
三个执行窗各自定时 git pull，读本文件
认领 status:OPEN 且 assignee 匹配（或 open 可 claim）的条目
做完：开 PR → CANDIDATE →（黄 FAST 代合）→ DEPLOYED 回写
把条目 status 改为 DONE（小 PR 改本文件 或 总管收口）
```

**业主不必转贴。** 聊天派工仅备份。

**上下文：** 默认 **不清理**（`context_reset: false`）。详见 [`docs/CONTEXT-POLICY.md`](./CONTEXT-POLICY.md)。总管漏写 = 不清理。无业主值守时禁止窗自作主张 /new。

---

## 1. 三窗身份（固定）

| 窗 ID | 建议 heartbeat 名 | 默认职责带 |
|-------|-------------------|------------|
| **E1** | `Pico EXEC-E1` | API / orchestrator / 安全 / 工具 |
| **E2** | `Pico EXEC-E2` | LibreChat 前端 / proxy / 工作台 UI |
| **E3** | `Pico EXEC-E3` | 部署专班 / 文档绿档 / 捡漏与 DEBT 小修 |

可抢同一 `assignee: ANY` 任务，但 **同一 `id` 同时只能一个窗 claim**（见 §3）。

---

## 2. 三窗共用固定提示词（一次性配置 · 只改窗口 ID）

每个执行窗创建 **一个** 定时任务，正文用下面模板，**仅替换 `WINDOW_ID=E1|E2|E3`**：

```text
你是 Pico 执行窗 WINDOW_ID=E1（改成 E1 或 E2 或 E3）。
工作区：dev-ECS 上 juanwan99/pico clone（可跳板 pico-prod）。
每次唤醒：
1) git fetch origin && git checkout main && git pull --ff-only
2) 完整阅读 docs/EXECUTION-QUEUE.md 与 docs/SPRINT-FAST.md
3) 只处理 status:OPEN 的条目：
   - assignee 为你的 WINDOW_ID，或 assignee: ANY 且无人 CLAIMED
4) 认领：在目标分支/PR 或队列条目评论 `## CLAIM E1`（用你的 ID）；若已有他人 CLAIM，换下一条
5) 按 task_doc / 描述实现 → PR → ## CANDIDATE + exact SHA
6) CI 绿后：绿/黄按 SPRINT-FAST 代合；红档等总管
7) 合后 2h 内跳板部署 → ## DEPLOYED 或 ## BLOCKED
8) 尽量把本文件对应条目改为 DONE（小 PR）或评论请总管改
HARD：只 pico；禁 edu-cloud；禁 PROXY=1；禁打印 key；无 GitHub 回写=未交付；15 分钟卡住必须 ## BLOCKED。
LEASE：遵守条目 files_lease；冲突则让出。
CONTEXT：默认不清理会话。仅当条目或总管写明 context_reset: true 才 /new；漏写=false。文件与记忆冲突以 main 队列为准。
```

频率建议：**10–15 分钟**（或空闲时更短）。  
三窗 **各建一条**，`WINDOW_ID` 分别 E1/E2/E3。

---

## 3. 认领与 lease 规则

| 规则 | 说明 |
|------|------|
| CLAIM | 评论 `## CLAIM E?` + 时间；30 分钟无进度可被其它窗抢 |
| files_lease | 条目列出的路径仅 claim 者可写 |
| 同时 OPEN 多条 | E1/E2/E3 优先拿 assignee 匹配的；ANY 按 priority 高者先 |
| 禁止 | 三窗同改一个文件无 lease；假 DEPLOYED |

---

## 4. 当前队列

### EQ-001 · N4 Run 过程时间线

```yaml
id: EQ-001
status: DONE
done_note: "N4 #78 merged+DEPLOYED 4a5dc7b"
priority: P0
assignee: E2
fallback: E1
task_doc: docs/DAY-TASK-N4-RUN-TIMELINE.md
title: N4 Run 事件时间线最小可见
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
  - apps/librechat/**/data-provider/**
  - tests/**  # only if adding UI/proxy tests
  - docs/DAY-TASK-N4-RUN-TIMELINE.md  # optional notes only
avoid:
  - services/orchestrator/**  # unless must wire event types
deliver:
  - PR with RISK:黄 FAST
  - ## DEPLOYED after merge
  - triggers VALIDATION-QUEUE VQ-002
```

### EQ-002 · N4 若缺 events 代理则由 API 侧协助

```yaml
id: EQ-002
status: CANCELLED
done_note: "N4 未阻塞代理；E2 已交付"
priority: P1
assignee: E1
title: 仅当 E2 阻塞在「无 GET /api/pico/.../events 代理或 API」时接手
files_lease:
  - apps/librechat/api/server/routes/pico.js
  - services/api/**  # only if events API bug
depends: EQ-001 claimed by E2 first 15min
note: 无阻塞则保持 OPEN 但不抢；E2 完成后本条 CANCELLED
```

### EQ-003 · 部署与队列卫生（轮值）

```yaml
id: EQ-003
status: DONE
done_note: "2026-07-31 E3 aligned production HEAD/health.git_sha to b405328b1e034209d4a449cabda1fd50a39a22e9 and posted ## DEPLOYED on #76"
priority: P2
assignee: E3
title: 巡检 — 合 main 未部署的 PR 补 ## DEPLOYED；EXECUTION/VALIDATION 队列 DONE 回写
files_lease:
  - docs/EXECUTION-QUEUE.md
  - docs/VALIDATION-QUEUE.md
  - docs/DEBT-BACKLOG.md
deliver:
  - 部署缺口 ## DEPLOYED 或 ## BLOCKED
  - 小 PR 把已完成条目标 DONE
```

### EQ-004 · N5 失败 Run 可见

```yaml
id: EQ-004
status: DONE
done_note: "PR #82 merged+DEPLOYED at main a79e40fe6ceb567203ecb6888db38cebc2102201; VQ-003 unlocked"
priority: P0
context_reset: false
assignee: E2
fallback: E1
task_doc: docs/DAY-TASK-N5-FAILED-RUN-VISIBLE.md
title: N5 failed/cancelled runs visible on timeline
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
deliver:
  - PR RISK:黄 FAST
  - ## DEPLOYED
  - unlocks VQ-003
```

### EQ-005 · N5 API 错误载荷（若 E2 需要）

```yaml
id: EQ-005
status: OPEN
priority: P2
context_reset: false
assignee: E1
title: 仅当失败 Run 缺 error 字段时补 API/事件
files_lease:
  - services/api/**
  - services/orchestrator/**
depends: EQ-004
```

### EQ-006 · 部署巡检续

```yaml
id: EQ-006
status: DONE
done_note: "2026-07-31 E3 aligned production HEAD/health.git_sha to f9bd81097cfa2e1c53f9b06a157a343aeed73ca0 and posted ## DEPLOYED on #81"
priority: P2
context_reset: false
assignee: E3
title: 确保 #78/#后续 tip 已 DEPLOYED；队列 DONE 回写；BLOCKED 升级总管
files_lease:
  - docs/EXECUTION-QUEUE.md
  - docs/VALIDATION-QUEUE.md
```

### EQ-000 · 模板

```yaml
id: EQ-000
status: CANCELLED
assignee: ANY
title: TEMPLATE
```

---

## 5. 总管如何派工（不经业主）

1. 在本文件「当前队列」顶部加 `EQ-00x`，`status: OPEN`，写 `assignee` / `files_lease` / `task_doc` / **`context_reset: false|true`（默认 false）**  
2. 合 main  
3. 三窗下一轮 pull 自动接到  

---

## 6. 与验证窗

- 执行：`EXECUTION-QUEUE.md`  
- 验证：`VALIDATION-QUEUE.md`  
- 部署后验证由 VQ 条目触发，执行窗不代替正式 ## TEST REPORT  
