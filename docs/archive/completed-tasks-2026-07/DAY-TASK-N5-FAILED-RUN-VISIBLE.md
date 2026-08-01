# 日间任务 · N5 失败/取消 Run 可见

```
TYPE: DAY
STATUS: COMPLETED · historical
RISK: 黄 · FAST
PRIOR: N4 timeline 已合 #78
```

## 目标

在 N4 时间线基础上：

1. `run` 状态 `failed` / `cancelled` 在时间线或结果区 **明确展示**（中文短句 + 错误码若有）  
2. 工具 `tool.result` ok=false 时显示失败而非静默  
3. 若已有 cancel API：聊天/结果区提供「停止」入口（最小）；没有则文档说明仅 API  
4. 单测或组件测覆盖失败事件摘要  

## 非目标

M5、像素、队列化 worker。

## 给执行（见 EXECUTION-QUEUE EQ-004）
