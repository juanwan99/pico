# 日间任务 · N4 Run 过程时间线（最小可见）

```
TYPE: DAY
SPRINT: docs/SPRINT-FAST.md（7 日窗内）
STATUS: COMPLETED · historical
RISK: 黄 · FAST 代合可
PRIOR: N1/N2/N3 已 PASS（含 #72 UI run-once）
```

## 目标

用户跑 `pico-agent` / 自动化后，**能看见过程**（不只最终一句回复）：

- 至少展示本 Run 的：`skill.snapshot`（若有）、`tool.call` / `tool.result`、`artifact.created`（有则显示）
- 数据源：已有 `GET /v1/runs/{run_id}/events`（经 LibreChat `/api/pico` 代理；**若缺 GET 代理则一并补齐**）
- 展示位置：优先 **结果区 / 右栏 / 任务详情** 任一稳定入口；不要大改 IA
- 空态：无事件时一行「暂无步骤」
- 桌面 1280 可用；不要求像素完美

## 非目标

M5、像素、PG、队列、新 Skill 批量、重做 SSE 协议。

## 验收

1. 真聊一次带工具的 agent → UI 能看到工具名或步骤列表  
2. 未知 skill 路径：可见 skill.unknown 或 tools 为空的 snapshot（若事件有）  
3. 代理 401 仍在；不暴露密钥  

## 【给：② 执行窗 · ECS】

```text
读 docs/DAY-TASK-N4-RUN-TIMELINE.md。
实现最小 Run 事件时间线 + 必要时补 pico.js GET 代理。
PR → CI → RISK:黄 FAST 代合 → 部署（librechat 必）→ ## DEPLOYED。
强制 GitHub 回写。禁 edu-cloud / PROXY=1。
```

## 完成后

总管将 VQ-002 保持 OPEN 供 ③ 自动测（见 VALIDATION-QUEUE）。
