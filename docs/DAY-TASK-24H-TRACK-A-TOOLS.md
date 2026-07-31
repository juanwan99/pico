# 日间 · 轨 A · 工具内核与 Agent 真调用

```
TYPE: DAY
TRACK: A
PLAN: docs/STANDALONE-AI-24H.md
LEASES: services/orchestrator/** · services/api 工具相关 · tests · scripts smoke
FORBID: 大改 LibreChat 页面 · 写 edu-cloud · M5 live
```

## 给 Codex-A

```text
git fetch && checkout main && pull --ff-only
读 docs/STANDALONE-AI-24H.md §2 与本文。
实现全局白名单工具（membership 隔离、产物走 Artifact）：
- workspace_write_file
- workspace_read_file
- workspace_list_files
- structured_outline 或 json_extract
- calculator
保留 pico_propose_change / echo / fake_edu_*（不依赖 edu 完成演示）
Runner/pico-agent 多步能真实调用 ≥3 个新工具。
单测+集成测；scripts 冒烟可选。
PR → CANDIDATE → CI → 等总管合 main（勿自合黄/红）。
报告 track A · 工具列表 · 测结果。
HARD：禁止任意 shell；禁止乱写宿主机路径；禁 PROXY=1。
```

## 验收

- [ ] ≥5 个新/强化工具在 gateway
- [ ] 测证明 tool call → artifact 或结构化结果
- [ ] 不破坏 S7 propose
