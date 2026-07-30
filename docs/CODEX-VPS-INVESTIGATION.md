# Codex VPS 调查结果整理（后续任务真源）

```
DOC: docs/CODEX-VPS-INVESTIGATION.md
STATUS: HANDOFF SNAPSHOT（非 PASS · VERDICT_AUTHORITY NONE）
DATE: 2026-07-30
AUTHORS: Codex 部署窗 + Grok 整理窗
REPO: juanwan99/pico ONLY
BRANCH: grok/pico-preview-librechat-p0
PLAN: MVP-3DAY v1.2 FIXED（无授权不升 v1.3）
```

> **用法：** 后续任何窗（Grok / Codex / 人）改生产或验收前先读本页。  
> 与旧 HANDOFF / 沙箱叙事冲突时：**以本页「生产机已证实」+ `DEPLOY-PUBLIC.md` 为准**。  
> **禁止：** 无明确升级需求时重新 clone 全量构建、推倒重来、因 Live Preview 白屏换壳。

---

## 0. 一句话现状

| 面 | 结论 |
|----|------|
| **业主看产品** | **https://pico.aivia.asia/login**（必须 HTTPS） |
| **部署** | Codex 已在阿里云轻量（宝塔）跑通 v1.3 形态栈 |
| **代码 tip（仓）** | `c47c3be`（含 host compose / Kimi apply 脚本回灌） |
| **服务器曾报 SHA** | `/opt/pico` 曾钉在 `07e2e79…`；应用 key / pull 后应以服务器 `git rev-parse` 为准 |
| **S1 真钥** | 须在服务器 `/opt/pico/.env` 的 `KIMI_API_KEY`；**永不进 Git**；聊天里出现过 key 则视为泄露，应轮换 |
| **Grok 沙箱** | 常被重置；**不能** SSH `139.196.147.40:22`；**不能**用沙箱 HTTPS 成败否定国内 ECS 验收 |

---

## 1. 资产清单（已确认）

### 1.1 域名与 DNS

| 项 | 值 | 证据来源 |
|----|-----|----------|
| 根域 | `aivia.asia` | 业主阿里云控制台 |
| 产品主机名 | **`pico.aivia.asia`** | 业主拍板 / 部署目标 |
| A 记录 | `pico` → **`139.196.147.40`** | Codex + Grok DoH（1.1.1.1） |
| NS | 阿里云 hichina（`dns1/dns2.hichina.com`） | 业主域名面板 |
| ACME | 曾用 **DNS-01**：`_acme-challenge.pico` TXT | Codex（签发 LE 时临时） |
| 证书 | Let’s Encrypt · 域名 `pico.aivia.asia` · **到期约 2026-10-28** | Codex |
| 续期 | **手工 DNS-01，未做自动续期** | Codex 明确缺口 |

### 1.2 服务器

| 项 | 值 |
|----|-----|
| 产品 | 阿里云 **轻量应用服务器** |
| 地域 | 华东2（上海） |
| 面板 | 宝塔 Linux |
| 公网 IP | **139.196.147.40** |
| 内网 IP | 172.24.28.181 |
| 规格 | 2 核 / 2 GiB / 40 GiB 系统盘 |
| 到期 | 约 2027-02-08（业主面板） |
| 路径 | **`/opt/pico`** |

### 1.3 仓库与分支

| 项 | 值 |
|----|-----|
| 仓 | https://github.com/juanwan99/pico （private） |
| 分支 | `grok/pico-preview-librechat-p0` → main |
| PR | https://github.com/juanwan99/pico/pull/30 （CANDIDATE · 不自 PASS · 不无人合） |
| 产品壳 | **`apps/librechat`**（禁 web/nextchat/workbench 回潮） |
| 产品定义 | AI 工作台底座：对话 + Agent + 产物 + **唯一 AI 账本** + 模型 HTTPS API |

---

## 2. Codex 已完成事项（按系统）

### 2.1 运行拓扑（生产 · host network）

```text
浏览器
  → https://pico.aivia.asia:443
      Nginx (/etc/nginx/conf.d/pico.aivia.asia.conf)
        → proxy_pass http://127.0.0.1:8080
            LibreChat (container, host net)
              ├─ Mongo  127.0.0.1:27017  (会话呈现，非 AI 业务真源)
              └─ OPENAI_REVERSE_PROXY → http://127.0.0.1:18765/v1
                    Pico API (Kimi / pico-agent / 账本 SQLite)
```

| 进程/端口 | 绑定 | 公网 |
|-----------|------|------|
| Nginx 80/443 | 0.0.0.0 | **是**（唯一入口） |
| LibreChat | **127.0.0.1:8080** | 否 |
| Pico API | **127.0.0.1:18765** | 否 |
| MongoDB | **127.0.0.1:27017** | 否 |

**为何 host network：** 该机 Docker **bridge 网络异常**；Codex 改用  
`/opt/pico/docker-compose.host.yml`（仓内已回灌同名文件）。

### 2.2 镜像与构建（服务器本地）

| 镜像 | 说明 |
|------|------|
| `pico-librechat:v13` | 本地构建；CN 适配 Dockerfile |
| `pico-api:v13` | 本地构建 |

| 文件（服务器 / 仓） | 作用 |
|---------------------|------|
| `apps/librechat/Dockerfile.pico-fast` | Alpine→阿里云镜像；避免 ghcr.io uv；`npm ci --legacy-peer-deps` |
| `Dockerfile.pico-api` | Python 3.12-slim + 阿里云 PyPI |
| `docker-compose.host.yml` | host 网络 + 127.0.0.1 绑定 |
| `librechat.yaml` | 最小自定义配置 `version: 1.3.13`；挂载 `:/app/librechat.yaml:ro` |

构建动机：2G 机 + 国内网络；默认上游 Dockerfile 易 OOM / 拉不动 ghcr。

### 2.3 LibreChat 环境（生产要点）

| 变量 | 值（概念） |
|------|------------|
| `MONGO_URI` | `mongodb://127.0.0.1:27017/LibreChat` |
| `OPENAI_REVERSE_PROXY` | `http://127.0.0.1:18765/v1` |
| `OPENAI_API_KEY` | `pico-dev`（**调 Pico 的代理钥**，不是 Kimi sk） |
| `DOMAIN_CLIENT` / `DOMAIN_SERVER` | `https://pico.aivia.asia` |
| `HOST`/`PORT` | 127.0.0.1 / 8080 |

日志曾确认：Custom config loaded · Connected to MongoDB · listening `http://127.0.0.1:8080` · readiness passing。

### 2.4 Nginx / TLS

| 项 | 内容 |
|----|------|
| 配置 | `/etc/nginx/conf.d/pico.aivia.asia.conf` |
| HTTP | `/.well-known/acme-challenge/` 保留；其余 **301 → HTTPS** |
| HTTPS | `ssl_certificate` / `privkey` under `/etc/letsencrypt/live/pico.aivia.asia/` |
| 反代 | `proxy_pass http://127.0.0.1:8080` |
| 校验 | `nginx -t` 通过并 reload |

### 2.5 Codex 验收（采信）

| 检查 | 结果 |
|------|------|
| 服务器本机 `https://pico.aivia.asia/login` | **HTTP/2 200** |
| 另一台 ECS 外网同 URL | **HTTP/2 200** |
| 页面 | `lang=zh-CN` · 简体默认 · zh-Hans 痕迹 |
| 公网 8080/18765/27017 | **不可达**（正确） |
| 监听 | 127.0.0.1:{8080,18765,27017} + 0.0.0.0:{80,443} |

### 2.6 容器名（Codex 报）

- `pico-mongo-1`
- `pico-pico-api-1`
- `pico-librechat-1`  

（均 Up；以服务器 `docker compose -f docker-compose.host.yml ps` 为准。）

---

## 3. Grok 窗交叉验证（有限）

| 探测（Grok 沙箱出口） | 结果 | 解读 |
|----------------------|------|------|
| DNS A `pico.aivia.asia` | `139.196.147.40` | 与部署一致 |
| TCP 80/443 | OPEN | Nginx 在听 |
| TCP 8080/18765/27017 | 超时/滤 | 符合「不裸奔」 |
| TCP 22 | **不通** | **Grok 无法代登 VPS** |
| `http://pico.aivia.asia` | 常 **403 Server: Beaver** | 阿里云拦截/备案相关；**应用 HTTPS** |
| `https://…` 自 Grok | 可能 TLS RST | **路径/区域问题；不以之否定 Codex 国内 200** |

**原则：** 生产是否健康，优先 **服务器本机 curl** 与 **中国境内浏览器/ECS**，不要用 Grok 沙箱 TLS 失败驱动重建。

---

## 4. 关键认知（必须保留）

### 4.1 产品 vs 预览

| 正确 | 错误 |
|------|------|
| 业主入口 = **https://pico.aivia.asia** | 业主应能开沙箱 8080 |
| Live Preview 6014 白/拒绝连接 = 平台隧道 | 白屏就换壳 / 重写前端 |
| Mongo over HTTP 英文句 = 误打 Mongo 口 | 当库坏了乱改 |
| `OPENAI_API_KEY=pico-dev` = LibreChat→Pico 代理 | 把它当成 Kimi sk |
| `KIMI_API_KEY` 只在服务器 `.env` | 写进 Git / 聊天常驻 |

### 4.2 鉴权陷阱（代码行为）

`services/api/app/openai_compat.py`：

- `PICO_ENV=production` 时 **拒绝** `pico-dev` 等 proxy key → LibreChat 聊天 **401**。
- 演示 VPS 须保持 **`PICO_ENV=development`**（或未来改 JWT 贯通后再 production）。
- 仓内 `docker-compose.host.yml` / `scripts/vps-apply-kimi-key.sh` 已按此钉死。

### 4.3 双存储边界

| 存储 | 内容 | 是否 AI 业务真源 |
|------|------|------------------|
| Pico SQLite（API data） | Task/Run/Event/Artifact… | **是（唯一）** |
| LibreChat Mongo | 会话气泡、用户、UI | 会话呈现 only |

### 4.4 硬边界（永久）

- 只写 `juanwan99/pico`；禁止 edu-cloud。
- 不自 PASS；CANDIDATE → CI → 审 → **值守**合 main。
- 禁止 `PROXY=1`（LibreChat undici）。
- 禁止公网暴露 8080 / 18765 / 27017。
- 密钥不进聊天记录与截图（已泄露则轮换）。

### 4.5 沙箱 vs 生产端口叙事

| 环境 | Mongo | 产品 UI | API |
|------|--------|---------|-----|
| Grok 沙箱（历史） | 真库 **27117**；27017 HTTP 盾 | mirror **8080** | 127.0.0.1:**18765** |
| 阿里云 VPS（Codex） | host **27017** 仅本机 | 本机 **8080** ← Nginx | 本机 **18765** |

两套都对；**不要**把沙箱 27117 方案硬套到已 host 部署的 VPS，除非重做网络。

---

## 5. 仓库内相关文件地图

| 路径 | 用途 |
|------|------|
| `docs/DEPLOY-PUBLIC.md` | 公网部署操作指南 + 域名/DNS |
| `docs/CODEX-VPS-INVESTIGATION.md` | **本页** · 调查结果真源 |
| `docs/PREVIEW-WHITE-SCREEN.md` | Live Preview 白屏（6014）· 与生产域名无关 |
| `docs/CORRECTED-GOALS.md` | 产品目标校正 |
| `docs/DEMO.md` | 演示路径；含生产 URL 提示 |
| `docs/CALIBRATION-NOW.md` | 主线校准 |
| `docker-compose.host.yml` | **生产 compose（host）** |
| `docker-compose.product.yml` | 备选 bridge/bootstrap 向 |
| `Dockerfile.pico-api` | API 镜像 |
| `apps/librechat/Dockerfile.pico-fast` | LibreChat CN 构建 |
| `librechat.yaml` | 最小 LC 配置 |
| `scripts/vps-bootstrap-aivia.sh` | 轻量机首装（swap/docker/compose） |
| `scripts/vps-apply-kimi-key.sh` | **写 Kimi key + 重启 + S1 冒烟（不 echo key）** |
| `scripts/publish-tunnel.sh` | 沙箱临时 trycloudflare（非正式） |
| `startup.sh` / `scripts/run-product.sh` | **Grok 沙箱** revive，不是 VPS 主路径 |

---

## 6. 未完成 / 后续任务队列（按优先级）

### P0 — 业主可用真聊（S1）

| ID | 任务 | 状态 | 做法 |
|----|------|------|------|
| P0.1 | 浏览器打开 https://pico.aivia.asia/login | Codex：200；业主确认登录 | 演示号 `teacher@example.com` / `pico-demo-123`（可先注册） |
| P0.2 | `/opt/pico/.env` 存在非空 `KIMI_API_KEY` | **待服务器确认**（Grok 不能 SSH） | 宝塔执行 `vps-apply-kimi-key.sh` |
| P0.3 | 本机 S1 冒烟 `18765/v1/chat/completions` | 随 P0.2 | 脚本内置；期望非 error JSON |
| P0.4 | UI 发「只回：演示OK」有模型回复 | 待 P0.2–3 | 默认模型直连 Kimi，非必须 pico-agent |

### P1 — 运维硬化

| ID | 任务 | 状态 |
|----|------|------|
| P1.1 | LE **自动续期**（DNS-01 hook / 阿里云 API） | 未做；证书 ~2026-10-28 |
| P1.2 | 服务器 `git pull` 与仓 tip 对齐；避免只活在磁盘的补丁漂移 | 部分回灌已在 `c47c3be` |
| P1.3 | 备份：`pico_data` / mongo volume / `.env`（无密钥进 Git） | 未标准化 |
| P1.4 | 监控：磁盘 40G、2G 内存、容器 restart | 未做 |
| P1.5 | HTTP Beaver/ICP 文案：对外只宣传 HTTPS | 已知 |

### P2 — 产品与 Phase1 诚实项

| ID | 任务 | 备注 |
|----|------|------|
| P2.1 | S2 `pico-agent` 显式多步演示 | 默认 chat ≠ 多步 |
| P2.2 | S3 账本产物 hello.txt 路径在生产复验 | 见 REGRESSION / DEMO |
| P2.3 | S7 确认横幅生产点验 | W2-S7-NOTES |
| P2.4 | LibreChat→Pico **JWT** 后可 `PICO_ENV=production` | 现靠 pico-dev |
| P2.5 | PR #30 CI 修红 + 值守合 main | S8；不自 PASS |
| P2.6 | 密钥轮换（若曾在聊天出现） | 安全 |

### P3 — 明确不做（本阶段）

- 写 edu-cloud / 以联调 edu 为门禁  
- 拆 WorkBuddy / 换壳  
- 依赖 Grok Live Preview 作为交付  
- 把 trycloudflare 当正式域名  
- 商业定价写死（未 FIXED）

---

## 7. 标准操作速查（给下一窗）

### 7.1 只改 key / 重启 API（服务器）

```bash
cd /opt/pico
git pull --ff-only origin grok/pico-preview-librechat-p0   # 如需脚本
export KIMI_API_KEY='…'   # 勿回传聊天
bash scripts/vps-apply-kimi-key.sh
```

### 7.2 看健康（服务器）

```bash
docker compose -f /opt/pico/docker-compose.host.yml ps
curl -sS http://127.0.0.1:18765/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/login
curl -sS -o /dev/null -w '%{http_code}\n' https://pico.aivia.asia/login
```

### 7.3 看日志（服务器）

```bash
docker compose -f /opt/pico/docker-compose.host.yml logs --tail=100 pico-api
docker compose -f /opt/pico/docker-compose.host.yml logs --tail=100 librechat
tail -n 50 /var/log/nginx/error.log
```

### 7.4 禁止默认动作

```text
✗  rm -rf /opt/pico && 重新 bootstrap
✗  因 Grok curl HTTPS 失败而 rebuild 镜像
✗  PROXY=1
✗  发布 8080/18765/27017 到 0.0.0.0
✗  自 PASS / 无人合 main
```

---

## 8. 验收清单（复制用）

- [ ] `dig pico.aivia.asia` → 139.196.147.40  
- [ ] `https://pico.aivia.asia/login` → 200 · 欢迎回来  
- [ ] 登录演示账号 → 任务台  
- [ ] `KIMI_API_KEY` SET（仅服务器；不贴值）  
- [ ] 聊天「演示OK」有回复  
- [ ] 公网 nmap/探活：8080/18765/27017 关  
- [ ] 证书到期日已知；续期方案有主  
- [ ] 未把密钥写入 Git  

---

## 9. 修订记录

| 日期 | 内容 |
|------|------|
| 2026-07-30 | 首版：汇总 Codex VPS 部署调查 + Grok 交叉验证 + 后续队列 |

**下一窗默认入口：** 读本页 §6 P0 → 在 **VPS** 执行 §7.1 → 勾 §8。  
**不要**从空 Grok 沙箱重新发明生产拓扑。
