**Execution queue:** [EXECUTION-QUEUE.md](./EXECUTION-QUEUE.md)

# 验证窗任务队列（总管直派 · 无需业主转贴）

```
DOC: docs/VALIDATION-QUEUE.md
STATUS: BINDING
ROLE: ③ 验证窗 / 本地 heartbeat **唯一派工入口**
WRITER: ① 总管（Grok）更新本文件并合 main（或绿档代合）
EXEC: ③ 每轮只读 **本文件 + 所列 PR**，禁止只靠聊天
```

## 0. 机制（人话）

```text
总管改本文件 → push/合 main
验证窗自动任务每 N 分钟 git pull（或 gh）读本文件
有 OPEN 且门槛满足 → 测 → ## TEST REPORT 贴指定 PR
测完把条目改为 DONE（验证窗可提小 PR 回写，或总管收口改）
```

**业主不必每次复制长提示词。**  
**上下文默认不清理**（`context_reset: false`）；见 [`docs/CONTEXT-POLICY.md`](./CONTEXT-POLICY.md)。  
聊天里的「给：③」只是备份；**以本文件为准。**

---

## 1. 验证窗自动任务应改成的固定提示（一次性配置）

把本地 heartbeat **正文换成下面这段**（可微调路径），**不要再贴超长临时文**：

```text
你是 Pico 独立验证窗。工作区：本地 pico clone。
每次：
1) git fetch && git checkout main && git pull --ff-only
2) 完整阅读 docs/VALIDATION-QUEUE.md
3) 只处理 status: OPEN 的条目；忽略 DONE/CANCELLED
4) 每条的 deploy_gate / test_plan 必须满足才测；否则静默等待（勿刷屏 BLOCKED）
5) 测完在 target_pr 评论 ## TEST REPORT；然后尽量把该条 status 改为 DONE（小 PR 或评论请总管改）
HARD: 只 pico；禁 edu-cloud；禁 PROXY=1；禁打印 key；禁用 CI 代替生产；禁假 DEPLOYED。
CONTEXT: 默认不清理。仅 context_reset: true 才清会话；漏写=false。
```

频率：建议 10–15 分钟。任务名可固定：`Pico VALIDATION-QUEUE`。

---

## 2. 当前队列

### VQ-001 · N2 UI run-once 复测（#72）

```yaml
id: VQ-001
status: DONE
done_note: "2026-07-31 TEST REPORT PASS on #72 (UI run-once + N3/P0 cross)"
priority: P0
target_pr: 72
related: [64, 70, 71, 72]
title: 公网 UI「运行一次」复测 + N3 交叉
deploy_gate:
  - PR 72 has ## DEPLOYED
  - production health.git_sha equals deployed main SHA (expect 77e3181… or newer containing #72)
  - production ancestry includes #70 merge 1a0bd672e3aab4831edb124c2f8f5ddd148a6a9b
test_plan:
  - A: 公网 UI 点「运行一次」必须产生 Task/Run/Artifact（禁止仅用回环代替 UI）
  - B: skill.summarize 有工具；【Pico-Skill:skill-reead】→ skill.unknown tools=[] 无写入
  - C: Bearer pico-dev → 401/403
report:
  - ## TEST REPORT on PR #72 (main)
  - optional cross note on #70 if not already PASS for same SHA
on_done: set status DONE; pause heartbeat if no other OPEN
```

### VQ-002 · N4 Run 时间线（部署后）

```yaml
id: VQ-002
status: DONE
done_note: "2026-07-31 production TEST REPORT on #78: overall FAIL; N4 timeline/run-once/P0 PASS, skill.unknown artifact write FAIL"
priority: P1
context_reset: false
target_pr: null
related_docs: [docs/DAY-TASK-N4-RUN-TIMELINE.md]
title: N4 过程可见验收
deploy_gate:
  - A merged PR implementing N4 exists with ## DEPLOYED
  - production health.git_sha equals that deploy SHA
  - (locate PR by title/path: Run timeline / events UI / DAY-TASK-N4)
test_plan:
  - A: 公网 pico-agent 真聊触发至少 1 次工具；UI 可见步骤/工具名（截图或 DOM 描述）
  - B: skill-reead 路径不出现非法工具写入；若 UI 显示 snapshot 则 tools 为空或 unknown
  - C: 自动化「运行一次」仍 PASS（防回归）
  - D: Bearer pico-dev → 401/403
report:
  - ## TEST REPORT on the N4 implementation PR
on_done: set status DONE
```

### VQ-003 · N5 失败态可见（等 EQ-004 部署）

```yaml
id: VQ-003
status: OPEN
priority: P0
context_reset: false
target_pr: 82
title: N5 failed tool/run visible
deploy_gate:
  - PR 82 has ## DEPLOYED
  - health.git_sha equals production deploy of N5 (main contains #82; tip may be 8cabb496… or newer)
test_plan:
  - 触发一次会失败的工具或取消路径（安全范围内）；UI 显示失败/取消
  - 正常工具路径不回归
  - pico-dev 401
report:
  - ## TEST REPORT on N5 PR
on_done: set status DONE
```

### VQ-004 · N6 能力中心工具展示

```yaml
id: VQ-004
status: OPEN
priority: P1
context_reset: false
target_pr: null
title: Skill hub tools visible
deploy_gate:
  - EQ-007 implementation PR ## DEPLOYED
test_plan:
  - 能力中心 skill.summarize 显示工具列表
  - skill.chat 为无工具/纯对话
  - skill.write_s7 含 propose 与需确认语义
  - 主路径抽检登录+真聊
report:
  - ## TEST REPORT on N6 PR
on_done: set status DONE
```

### VQ-000 · 模板（勿删）

```yaml
id: VQ-000
status: CANCELLED
title: TEMPLATE
target_pr: 0
deploy_gate: []
test_plan: []
```

---

## 3. 总管如何派新任务（不经过业主聊天）

1. 编辑本文件，在「当前队列」顶部新增 `VQ-00x`，`status: OPEN`  
2. 写清 `target_pr` / `deploy_gate` / `test_plan` / `report`  
3. 合 main（绿档文档可 FAST/总管合）  
4. 验证窗下一轮 pull 即自动接到  

可选：同时在目标 PR 留一句 `VALIDATION-QUEUE VQ-00x OPEN` 方便人读。

---

## 4. 与 SPRINT-FAST

- 仍遵守 SLA、禁假报告  
- 本文件是 **③ 的 inbox**；② 的 inbox 仍是 DAY-TASK / PR  
