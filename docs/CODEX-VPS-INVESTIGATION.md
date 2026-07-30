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
| **业主入口** | **https://pico.aivia.asia/login**（必须 HTTPS） |
| **部署** | Codex 已在阿里云轻量（宝塔）跑通 v1.3 形态栈 |
| **S1 本机冒烟（2026-07-30 业主回报）** | `health.ok` · **HTTP 200** · reply **「演示OK」** · `S1_SMOKE=PASS_LIKELY` |
| **解读** | **Kimi 上游 + Pico API 代理链在 VPS 本机已通**（非自 PASS 全产品） |
| **代码 tip（仓）** | 以 `git log` 为准（本页修订时 tip 在 144bd8b 一带） |
| **服务器 SHA** | 以 `/opt/pico` `git rev-parse` 为准 |
| **Grok 沙箱** | 常被重置；**不能** SSH `139.196.147.40:22`；**不能**用沙箱 HTTPS 成败否定国内验收 |

---

## 0.1 最新生产证据（业主粘贴 · 2026-07-30）

```text
health: {"ok":true,"service":"pico-api","phase":"3-integrate","git_sha":"unknown"}
S1 http=200
reply_snippet: 演示OK
S1_SMOKE=PASS_LIKELY
```

| 推论 | 说明 |
|------|------|
| Pico API 进程健康 | `ok:true` |
| `KIMI_API_KEY` 已生效 | 无「missing KIMI」类错误且模型回了「演示OK」 |
| LibreChat→API 代理钥路径可用 | 冒烟用 `Bearer pico-dev`（`PICO_ENV` 须非 production） |
| `git_sha: unknown` | 镜像/运行环境未注入 BUILD_COMMIT；**不阻塞** S1 |
| 仍非全量 PASS | 未代替浏览器任务台 / S2–S8 / CI / 合 main |

**下一步默认：** 浏览器 UI 登录 + 发同一句；不要重装栈。

---

## 1. 资产清单（已确认）

### 1.1 域名与 DNS

| 项 | 值 | 证据来源 |
|----|-----|----------|
| 根域 | `aivia.asia` | 业主阿里云控制台 |
| 产品主机名 | **`pico.aivia.asia`** | 业主拍板 / 部署目标 |
| A 记录 | `pico` → **`139.196.147.40`** | Codex + Grok DoH |
| 证书 | Let’s Encrypt · 约 **2026-10-28** | Codex |
| 续期 | **手工 DNS-01，未自动续期** | Codex 缺口 |

### 1.2 服务器

| 项 | 值 |
|----|-----|
| 产品 | 阿里云轻量 · 华东2 · 宝塔 |
| 公网 IP | **139.196.147.40** |
| 规格 | 2C / 2G / 40G |
| 路径 | **`/opt/pico`** |

### 1.3 仓库

| 项 | 值 |
|----|-----|
| 仓 | juanwan99/pico |
| 分支 | `grok/pico-preview-librechat-p0` |
| PR | #30 CANDIDATE |
| 壳 | `apps/librechat` |

---

## 2. 运行拓扑（生产 · host network）

```text
浏览器 → https://pico.aivia.asia:443
  Nginx → 127.0.0.1:8080 LibreChat
            ├─ Mongo 127.0.0.1:27017
            └─ OPENAI_REVERSE_PROXY → 127.0.0.1:18765 Pico API → Kimi HTTPS
```

| 端口 | 绑定 | 公网 |
|------|------|------|
| 80/443 | 0.0.0.0 Nginx | 是 |
| 8080 / 18765 / 27017 | 127.0.0.1 | 否 |

Compose：`docker-compose.host.yml`。镜像：`pico-librechat:v13` / `pico-api:v13`。

---

## 3. 关键陷阱（摘要）

- `pico-dev` ≠ Kimi sk；Kimi 只在 `/opt/pico/.env`
- **`PICO_ENV=production` → proxy 401**；演示保持 `development`
- HTTP 常 Beaver 403 → 只用 HTTPS
- 勿因 Grok TLS RST 重建
- 不自 PASS / 不无人合 main / 不写 edu / 不换壳 / 禁 `PROXY=1`

---

## 4. 后续任务队列


### P0.4 登录失败（2026-07-30）

现象：UI「登录失败，请检查邮箱和密码后再试」。

常见原因（生产空库 / 新 Mongo）：
1. **演示用户从未注册**（文档账号 ≠ 自动入库）
2. 注册后 `emailVerified=false` 且未开 `ALLOW_UNVERIFIED_EMAIL_LOGIN`
3. 密码不一致

修复（服务器）：
```bash
cd /opt/pico && git pull --ff-only origin grok/pico-preview-librechat-p0
bash scripts/vps-seed-demo-user.sh
```
期望输出：`DEMO_LOGIN=OK`。然后再打开 https://pico.aivia.asia/login。

### P0 — 真聊闭环

| ID | 任务 | 状态 |
|----|------|------|
| P0.1 | HTTPS 登录页 200 | Codex 已证；业主 UI 再点一次 |
| P0.2 | `KIMI_API_KEY` 生效 | **已证（S1 200 + 演示OK）** |
| P0.3 | 本机 S1 冒烟 | **PASS_LIKELY（业主 2026-07-30）** |
| P0.4 | **浏览器**登录任务台并发「只回：演示OK」 | **待业主/下一窗** |
| P0.5 | （可选）产物 hello.txt / 结果区 | 跟 DEMO 主路径 |

### P1 — 运维

| ID | 任务 | 状态 |
|----|------|------|
| P1.1 | LE 自动续期 | 未做 |
| P1.2 | 服务器 git 与 tip 对齐；注入 git_sha | `git_sha: unknown` 可修 |
| P1.3 | 备份 data/mongo/.env 策略 | 未做 |
| P1.4 | 密钥轮换（若曾进聊天） | 建议做 |

### P2 — 产品诚实项

| ID | 任务 |
|----|------|
| P2.1 | S2 pico-agent 显式多步 |
| P2.2 | S3 账本产物生产复验 |
| P2.3 | S7 确认横幅 |
| P2.4 | JWT 后 production |
| P2.5 | PR #30 CI + 值守合 |

### P3 — 不做

edu 门禁、换壳、依赖 Grok Preview、trycloudflare 当正式域名。

---

## 5. 标准操作速查

```bash
# 健康
curl -sS http://127.0.0.1:18765/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/login
curl -sS -o /dev/null -w '%{http_code}\n' https://pico.aivia.asia/login

# 日志
docker compose -f /opt/pico/docker-compose.host.yml logs --tail=80 pico-api
```

**禁止：** 因 S1 已通仍 `rm -rf /opt/pico` 重装。

---

## 6. 验收清单

- [x] DNS → 139.196.147.40（历史）
- [x] API health ok（2026-07-30）
- [x] S1 本机 200 + 演示OK（2026-07-30）
- [x] 浏览器 https 登录（2026-07-30 业主）
- [x] 任务台 UI 真聊能回复（2026-07-30 业主）
- [ ] 公网仅 443 暴露（历史已查，可抽查）
- [ ] 证书续期方案
- [ ] 未把密钥写入 Git
- [ ] **未**自 PASS / 未合 main

---

## 7. 修订记录

| 日期 | 内容 |
|------|------|
| 2026-07-30 | 首版：Codex 部署调查汇总 |
| 2026-07-30 | **S1 业主证据：health ok + 200 + 演示OK**；P0.2/0.3 勾完；下一默认 P0.4 UI |

### 登录修复（2026-07-30 续）

生产空 Mongo / 未验证邮箱 → UI「登录失败」。

**服务器一键（推荐）：**
```bash
cd /opt/pico && bash scripts/vps-fix-login.sh
```
期望 `DEMO_LOGIN=OK`。然后浏览器：
`teacher@example.com` / `pico-demo-123`

机制：
- `PICO_SEED_DEMO_USER` 启动播种（compose 挂载 seed 源码，免全量 rebuild）
- 脚本兜底：register API + mongosh emailVerified + create-user

### P0.4 登录（2026-07-30 业主确认）

**已可登录** https://pico.aivia.asia/login  
演示号 `teacher@example.com` / `pico-demo-123`（seed/fix-login 路径）。

下一默认：浏览器任务台发「只回：演示OK」闭合 UI 真聊（S1 本机此前已 200）。

### P0.4 UI 真聊（2026-07-30 业主确认）

浏览器任务台 **能回复**（与 S1 本机 200 /「演示OK」一致）。

**生产演示主路径闭环（诚实）：** HTTPS 入口 + 登录 + Kimi 真聊。  
仍 **非** S2–S8 全量 PASS / 非 WorkBuddy 对等 / 未合 main。

## 10. 生产热更新验收（Codex · 2026-07-30 业主报告）

| 项 | 结果 |
|----|------|
| 部署 SHA（当时） | `12c31c907dada11f0dbac991008ea28673cf7f9e` |
| 分支 | `grok/pico-preview-librechat-p0` |
| compose | mongo / pico-api / librechat **Up** |
| health | ok |
| UI login API | 200 · token PRESENT |
| S1 | 200 · reply **演示OK** |
| 浏览器登录 | **Y** |
| 浏览器真聊 | **Y** ·「演示OK」 |
| 公网 | 443 open；8080/18765/27017 closed |
| 监听 | 127.0.0.1:{8080,18765,27017}；0.0.0.0:{80,443} Nginx |
| PROXY=1 | 未用 |
| 合 main / 自 PASS | **否** |

**额外（服务器本地）：** 强制 pico-api `127.0.0.1:18765`；关闭 Meili 噪音。仓内 `docker-compose.host.yml` 已对齐 127.0.0.1 + SEARCH=false / Meili 空 host。

**热更新命令已验证：** `git pull --ff-only` + `docker compose -f docker-compose.host.yml up -d`  
后续可用：`bash scripts/prod-update.sh`

**提醒：** 聊天出现过的 Kimi key 建议 Moonshot 轮换。

**注意：** 验收后 origin tip 可能继续前进（CI/selftest/prod-update 等）；生产可再 `prod-update.sh` 对齐最新 tip，不必重装。

## 11. 产物路径（2026-07-30 本地复验）

- Chat 创建 `hello.txt` → Task 账本 `artifacts` 含 `kind=file` title=`hello.txt` inline=`hi`
- 单元测试：`tests/unit/test_file_artifacts.py`
- selftest 步骤 7 覆盖
- 生产 health `git_sha: unknown`：部署时 `prod-update.sh` 写入 `PICO_GIT_SHA`；compose 注入 env

## 12. 二次「热更新报告」仍停在 12c31c9（2026-07-30）

Codex 再次回报 origin/local 均为 `12c31c9`，但 GitHub tip 已是 **`e22b602`**（及之后）。
含义：**生产未真正 fetch/reset 到最新 tip**（常见原因：本地改了 `docker-compose.host.yml` 导致 pull 未进、或只 up 未 pull、或旧报告复贴）。

纠正：
```bash
cd /opt/pico
git fetch origin
git reset --hard origin/grok/pico-preview-librechat-p0
# 或：EXPECT_SHA_PREFIX=e22b602 bash scripts/prod-update.sh
curl -sS http://127.0.0.1:18765/health   # 期望 git_sha 前缀 = tip，非 unknown/旧
```

