# Kimi Agent 日常运维短表

```
STATUS: BINDING runbook
SCOPE: Pico production only
SECRETS: never print, copy to GitHub, or commit
UPDATED: 2026-08-05 (#290 residual R9)
```

1. **先核版本。** 执行 `bash scripts/remote-health.sh`；`git_sha` 必须等于拟验证的
   40 位 main SHA。再从生产 loopback health 核 `kimi_agent_scope`、
   `kimi_agent_runtime_enabled`、`kimi_agent_canary_configured`、
   `kimi_agent_canary_membership_count`、`kimi_agent_canary_batch` 与
   `legacy_agent_loop_emergency` / **`legacy_agent_loop_emergency_effect`**。
   公网 `/health` 只返回 OK 时不能据此猜内部字段。
2. **登录限流先止损。** 登录或 chat 出现 429 时停止并发/自动重试，保留状态码、时间窗和
   脱敏请求类别；按 health 的 `rate_limit` 摘要检查 RPM、并发上限及联合键作用域。不要
   临时放宽租户键、关闭限流或使用 `PROXY=1` 绕过。API 429 应带人话
   `user_message`（非裸栈）。
3. **测试凭据只做私下轮换。** 由获授权人员在密钥存储或生产配置面轮换测试账号密码/
   token；Issue 只记录轮换完成时间与验证结果。禁止在 shell trace、截图、日志、命令行
   参数或 GitHub 评论中出现原值；旧值撤销后再运行错密拒绝与正常登录各一次。
4. **按字段判路由。** `scope=all` 表示 runtime 开且有意空 canary（或显式 `*`）；
   `scope=canary` 表示仅合法 school+membership 联合键命中；`scope=off` 表示 runtime 关。
   **`legacy_agent_loop_emergency_effect` 恒为 `noop`（KA-4 HARD）：** env 即使为 true
   **也不会**恢复 `run_agent_loop`；多步仅 Kimi Agent 或 fail-closed。回滚 = **redeploy 旧 tip**。
5. **异常时安全回退并回写。** 运行时 P0 **只能** `PICO_DEPLOY_SHA=<old> bash scripts/prod-update.sh`
   redeploy 上一 tip；**禁止**把 emergency 当作回 loop 开关。recreate `pico-api` 后再核
   exact SHA/scope；15 分钟内在阶段 Issue 写 `## BLOCKED`。未获配置变更授权时只收集脱敏事实。

默认路径约束由 `tests/unit/test_kimi_runtime.py` / `test_ka4_soft.py` 断言：runtime 开且
有意空 canary 时走 Kimi Agent；RUNTIME=0 / 未 allowlist / emergency 旗 → **fail-closed no-op**，
**不**进 loop。不代表全球 product PASS。
