# 总管 Bot（已停定时）

```
DOC: docs/CONTROLLER-BOT.md
STATUS: OFF — 定时空转已停；只留 workflow_dispatch
DATE: 2026-09-05
```

## 1. 解决什么问题

定时 poll 已停（空转写 #475、黄档默代合）。脚本仍在 `scripts/controller_bot.py`，只许 `workflow_dispatch`，默认 dry_run、不合 PR。

## 2. 会做什么 / 不会做什么

| 做 | 不做 |
|----|------|
| 扫 open PR | 不写 edu-cloud |
| CI 绿 + 黄/FAST（或 docs）→ **可自动合 main** | 不自动合 **RISK:红** |
| 在 PR / 日志 Issue 评论 `## CONTROLLER-BOT` | **不部署生产**（仍 E3） |
| 创建/更新 `[controller-bot] poll log` Issue | 不打印密钥 |
| | 不替代验证窗 ## TEST REPORT |

## 3. 开关

| 变量 | 含义 |
|------|------|
| `workflow_dispatch` | 手动跑一轮；默认 dry_run、不合 PR |
| `CONTROLLER_DRY_RUN=1` | 本地只打印 |

定时已关。需要代合时手动 Run workflow，并显式把 auto_merge 设为 true、dry_run 设为 false。

## 4. 本地只打印

```bash
export GITHUB_TOKEN=ghp_xxx
export CONTROLLER_DRY_RUN=1
python scripts/controller_bot.py poll
```

禁止再挂 ECS cron。需要代合用 GitHub 手动 Run workflow。  
