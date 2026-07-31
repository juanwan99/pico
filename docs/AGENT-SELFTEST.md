# Agent 自测能力说明（效率）

```
DOC: docs/AGENT-SELFTEST.md
```

## 我能测什么 / 不能测什么

| 目标 | Agent 能否测 | 说明 |
|------|--------------|------|
| 本沙箱 8080 UI / 18765 API | **能** | `bash scripts/agent-selftest.sh` |
| Playwright 登录截图 | **能** | 沙箱 Chromium |
| Kimi S1 真聊（本地 .env） | **能** | key 仅本地 `.env`，不进 Git |
| 生产 https://pico.aivia.asia | **多数不能** | 沙箱出口 TLS 常 RST / Beaver |
| 生产 SSH / 宝塔 | **不能** | 22 不通 |
| 业主浏览器观感 | 需业主 1 句确认 | 公网最终验收 |

## 高效协作约定

1. **默认：** Agent 在沙箱起栈 → selftest → 改代码 → push 分支。  
2. **仅当必须动 VPS：** 给业主 **一条** 宝塔命令（pull + compose），不再来回猜。  
3. **禁止** 用「请你打开域名告诉我」代替 Agent 本可做的本地测试。  
4. 生产闭环证据：业主一句「能登录/能回」即可；细节用 selftest 本地复现。

## 命令

```bash
# 栈已启动时
bash scripts/agent-selftest.sh
# 期望 SELFTEST_OK
```

脚本启动时先检查 `/health` 的 readiness 摘要：

- `edu_mode` 只能是 `fake` 或 `live`；
- `rate_limit.scope` 固定为 `membership_or_ip`；
- `rate_limit.rpm` 与 `rate_limit.max_concurrent` 必须是正整数。

这些字段只公开运行模式和限流数值，不包含 token、key、issuer secret
或上游服务凭据。部署核验仍以 `health.git_sha` 与已合 main 的完整 SHA
一致为准。

## 责任边界（HARD）

| 角色 | 负责 |
|------|------|
| **Agent（本窗）** | 写代码、本地起栈、selftest、单测、ruff、push 分支 |
| **业主** | 仅公网最终一眼；或 VPS 执行 **一行** 热更新 |
| **Codex（有 SSH 时）** | 生产 `prod-update` / 浏览器公网验收 |

**禁止**把「请你打开页面测一下」当作默认验收。Agent 本地 `SELFTEST_OK` 是开发门禁。
