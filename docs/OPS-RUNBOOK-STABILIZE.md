# 运维短 Runbook（登录限流 · 测密 · health · 值班）

```
DOC: docs/OPS-RUNBOOK-STABILIZE.md
STATUS: BINDING ops discipline (post KA-3 · post GLOBAL #298 · harden #299)
STAGE: #284 / #298 / #299
PROD: https://pico.aivia.asia
LOOPBACK_HEALTH: http://127.0.0.1:18765/health  (via pico-prod SSH)
AUTH_HEALTH: GET /api/pico/health  (登录后 · 策略 A · 含 git_sha)
```

**原则：** 公网 `/health` 可能仅 `OK`；**字段真源在 loopback** 或 **登录后** `/api/pico/health`（策略 A）。禁止把密钥、原始 membership ID、完整 Bearer 贴进 Issue。**禁止**无设计把全量 health JSON 公网裸露。

---

## 0.1 分级 Run 预算（P-COMPLEX-DONE · 包 A）

| 档 | 用途 | 默认 |
|----|------|------|
| **delivery** | `pico-agent` / 课件等多步 | `PICO_RUN_MAX_SECONDS=900` · steps=24 · tokens=32000 |
| **short** | 直连模型短聊 | `PICO_RUN_SHORT_MAX_SECONDS=120` · tokens=8000 |

- 交付档 **禁止** 仍为 `120`（会 `Kimi Agent timeout after 120s` 杀课件）。
- 改 env 后须 recreate `pico-api`；可用 `bash scripts/apply-tiered-run-caps.sh --remote pico-prod`。

### 0.2 Durable Run（P-LONG-DURABLE · 包 B）

| 项 | 默认 |
|----|------|
| 页关 / SSE 断 | **不杀 job**（`PICO_RUN_DETACH_ON_DISCONNECT=1`） |
| 长跑墙钟 | `PICO_RUN_DURABLE_MAX_SECONDS=3600` |
| 权威 | 服务端 ledger（Task/Run/Event/Artifact） |
| 部署 | 进程重启 in-flight 可能丢 → 失败可 **续跑/retry**；见 `docs/ADR-DURABLE-RUN.md` |

- **禁止** 只把 `MAX_SECONDS` 拧到 28800 冒充 durable。
- 金路径：`POST /v1/durable-jobs`（wall≥1800）+ 关页后轮询 run 仍 running/succeeded。

---

## 1. 读 health（生产）

```bash
# 窗1 / 运维：loopback 字段真源
bash scripts/remote-health.sh pico-prod
# 或
ssh pico-prod 'curl -sf --max-time 5 http://127.0.0.1:18765/health'
```

### 1.0 窗4 tip 对齐（策略 A · #299 H1）

验证窗**不依赖** loopback/SSH 时：

1. 用密码器当前演示密登录 `https://pico.aivia.asia`  
2. 浏览器已登录会话下：`GET /api/pico/health`（同源；需 JWT cookie/header）  
3. 读 JSON 的 `git_sha`（40 位）与声明 tip **exact** 对齐  
4. 无 token → 401；**勿**把响应全文贴 Issue（可只贴 sha 前缀或 exact 结论）

| 面 | 期望 |
|----|------|
| 公网 `/health` | 200 常仅 `OK` — **不可**当 tip 证据 |
| loopback `/health` | 运维 JSON 真源 |
| `/api/pico/health` | 登录后 JSON · 含 `git_sha` · **窗4 SSOT** |

### 字段解读

| 字段 | 健康默认（KA-3 后） | 含义 |
|------|---------------------|------|
| `ok` | `true` | 进程存活 |
| `git_sha` | **40 位** full SHA | 必须与声明 tip exact 一致才可签阶段 |
| `kimi_agent_runtime_enabled` | `true` | `PICO_KIMI_AGENT_RUNTIME=1` |
| `kimi_agent_scope` | **`all`** | 空 canary = 全员 Kimi Agent |
| `kimi_agent_canary_membership_count` | `0` | 故意空名单；**非**「无人进 KA」 |
| `kimi_agent_canary_configured` | `false` | raw canary 空 |
| `legacy_loop_unavailable` | **`true` 恒定** | #295 F：过渡 loop **不可用**；回滚=redeploy tip（**不再**暴露 raw emergency 旗标） |
| `kimi_agent_canary_batch` | 如 `BATCH-KA3-DEFAULT` | 运维标签，非 principal |
| `rate_limit.chat_rpm` | 正数（现网常见 30） | 聊天 RPM |
| `rate_limit.chat_max_concurrent` | 正数（现网常见 2） | 并发上限 |
| `rate_limit.key_scope` | `membership_or_ip` | 限流键 |

**异常快判**

| 现象 | 优先动作 |
|------|----------|
| `git_sha` ≠ tip | 停签；查是否未部署或部署错 SHA |
| `scope=off` 且 runtime false | multi-step fail-closed（**无** loop） |
| 缺 `legacy_loop_unavailable` | tip 过旧或部署错；对齐 main 后再签 |
| `scope=canary` 且 count=0 | 可能是 **无效 non-empty canary** fail-closed — 查 raw 串 |

---

## 2. 登录限流（纪律）

1. **不要**为「测不通」反复改生产演示密码；错密应拒绝，对密应一次成功。  
2. 超 RPM / 并发 → API **429**（`PICO_CHAT_RPM` / `PICO_CHAT_MAX_CONCURRENT`）。冒烟时串行短任务，避免并行轰炸。  
3. 生产 `ALLOW_REGISTRATION=false`；演示号仅显式 seed（`PICO_DEMO_SEED=1` + 12+ 位密码）。  
4. 公网登录页 5xx：先 loopback LibreChat/`pico-api` health，再 nginx；**不要**先改 JWT/密钥。

### 2.1 限流看板（#299 H3）

| 读什么 | 哪里 |
|--------|------|
| 配置面 | loopback/登录 health → `rate_limit.chat_rpm` · `chat_max_concurrent` · `key_scope` |
| 触发态 | 超限响应 **HTTP 429** · body `user_message` **中文**（并发满 / RPM） |
| 复现纪律 | 受控 1 次并发或 RPM 触顶即可；**禁止**无脑轰炸；记录指纹（无密钥）后恢复串行短聊绿 |

---

## 3. 测密 / 凭据轮换（短）

1. **轮换前：** 确认新 `PICO_JWT_SECRET` / `PICO_OPENAI_PROXY_KEY` / LibreChat JWT 互不相同且 ≥32 字符；**永不**用 `pico-dev`。  
2. **写入：** 仅服务器 `/opt/pico/.env`（或部署通道），不进 git / Issue。  
3. **生效：** recreate 受影响容器（通常 `pico-api`；JWT 也可能影响 LibreChat）。  
4. **验证：** loopback health · 错密拒绝 · 一次正确登录或 proxy 短聊 · `git_sha` 仍对齐。  
5. **回滚：** 恢复上一份 env 备份 + recreate；写 `## DEPLOYED` 时间线（无密钥）。  
6. **实转须 AUTH**（#299 H4 / #298 G7）：无业主授权 → **BLOCKED** 诚实；密**永不**进 Issue。

### 3.1 凭据 SSOT（#299 H5 · R-B）

| 规则 | 说明 |
|------|------|
| **SSOT** | 密码器条目（演示教师 / 演示管理员 / 运维 JWT 等） |
| 仓库 | 只写账号**邮箱形态**与「从密码器取当前密」；**禁止**固定明文密 |
| 生产 seed | **默认关**（`PICO_DEMO_SEED` 非 1）；仅受控 reseed 时开，密仍只进密码器与服务器 env |
| 窗4 | 登录前强制从密码器取**当前**密；旧密 Incorrect password = 密钥库未同步，非必登录代码坏 |
| Issue | **禁止**贴密、JWT、完整 Bearer、proxy key |

---

## 4. 默认路由与回滚（KA-3 继承）

| 目标态 | 配置 |
|--------|------|
| 生产默认 | `PICO_KIMI_AGENT_RUNTIME=1` + **空** canary → scope=`all` |
| 紧急回 loop | **不可用**（KA-4 HARD）：`RUNTIME=0` / emergency → multi-step **fail-closed**，不进 loop |
| 有限 canary | RUNTIME=1 + 非空 **joint** `school:membership` 列表 |
| **回滚** | **redeploy previous tip**（`PICO_DEPLOY_SHA=<old> bash scripts/prod-update.sh`） |

**禁止：** 静默 dual-run；默认 DeepSeek/Pi；假删 runner。

---

## 5. 产物自读 / 教师 REST 路径表（R2/R5）

| 路径 | 期望 |
|------|------|
| 公网 `GET /health` | 200 `OK`（无字段） |
| loopback `GET /health` | JSON · git_sha · scope · `legacy_loop_unavailable` |
| UI 代理 `GET /api/pico/health` | **需登录**；200 JSON（无 token → 401）· **窗4 tip 对齐** |
| 公网 `GET /api/health` | 404 人话/非账本（**勿当** Pico 入口） |
| 账本 `GET /api/pico/v1/tasks` 等 | 需 JWT |
| 下载 `GET /api/pico/v1/artifacts/{id}/content?download=true` | 需 JWT · 正确 content 路径 |
| 虚构 `…/artifacts/{id}/download` | **不要用** |

- 真文件：`kind=html|docx|pptx` + `content_sha256` + 非空 `byte_size`
- 最小测（R8）：`bash scripts/run-min-tests.sh`（host 无 py3.12 时走 docker/CI）

---

## 7. 502 值班面（#299 H2 / #298 G6）

| 项 | 路径 / 动作 |
|----|-------------|
| 公网采样脚本 | `bash scripts/public-502-monitor.sh`（`ONCE=1` 单采；默认长窗） |
| Jump 公网 cron（参考） | 每 15m · `/login`+`/health` → `/home/ops/var/pico-502-monitor/` |
| Prod loopback cron（参考） | 每 15m · `127.0.0.1:18765/health` → `/opt/pico/var/502-monitor/` |
| DUTY 摘要 | `/opt/pico/var/502-monitor/DUTY.txt` 或 jump 目录 `summary-*.txt` |
| **阈值** | 15min 窗内 **≥2 次非 2xx** → 值班查 loopback health → 容器 → nginx；**勿**先改密钥 |
| 失败退出码 | 脚本非 0 或 summary 含 FAIL/502 → 同上 |
| 谁看 | 窗1 部署窗 / 业主值班；Issue 只贴 **无密钥** 摘要（codes + 时间） |

**值班检查清单（可复制）**

1. `ONCE=1 bash scripts/public-502-monitor.sh` 或读最新 summary  
2. 非 2xx ≥2？→ `bash scripts/remote-health.sh pico-prod`  
3. health `ok`/`git_sha` 异常？→ 查 compose/ps · nginx error · 最近 `## DEPLOYED`  
4. 记录 Issue 一行结论（无密钥）

---

## 8. 本阶段不写

- 自签重开全球 product PASS（#298 已签；定义见 [PRODUCT-PASS-CONTRACT.md](./PRODUCT-PASS-CONTRACT.md)）  
- 「emergency 可回 loop」（**禁止**；health 仅 `legacy_loop_unavailable=true`）  
- 假 ENGINEERING complete（须证据矩阵，见 KIMI-AGENT-GAP）  
- 无 AUTH 测密实转 / 密钥进 Issue
