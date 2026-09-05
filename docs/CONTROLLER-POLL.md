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

- **对话总管限制：** 聊天回合才醒。
**7×24 已停：** [`docs/CONTROLLER-BOT.md`](./CONTROLLER-BOT.md) 定时空转已关；只留手动 `workflow_dispatch`。
- 对话仍在时：业主一问或间隙即轮询推进  
- 目标：被唤醒后 **立即** poll → 合/派/收口  
- 真源仍是 GitHub，不靠聊天记忆  
- 业主可在验证/执行 heartbeat 旁加一句「@总管 请 poll」的提醒，但总管仍须有对话回合

## 本轮动作模板

```text
poll → 分类（可合 / 等验 / 阻塞 / 空闲）
  → 更新队列 status
  → 空闲则派 EQ/VQ 新条目
  → 红档写 ## REVIEW
```

## 派工与上下文（固化）

- 更新 EXECUTION/VALIDATION 队列时 **必须** 带 `context_reset: false|true`
- **默认 false**；无业主值守时 **禁止** 要求各窗清上下文，除非会话已串台且提供冷启动必读
- 漏写按 false 执行
