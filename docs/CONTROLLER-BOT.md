# 总管 Bot（7×24 · BINDING）

```
DOC: docs/CONTROLLER-BOT.md
STATUS: BINDING
DATE: 2026-07-31
```

## 1. 解决什么问题

对话里的 Grok **没有后台时钟**；休眠时不会 poll。  
**Controller Bot** 用 **GitHub Actions 定时**（每 15 分钟）在仓库内轮询并推进，**不依赖业主转贴、不依赖 Grok 对话在线**。

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
| repo **Variable** `CONTROLLER_AUTO_MERGE` | `true`/`false`，默认 workflow 为 true |
| `workflow_dispatch` | 手动跑一轮；可 dry_run |
| `CONTROLLER_DRY_RUN=1` | 本地只打印 |

关闭自动合：GitHub → Settings → Secrets and variables → Actions → Variables → `CONTROLLER_AUTO_MERGE` = `false`。

## 4. 本地 / ECS 也可跑

```bash
export GITHUB_TOKEN=ghp_xxx   # 需要 repo 写权限
export CONTROLLER_AUTO_MERGE=true
python scripts/controller_bot.py poll
```

cron 示例（ECS）：

```cron
*/15 * * * * cd /path/to/pico && GITHUB_TOKEN=... CONTROLLER_AUTO_MERGE=true python3 scripts/controller_bot.py poll >>/tmp/controller-bot.log 2>&1
```

## 5. 与对话总管分工

| 角色 | 职责 |
|------|------|
| **Controller Bot** | 定时合黄/docs、催 CI/红档、写 poll 日志 |
| **Grok 对话总管** | 定北星、改队列、红档深审、产品裁决 |
| **E1/E2/E3** | 实现与部署 |
| **验证窗** | TEST REPORT |

## 6. context_reset

Bot **不**清理任何人会话。派工字段仍见 `CONTEXT-POLICY.md`。

## 7. 首次启用检查

1. 本 workflow 已在 `main`  
2. Actions 页能看到 `controller-bot`；可 **Run workflow** 测一轮  
3. 出现 Issue：`[controller-bot] poll log`  
4. 需要代合：保持 `CONTROLLER_AUTO_MERGE=true`（或 Variable 显式 true）  
