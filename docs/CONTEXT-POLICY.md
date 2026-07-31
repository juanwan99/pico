# 上下文策略（执行/验证窗 · BINDING）

```
DOC: docs/CONTEXT-POLICY.md
STATUS: BINDING
DATE: 2026-07-31
```

## 1. 默认（无业主值守时更重要）

| 项 | 规则 |
|----|------|
| **默认** | **不清理上下文**（`context_reset: false`） |
| 原因 | 业主不值守时，清上下文 = 丢失队列约定、lease、生产路径与未写完的 CLAIM，窗会「失忆停工」 |
| 总管派工 | **必须显式写** `context_reset: false \| true`；**漏写 = 视为 false（不清理）** |

## 2. 何时才允许清理（true）

仅当条目或总管评论同时满足：

1. 明确写了 `context_reset: true` 或「请清理上下文 /new」  
2. 且给出 **冷启动最小必读**（至少：本队列文件 + 当前 EQ/VQ id + HARD）  

否则执行/验证窗 **禁止** 自行 /new 或清空会话。

## 3. 队列字段（推荐）

每个 EQ/VQ 条目可带：

```yaml
context_reset: false   # 默认；true 仅总管显式要求
```

## 4. 窗侧行为

- 读到 `false` 或缺失：继续当前会话记忆 + **仍以 git pull 后的队列文件为准**（文件优先于旧记忆）  
- 读到 `true`：清理后只按冷启动必读重建  
- **文件与记忆冲突：以 main 上队列/任务书为准**

## 5. 总管义务

- 派工（改 EXECUTION/VALIDATION-QUEUE 或 PR 评论）时写明 context_reset  
- 默认写 `false`；仅在会话已严重污染/串台时用 `true`  
