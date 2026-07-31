# 已知借债清单（快模式 · 不堵本周北星）

```
DOC: docs/DEBT-BACKLOG.md
STATUS: LIVING
```

| ID | 债 | 来源 | 目标窗口 |
|----|-----|------|----------|
| D1 | SQLite 单机；无正式迁移框架 | 体检 P1 | 后置 |
| D2 | 自动化无 claim/lease/持久队列 | 体检 P1 | 后置 |
| D3 | Change handoff 无 outbox | 体检 P1 | 后置 |
| D4 | 事件 seq 无唯一约束 | 体检 P1 | 后置 |
| D5 | 限流仅单机 IP 内存 | P0 有意简化 | 多实例前必换 |
| D6 | usage 为估计值 | P0 | 后置接上游 |
| D7 | LibreChat CI 非完整 npm | 体检 P1 | 后置 |
| D8 | Kimi CLI 依赖链 vs 自研循环叙事 | 体检 P1 | 后置 |
| D9 | 像素 / WorkBuddy 全面对标 | 产品后置 | 后置 |
| D10 | M5 edu 真联调 | 需授权 | 授权后 |

新增借债：PR 写 `DEBT: Dn 简述` 并追加本表一行。
