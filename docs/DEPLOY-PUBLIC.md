# 公网可见部署（绕开 Grok Live Preview 6014）

```
DOC: docs/DEPLOY-PUBLIC.md
STATUS: OPERATIONAL GUIDE
DATE: 2026-07-30
WHY: 业主浏览器打不开沙箱 8080，只能走坏掉的 hds-…-6014-…；须另给 HTTPS 入口
OWNER_DOMAIN: aivia.asia（阿里云注册 · DNS=hichina）
```

## 问题

- Agent 测 `127.0.0.1:8080` 正常 ≠ 用户能打开。
- Live Preview（6014）403/拒绝连接时，用户等于「没网页」。
- **解决「你看得见」= 公网 HTTPS 入口**，不是再改壳。
- **域名 alone 不够**：`aivia.asia` 必须解析到「有产品在跑的公网入口」（ECS IP 或 Cloudflare Tunnel）。

## 业主域名（aivia.asia）

| 建议 | 说明 |
|------|------|
| **产品主机名** | `pico.aivia.asia`（推荐；别一上来改根域 `aivia.asia`，避免动邮箱/备案主站） |
| **可选根域** | `aivia.asia` / `www.aivia.asia` 仅当根域只给 Pico 用时 |
| **DNS 面板** | 阿里云控制台 → 域名与网站 → **域名解析**（当前 NS：`dns1.hichina.com` / `dns2.hichina.com`） |
| **LibreChat** | `DOMAIN_CLIENT` = `DOMAIN_SERVER` = `https://pico.aivia.asia` |

### 在阿里云「域名解析」添加记录（路径 B：自有 ECS）

假设 ECS 公网 IP = `x.x.x.x`，产品监听 80/443（或 8080 经 Nginx 反代）：

| 主机记录 | 记录类型 | 记录值 | 说明 |
|----------|----------|--------|------|
| `pico` | **A** | `x.x.x.x` | → `pico.aivia.asia` |
| `www` | CNAME 或 A | 可选 | 需要时再加 |

然后：

1. ECS 上 `docker compose -f docker-compose.product.yml up -d --build`（或本仓 run-product 等价栈）
2. Nginx/Caddy 终止 HTTPS（阿里云免费 SSL 或 Let’s Encrypt）
3. 反代到 LibreChat `:3080`（或 compose 映射的 8080）
4. 环境变量：
   ```bash
   DOMAIN_CLIENT=https://pico.aivia.asia
   DOMAIN_SERVER=https://pico.aivia.asia
   ```
5. 浏览器打开 `https://pico.aivia.asia` → 登录演示账号

### 路径 A′ — Cloudflare **具名隧道**（把沙箱/小机器绑到域名）

Quick Tunnel（`*.trycloudflare.com`）**不能**直接当阿里云 CNAME 目标。  
要用自定义域名，需要 Cloudflare 账号 + **Named Tunnel**：

1. Cloudflare 添加站点 `aivia.asia`（或仅用 Tunnel 的 DNS 指引）
2. `cloudflared tunnel create pico`
3. 路由：`cloudflared tunnel route dns pico pico.aivia.asia`  
   → 会在 CF 侧生成 CNAME → `xxxxx.cfargotunnel.com`
4. 若 DNS 仍在阿里云 hichina：在阿里云解析里加  
   | 主机记录 | 类型 | 记录值 |
   |----------|------|--------|
   | `pico` | **CNAME** | `xxxxx.cfargotunnel.com`（CF 控制台给出的隧道域名） |
5. 本机：`cloudflared tunnel run --url http://127.0.0.1:8080 pico`
6. LibreChat DOMAIN 改为 `https://pico.aivia.asia` 并重启

**本 Grok 沙箱**没有 Cloudflare 登录态 / Tunnel Token 时，无法替你完成具名隧道；需要你提供 **Tunnel Token** 或改在 **有公网 IP 的 ECS** 上部署。

## 路径 A — 当前沙箱临时公网（最快 · 现在就能看）

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
- **不能**把 `pico.aivia.asia` CNAME 到 `*.trycloudflare.com`（官方不支持长期自定义域）。

## 路径 B — 正式部署（推荐 · 配 aivia.asia）

多服务：Mongo + LibreChat(Node) + Pico API(Python)。适合 **阿里云 ECS / 轻量应用服务器**（Docker Compose），不适合单静态 Vercel。

见 `docker-compose.product.yml`（仓库根）：

```bash
# 在有 Docker 的机器上
cp .env.example .env   # 填 KIMI_API_KEY 等
# 编辑 DOMAIN_CLIENT/DOMAIN_SERVER 为 https://pico.aivia.asia
docker compose -f docker-compose.product.yml up -d --build
```

对外只暴露 **80/443 → LibreChat**；Pico API 仅容器网访问。

## 路径 C — 合 main 后业主机房

按 `docs/DEPLOY-AND-PRICING.md` 形态选共享/专有；本页不替代商业 FIXED。

## 验收（用户侧）

- [ ] 浏览器打开 **HTTPS 公网 URL**（`pico.aivia.asia` 或 trycloudflare；**非** hds-6014）
- [ ] 见中文登录「欢迎回来」
- [ ] 演示账号能进任务台并发消息
- [ ] 不出现 Mongo over HTTP 句

## 与 Live Preview

| 入口 | 用途 |
|------|------|
| **pico.aivia.asia** / 隧道 URL | **业主看见产品** |
| Grok Live Preview 6014 | 辅助；挂了不挡交付 |
| 127.0.0.1:8080 | 仅沙箱内 agent |
