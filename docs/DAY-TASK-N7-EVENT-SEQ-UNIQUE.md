# 日间任务 · N7b 事件序号约束（底座）

```
TYPE: DAY
STATUS: OPEN
RISK: 黄 · FAST
context_reset: false
```

## 目标

缓解体检 P1：

1. SQLite/建表：`Event` 增加 `(run_id, seq)` **唯一约束**（迁移或 init 兼容）  
2. 连接打开时 `PRAGMA foreign_keys=ON`（若用 SQLite）  
3. 写入事件用安全分配 seq（避免纯 max+1 无保护）；冲突重试一次  
4. 单测覆盖唯一约束  

## 非目标

迁 PostgreSQL、上队列。
