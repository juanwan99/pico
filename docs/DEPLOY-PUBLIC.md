# 公网可见部署（绕开 Grok Live Preview 6014）

```
DOC: docs/DEPLOY-PUBLIC.md
STATUS: OPERATIONAL GUIDE
DATE: 2026-07-30
WHY: 业主浏览器打不开沙箱 8080，只能走坏掉的 hds-…-6014-…；须另给 HTTPS 入口
```

## 问题

- Agent 测 `127.0.0.1:8080` 正常 ≠ 用户能打开。
- Live Preview（6014）403/拒绝连接时，用户等于「没网页」。
- **解决「你看得见」= 公网 HTTPS 入口**，不是再改壳。

## 路径 A — 当前沙箱临时公网（最快）

用 Cloudflare **Quick Tunnel** 把本机 8080 映到 `*.trycloudflare.com`：

```bash
# 产品已在 8080
bash scripts/publish-tunnel.sh
# 输出一行 https://….trycloudflare.com
```

然后：

1. LibreChat `DOMAIN_CLIENT` / `DOMAIN_SERVER` 设为该 HTTPS 源站（脚本会写提示）。
2. **重启** LibreChat backend。
3. 浏览器打开隧道 URL → 登录 `teacher@example.com` / `pico-demo-123`。

限制：

- 无账号 quick tunnel **无 SLA**，URL 每次重启会变。
- 沙箱休眠则隧道断；需再跑脚本。
- **勿**把含真实密钥的长期演示完全依赖 quick tunnel。

## 路径 B — 正式部署（推荐中期）

多服务：Mongo + LibreChat(Node) + Pico API(Python)。适合 **VPS / Railway / Fly / Render**（Docker Compose），不适合单静态 Vercel。

见 `docker-compose.product.yml`（仓库根）：

```bash
# 在有 Docker 的机器上
cp .env.example .env   # 填 KIMI_API_KEY 等
# 编辑 DOMAIN_CLIENT/DOMAIN_SERVER 为你的 https 域名
docker compose -f docker-compose.product.yml up -d --build
```

对外只暴露 **80/443 → LibreChat**；Pico API 仅容器网访问。

## 路径 C — 合 main 后业主机房

按 `docs/DEPLOY-AND-PRICING.md` 形态选共享/专有；本页不替代商业 FIXED。

## 验收（用户侧）

- [ ] 浏览器打开 **HTTPS 公网 URL**（非 hds-6014）
- [ ] 见中文登录「欢迎回来」
- [ ] 演示账号能进任务台并发消息
- [ ] 不出现 Mongo over HTTP 句

## 与 Live Preview

| 入口 | 用途 |
|------|------|
| 公网隧道/部署 URL | **业主看见产品** |
| Grok Live Preview 6014 | 辅助；挂了不挡交付 |
| 127.0.0.1:8080 | 仅沙箱内 agent |
