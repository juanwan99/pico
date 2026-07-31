# 日间任务 · N6b 限流键优先 membership

```
TYPE: DAY
STATUS: OPEN
RISK: 黄 · FAST
context_reset: false
```

## 目标

`ChatRateLimitMiddleware`：在能解析到 principal/membership 时，**限流键用 membership_id**（可带 school 前缀）；否则回退 IP。

- 单测：两 membership 同 IP 不互相占满（在可测范围内）
- 生产默认 RPM/并发配置不变  
- 不引入 redis（仍单机内存）

## 非目标

多实例分布式限流。
