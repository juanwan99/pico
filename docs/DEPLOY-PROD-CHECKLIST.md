# Pico 生产部署核对清单

生产配置以 `.env.production.example` 为模板；真实密钥只保存在服务器，
不得写入 Git、日志或 PR 评论。

## 部署前

- [ ] `PICO_ENV=production`
- [ ] `PICO_JWT_SECRET` 为独立随机值（至少 32 字符），不是开发默认值
- [ ] `PICO_ACCEPT_TEST_ISSUER=false`
- [ ] `PICO_ALLOW_TEST_ISSUER_BREAK_GLASS=false`
- [ ] `PICO_OPENAI_PROXY_KEY` 为 LibreChat→Pico 内网专用随机值（至少 32 字符）
- [ ] 配置 `DEEPSEEK_API_KEY`（推荐）或 `KIMI_API_KEY`
- [ ] `PICO_MODEL_PROVIDER=deepseek`（产品默认脑）
- [ ] `PICO_ALLOWED_MODELS` **首项**为可用 DeepSeek（推荐 `deepseek-chat,pico-agent`）；**禁止**把坏的 `kimi-k2.x` 放第一位作默认
- [ ] `PICO_CHAT_RPM`、`PICO_CHAT_MAX_CONCURRENT`、`PICO_RUN_MAX_TOKENS` 为正数
- [ ] `ALLOW_REGISTRATION=false`、`ALLOW_UNVERIFIED_EMAIL_LOGIN=false`
- [ ] `PICO_DEMO_SEED=0`
- [ ] LibreChat 的 `CREDS_KEY`、`CREDS_IV`、`JWT_SECRET`、
      `JWT_REFRESH_SECRET` 均为相互独立的随机值
- [ ] Pico API、Mongo 仅监听内网或 loopback；公网只开放 HTTPS

## 部署后

- [ ] `/health` 返回 `ok=true` 且 `git_sha` 等于已合入 main 的 SHA
- [ ] 默认 `pico-dev` Bearer 被拒绝
- [ ] 未在 `PICO_ALLOWED_MODELS` 中的 model 返回 4xx
- [ ] 超过 RPM/并发上限返回 429
- [ ] 开放注册关闭；未显式开启时不会播种固定密码账号
- [ ] GitHub PR 回写 `## DEPLOYED`（SHA、健康检查、清单结果；不得含密钥）

任何一项无法满足：停止部署，并在 PR 评论写 `## BLOCKED` 和原因。
