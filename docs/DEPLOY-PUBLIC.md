# 公网可见部署（绕开 Grok Live Preview 6014）

```
DOC: docs/DEPLOY-PUBLIC.md
STATUS: OPERATIONAL GUIDE
DATE: 2026-07-30
WHY: 业主浏览器打不开沙箱 8080，只能走坏掉的 hds-…-6014-…；须另给 HTTPS 入口
OWNER_DOMAIN: aivia.asia（阿里云 · DNS=hichina）
OWNER_VPS: 轻量应用服务器 华东2 · 公网 139.196.147.40 · 宝塔面板 · 2C2G
```

## 问题

- Agent 测 `127.0.0.1:8080` 正常 ≠ 用户能打开。
- Live Preview（6014）403/拒绝连接时，用户等于「没网页」。
- **解决「你看得见」= 公网 HTTPS 入口**，不是再改壳。
- **域名 alone 不够**：须解析到 VPS；**VPS alone 不够**：须跑产品 + 反代 + SSL。

---

## 业主资产（已确认）

| 项 | 值 |
|----|-----|
| 域名 | `aivia.asia` |
| 推荐产品主机名 | **`pico.aivia.asia`** |
| 服务器 | 宝塔 Linux 轻量 · 华东2（上海） |
| 公网 IP | **`139.196.147.40`** |
| 内网 IP | `172.24.28.181` |
| 规格 | 2 核 / 2G / 40G · 至 2027-02 |
| 探测（agent） | **:80 / :443 OPEN**；:22 从本沙箱不可达（部署请在宝塔命令助手执行） |

---

## 你现在要做的 3 步（正式上线）

### ① DNS（阿里云 · 域名解析）

| 主机记录 | 类型 | 记录值 | TTL |
|----------|------|--------|-----|
| **`pico`** | **A** | **`139.196.147.40`** | 10 分钟 |

完成后：`ping pico.aivia.asia` 应指向 `139.196.147.40`。

### ② 服务器一键装栈（宝塔 → 命令助手 → 粘贴执行）

```bash
# 若还没有 git：
# yum install -y git || apt-get install -y git

git clone --branch main --single-branch https://github.com/juanwan99/pico.git /opt/pico
cd /opt/pico
bash scripts/vps-bootstrap-aivia.sh
```

脚本会：加 2G swap、装 Docker、拉代码、compose build/up。  
产品只监听 **`127.0.0.1:8080`**（不裸奔公网 8080）。

可选：编辑 `/opt/pico/.env` 填入 `KIMI_API_KEY=…` 后：

```bash
cd /opt/pico && docker compose -f docker-compose.product.yml up -d
```

### ③ 宝塔网站 + SSL

1. **网站 → 添加站点**：域名填 `pico.aivia.asia`（可不创建数据库）
2. **反向代理** → 目标 URL：`http://127.0.0.1:8080`  
   - 开启「发送域名」/ WebSocket 支持（若有开关）
3. **SSL** → Let’s Encrypt 申请 → **强制 HTTPS**
4. 浏览器打开：**https://pico.aivia.asia**  
   - 应见「欢迎回来」  
   - 生产默认关闭开放注册；账号由管理员创建。临时演示播种必须显式
     `PICO_DEMO_SEED=1` 并使用 12 位以上随机密码，演示后立即关闭。

LibreChat 环境（compose 已默认）：

```text
DOMAIN_CLIENT=https://pico.aivia.asia
DOMAIN_SERVER=https://pico.aivia.asia
```

---

## 2G 内存注意

- compose 已限制 Mongo cache（`wiredTigerCacheSizeGB=0.25`）与容器 mem_limit  
- LibreChat 镜像构建默认堆改为 **1536MB**（Dockerfile build-arg）  
- 脚本会创建 **2G swap**；构建仍可能要 **10–20 分钟**  
- 若 OOM：先 `docker system prune -f`，确认 swap 已开，再 `compose build`

---

## 路径 A — Cloudflare 具名隧道（备选）

仅当不用本 VPS 反代时；需 Tunnel Token + CNAME 到 `*.cfargotunnel.com`。本页优先 **路径 B（本机 139.196…）**。

## 路径 B — Docker Compose（本仓库）

```bash
cd /opt/pico
export DOMAIN_CLIENT=https://pico.aivia.asia
export DOMAIN_SERVER=https://pico.aivia.asia
docker compose -f docker-compose.product.yml up -d --build
```

- 对外：**宝塔 443 → 127.0.0.1:8080**  
- Pico API：**不**映射公网，仅 compose 内网 `pico-api:18765`

## 路径 C — 合 main 后机房形态

见 `docs/archive/DEPLOY-AND-PRICING.md`；商业定价未 FIXED。

---

## 验收

- [ ] `pico.aivia.asia` 解析到 `139.196.147.40`
- [ ] `https://pico.aivia.asia` 打开中文登录（非 Mongo 英文句、非 6014 白屏）
- [ ] 登录后见任务台；可发消息（需 Kimi key）
- [ ] 公网扫端口：**不应**直接暴露 18765 / Mongo

## 与 Live Preview

| 入口 | 用途 |
|------|------|
| **https://pico.aivia.asia** | **业主正式观看** |
| Grok Live Preview 6014 | 辅助；挂了不挡交付 |
| 127.0.0.1:8080 | 仅本机/沙箱 agent |


## Kimi 真钥（生产）

密钥**永不进 Git**。在 **VPS** 上：

```bash
export KIMI_API_KEY='sk-...'   # 只在服务器环境变量里
cd /opt/pico
git fetch origin main
export PICO_DEPLOY_SHA="$(git rev-parse origin/main)"
bash scripts/prod-update.sh
bash scripts/vps-apply-kimi-key.sh
```

脚本会写入 `/opt/pico/.env`（不打印 key）、重启 `docker-compose.host.yml`、跑本地 S1 冒烟。

聊天里贴过的 key 视为已泄露，稳定后建议在 Moonshot 控制台**轮换**。

## 历史调查（非真源）

现行部署以本页正式步骤 + 生产机状态 + `docs/STATE-NOW.md` 为准。
Codex 早期 VPS 调查仅作历史：`docs/archive/CODEX-VPS-INVESTIGATION.md`（**HISTORICAL ONLY**）。
