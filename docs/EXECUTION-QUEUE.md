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

> **MANUAL_DISPATCH 2026-07-31**：业主要求手动派发。E2 必须认领 EQ-013+014；E3 必须部署 tip `eaf9875`+；E1 待命或协助 E2 API。context_reset: false。

### EQ-031 · 部署最新可靠性与清理主线

```yaml
id: EQ-031
status: DONE
done_note: "2026-08-01 E3 deployed origin/main 768d0bd56858acacf859cf9a8cd357f68dc2f1ba; exact-SHA CI green; production HEAD/health.git_sha exact-match; local/public login 200; protected ports loopback-only; pico-dev 401; ## DEPLOYED on #122"
priority: P0
context_reset: false
assignee: E3
task_type: DEPLOY
target_pr: 122
target_floor_sha: af31ccce6c5a33b915a8e847dcb10861d4071f26
target_sha_rule: "认领时 origin/main 的完整 SHA；必须包含 target_floor_sha，且部署时仍为 origin/main tip"
title: 部署最新 main（含 #119/#120/#122）并回写诚实生产证据
files_lease:
  - docs/EXECUTION-QUEUE.md  # 仅用于请求总管收口；部署时不改业务代码
preflight:
  - production /opt/pico worktree clean; dirty means BLOCKED, never stash/reset
  - target exact-SHA main CI green
  - bootstrap scripts/prod-update.sh from the target Git object; do not trust an older checked-out script
deliver:
  - "## CLAIM E3 on PR #122 with target full SHA"
  - production HEAD == health.git_sha == claimed origin/main tip
  - local and public /login HTTP 200 with product HTML
  - 18765/27017/8080 not bound to 0.0.0.0 or wildcard
  - production Bearer pico-dev returns 401
  - "## DEPLOYED or ## BLOCKED on PR #122; no product PASS claim"
avoid:
  - PROXY=1
  - printing or changing secrets
  - edu-cloud or any other repository
  - repeating VQ-008 cancellation validation without regression evidence
result_sink: https://github.com/juanwan99/pico/pull/122
```


### EQ-001 · N4 Run 过程时间线

```yaml
id: EQ-001
status: DONE
done_note: "N4 #78 merged+DEPLOYED 4a5dc7b"
priority: P0
assignee: E2
fallback: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N4-RUN-TIMELINE.md
title: N4 Run 事件时间线最小可见
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
  - apps/librechat/**/data-provider/**
  - tests/**  # only if adding UI/proxy tests
  - docs/archive/completed-tasks-2026-07/DAY-TASK-N4-RUN-TIMELINE.md  # optional notes only
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
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N5-FAILED-RUN-VISIBLE.md
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
status: CANCELLED
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

### EQ-007 · N6 能力中心技能工具只读

```yaml
id: EQ-007
status: DONE
done_note: "N6 #89 merged; await DEPLOYED+VQ-004"
priority: P0
context_reset: false
assignee: E2
fallback: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N6-SKILL-HUB-TOOLS.md
title: Skill hub shows policy-bound tools (read-only)
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
  - services/api/**  # if adding GET /v1/skills
  - services/orchestrator/pico_orchestrator/skill_policy.py  # export only if needed
deliver:
  - PR RISK:黄 FAST
  - ## DEPLOYED
  - unlocks VQ-004
```

### EQ-008 · N6b 限流 membership 键

```yaml
id: EQ-008
status: DONE
done_note: "N6b #87 merged 597acfb; check DEPLOYED"
priority: P1
context_reset: false
assignee: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N6-RATELIMIT-MEMBERSHIP.md
title: Rate limit key prefers membership_id
files_lease:
  - services/api/app/rate_limit.py
  - services/api/app/openai_compat.py
  - services/api/app/main.py
  - tests/unit/**
deliver:
  - PR RISK:黄 FAST
  - ## DEPLOYED
```

### EQ-009 · 巡检

```yaml
id: EQ-009
status: DONE
done_note: "superseded by EQ-016 deploy tip"
priority: P2
context_reset: false
assignee: E3
title: Deploy #82/#tip if needed; queue DONE; surface BLOCKED to controller
files_lease:
  - docs/EXECUTION-QUEUE.md
  - docs/VALIDATION-QUEUE.md
```

### EQ-010 · N7 生产 readiness 探针增强

```yaml
id: EQ-010
status: DONE
done_note: "N7 health #91 merged"
priority: P1
context_reset: false
assignee: E1
title: /health 暴露 edu_mode、rate_limit 配置摘要（无密钥）+ selftest 钩子文档
files_lease:
  - services/api/app/main.py
  - scripts/agent-selftest.sh
  - docs/**
deliver:
  - PR 黄 FAST；不打印 secrets
```

### EQ-011 · N7 UI 能力中心空态与加载

```yaml
id: EQ-011
status: CANCELLED
done_note: "no hub failure reported; VQ-004 handles product"
priority: P2
context_reset: false
assignee: E2
title: 仅当 #89 部署后能力中心加载失败时修空态/重试；无则标 CANCELLED
files_lease:
  - apps/librechat/client/src/components/Workbench/**
depends: EQ-007 DEPLOYED + VQ-004
```

### EQ-012 · 部署巡检

```yaml
id: EQ-012
status: DONE
done_note: "superseded by EQ-016"
priority: P0
context_reset: false
assignee: E3
title: 部署 main tip（含 #87+#89）## DEPLOYED；队列卫生
files_lease:
  - docs/EXECUTION-QUEUE.md
  - docs/VALIDATION-QUEUE.md
```

### EQ-013 · N7 历史 Run 时间线

```yaml
id: EQ-013
status: DONE
done_note: "history timeline production PASS; closed with N7 stop line"
priority: P0
context_reset: false
assignee: E2
fallback: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N7-HISTORY-RUN-TIMELINE.md
title: History task opens run timeline
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
deliver:
  - PR RISK:黄 FAST + ## CANDIDATE
  - ## DEPLOYED after merge
  - unlocks VQ-005
```

### EQ-014 · N7 运行中停止

```yaml
id: EQ-014
status: DONE
done_note: "cancel UI path closed; VQ-008 PASS cancelled"
priority: P0
context_reset: false
assignee: E2
fallback: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N7-CANCEL-RUN.md
title: Cancel in-flight run from UI
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
note: 可与 EQ-013 同 PR 或连续两 PR；lease 同属 E2
deliver:
  - PR RISK:黄 FAST
  - ## DEPLOYED
  - unlocks VQ-005
```

### EQ-015 · N7b 事件 seq 唯一

```yaml
id: EQ-015
status: DONE
done_note: "#97 merged eaf9875; await E3 DEPLOYED"
priority: P1
context_reset: false
assignee: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N7-EVENT-SEQ-UNIQUE.md
title: Event (run_id, seq) unique + foreign_keys
files_lease:
  - services/api/**
  - services/orchestrator/**
  - tests/**
deliver:
  - PR RISK:黄 FAST
  - ## DEPLOYED
```

### EQ-016 · 部署与队列卫生（必做）

```yaml
id: EQ-016
status: DONE
done_note: "E3 deployed main 29119098492a06a8ecbfadd7864afc34674ec8e8; backfilled ## DEPLOYED on #94/#97/#98/#99; promoted and merged tested docs PRs #86/#93"
priority: P0
context_reset: false
assignee: E3
title: 部署 main tip（含 #89/#91/#94 及后续 N7）→ ## DEPLOYED；DRAFT #86/#93 有 TEST 则转正合入；队列 DONE 回写
files_lease:
  - docs/EXECUTION-QUEUE.md
  - docs/VALIDATION-QUEUE.md
deliver:
  - production health == main tip
  - comment ## DEPLOYED on latest feature PRs missing it
```

### EQ-017 · 验证配合 · 生产 tip 对齐 VQ-005

```yaml
id: EQ-017
status: DONE
done_note: "E3 rebuilt and aligned production HEAD/health.git_sha to 28107fa2d882900dae1aa000e800f46c373b9f01; posted ## DEPLOYED on #100"
priority: P0
context_reset: false
assignee: E3
title: 确认 production health == main tip（含 #99/#100）；缺则部署；为 VQ-005 扫障
files_lease:
  - docs/EXECUTION-QUEUE.md
deliver:
  - ## DEPLOYED or comment tip SHA already live on #99 or #100
```

### EQ-018 · N8 未知 skill 无旁路产物

```yaml
id: EQ-018
status: DONE
done_note: "#102 merged 28107fa; CI green and production health.git_sha exact-match DEPLOYED"
priority: P1
context_reset: false
assignee: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N8-UNKNOWN-SKILL-NO-ARTIFACT.md
title: unknown skill cannot create artifacts via extractor
files_lease:
  - services/api/**
  - services/orchestrator/**
  - tests/**
deliver:
  - PR 黄 FAST + ## DEPLOYED
```

### EQ-019 · VQ-005 FAIL 时补实现

```yaml
id: EQ-019
status: DONE
done_note: "superseded by #104/#107/#108; VQ-008 PASS"
priority: P0
context_reset: false
assignee: E2
title: 仅当 VQ-005 FAIL 时补历史时间线/停止 UI；PASS 则标 CANCELLED
files_lease:
  - apps/librechat/client/**
depends: VQ-005
```

### EQ-023 · N7 停止根治（VQ-006 FAIL）

```yaml
id: EQ-023
status: DONE
done_note: "#108 merged fa1c140; Chromium browser proof PASS; E3 deployed exact main SHA (EQ-024)"
priority: P0
context_reset: false
assignee: E2
fallback: E1
task_doc: docs/archive/completed-tasks-2026-07/DAY-TASK-N7-CANCEL-ROOTFIX.md
title: Root-fix public stop → POST cancel 200 + cancelled
files_lease:
  - apps/librechat/client/**
  - apps/librechat/api/server/routes/pico.js
  - tests/**
deliver:
  - PR with Network proof checklist
  - ## DEPLOYED
  - VQ-007
```

### EQ-024 · 部署根治 tip

```yaml
id: EQ-024
status: DONE
done_note: "2026-07-31 E3 deployed EQ-023 tip fa1c1402a5d2b828f4fdb720a70681bf8e2a8b2a; CI green; production HEAD/health.git_sha exact-match; ## DEPLOYED on #108"
priority: P0
context_reset: false
assignee: E3
title: Deploy EQ-023 tip; ## DEPLOYED on fix PR
depends: EQ-023 merge
```

### EQ-025 · cancel API/proxy 协助

```yaml
id: EQ-025
status: CANCELLED
done_note: "VQ-008 PASS; cancel API/proxy assistance no longer needed"
priority: P1
context_reset: false
assignee: E1
title: 仅当 Network 显示请求已发但 4xx/5xx/无账本时修 API/proxy
files_lease:
  - services/api/**
  - apps/librechat/api/server/routes/pico.js
```

### EQ-026 · 保障 VQ-007 可测

```yaml
id: EQ-026
status: DONE
done_note: "2026-07-31 E3 confirmed production HEAD/health.git_sha fa1c1402a5d2b828f4fdb720a70681bf8e2a8b2a contains #108 lineage; public login 200; protected ports loopback-only; VQ-007 testable"
priority: P0
context_reset: false
assignee: E3
title: 确认 production health 含 #108（fa1c140 或更新 tip）；缺则部署；在 #108 再确认 ## DEPLOYED 或 already aligned
files_lease:
  - docs/**
```

### EQ-027 · VQ-007 FAIL 待命

```yaml
id: EQ-027
status: DONE
done_note: "no UI FAIL after #117; VQ-008 PASS"
priority: P0
context_reset: false
assignee: E2
title: 仅当 #108 出现 VQ-007 TEST REPORT FAIL 时再修；无报告则 idle
files_lease:
  - apps/librechat/client/**
```

### EQ-028 · idle 卫生

```yaml
id: EQ-028
status: CANCELLED
done_note: "VQ-008 PASS; contingency idle slot closed"
priority: P2
context_reset: false
assignee: E1
title: idle；除非 VQ-007 FAIL 且根因在 API/proxy
```

### EQ-029 · 部署 #114 cancel 认领（P0）

```yaml
id: EQ-029
status: DONE
done_note: "2026-07-31 E3 rebuilt pico-api and deployed main f8c36bdc339aa2e2124b10eaf881a9d16024e54c containing #114; production HEAD/health.git_sha exact-match; public login 200; protected ports loopback-only; ## DEPLOYED on #114"
priority: P0
context_reset: false
assignee: E3
fallback: E1
title: Deploy main tip 880b714 (#114) — honor cancel in agent streams
note: |
  E1 BLOCKED: cannot resolve Host pico-prod from its runtime.
  E3 用既有 aliyun→生产 路径（DEPLOY-PROD-CHECKLIST / 既往成功路径），禁止假 DEPLOYED。
deliver:
  - production HEAD == health.git_sha == 880b71402a701f33366dadbd20149516b90cdc9a（或更新 main 若已前进）
  - rebuild pico-api（必）+ librechat 若需要
  - ## DEPLOYED on PR #114
  - unlock VQ-007 retest
files_lease:
  - docs/EXECUTION-QUEUE.md
```

### EQ-030 · VQ-007 复测后待命

```yaml
id: EQ-030
status: DONE
done_note: "no UI FAIL; VQ-008 PASS"
priority: P1
context_reset: false
assignee: E2
title: idle unless VQ-007 FAIL is UI-side after #114 deploy
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
