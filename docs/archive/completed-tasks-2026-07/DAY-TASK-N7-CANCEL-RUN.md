# 日间任务 · N7 运行中取消（最小）

```
TYPE: DAY
STATUS: COMPLETED · historical
RISK: 黄 · FAST
context_reset: false
```

## 目标

对 **running/queued** 的 Run：

1. 确认 API `POST /v1/runs/{id}/cancel` 可用且经 LibreChat pico 代理  
2. 结果区或任务条提供 **「停止」** 按钮（仅非终态显示）  
3. 取消后时间线/状态显示 cancelled（衔接 N5）  
4. 单测或路由测：代理 + 权限  

## 非目标

分布式强制杀进程、多实例 claim。
