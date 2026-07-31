# 总管轮询（Grok · BINDING）

```
DOC: docs/CONTROLLER-POLL.md
STATUS: BINDING
ROLE: ① 总管
```

## 职责

总管 **主动轮询 GitHub**（不依赖业主每次喊「审查」）：

1. `main` tip / open PR / 最近 merge  
2. `docs/EXECUTION-QUEUE.md` · `docs/VALIDATION-QUEUE.md`  
3. 活跃 PR 评论：`## CLAIM` / `## CANDIDATE` / `## DEPLOYED` / `## TEST REPORT` / `## BLOCKED`  
4. 据结果：**审合红档、标 DONE、派下一条 EQ/VQ、回 BLOCKED**  

## 节奏

- 对话仍在时：业主一问或间隙即轮询推进  
- 目标：Codex 回写后 **尽快** 有总管反应（合/派/收口）  
- 真源仍是 GitHub，不靠聊天记忆  

## 本轮动作模板

```text
poll → 分类（可合 / 等验 / 阻塞 / 空闲）
  → 更新队列 status
  → 空闲则派 EQ/VQ 新条目
  → 红档写 ## REVIEW
```
