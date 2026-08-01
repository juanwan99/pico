# 日间任务 · N7 历史任务打开 Run 时间线

```
TYPE: DAY
STATUS: COMPLETED · historical
RISK: 黄 · FAST
context_reset: false
```

## 目标

用户在 **历史 / 任务列表 / 项目资产关联任务** 中选中一条已完成 Task/Run 时，结果区 **Run 时间线** 加载该 `run_id` 的事件（复用 N4 `GET .../events` + RunTimeline），不只当前会话最新一条。

## 验收

1. 完成一次 agent 任务后，从历史进入仍能看到 skill/tool/artifact 步骤  
2. 无事件 →「暂无步骤」  
3. 不破坏当前会话 live 时间线  

## 非目标

M5、像素、全站重构。
