# 运维短 Runbook（登录限流 · 测密 · health）

```
DOC: docs/OPS-RUNBOOK-STABILIZE.md
STATUS: BINDING ops discipline (post KA-3)
STAGE: #284 P-POST-KA3-STABILIZE
PROD: https://pico.aivia.asia
LOOPBACK_HEALTH: http://127.0.0.1:18765/health  (via pico-prod SSH)
```

**原则：** 公网 `/health` 可能仅 `OK`；**字段真源在 loopback**。禁止把密钥、原始 membership ID、完整 Bearer 贴进 Issue。

---

## 1. 读 health（生产）

```bash
# 从跳板/本机有 pico-prod 配置时
bash scripts/remote-health.sh pico-prod
# 或
ssh pico-prod 'curl -sf --max-time 5 http://127.0.0.1:18765/health'
```

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

---

## 3. 测密 / 凭据轮换（短）

1. **轮换前：** 确认新 `PICO_JWT_SECRET` / `PICO_OPENAI_PROXY_KEY` / LibreChat JWT 互不相同且 ≥32 字符；**永不**用 `pico-dev`。  
2. **写入：** 仅服务器 `/opt/pico/.env`（或部署通道），不进 git / Issue。  
3. **生效：** recreate 受影响容器（通常 `pico-api`；JWT 也可能影响 LibreChat）。  
4. **验证：** loopback health · 错密拒绝 · 一次正确登录或 proxy 短聊 · `git_sha` 仍对齐。  
5. **回滚：** 恢复上一份 env 备份 + recreate；写 `## DEPLOYED` 时间线（无密钥）。

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
| UI 代理 `GET /api/pico/health` | **需登录**；200 JSON（无 token → 401） |
| 公网 `GET /api/health` | 404 人话/非账本（**勿当** Pico 入口） |
| 账本 `GET /api/pico/v1/tasks` 等 | 需 JWT |
| 下载 `GET /api/pico/v1/artifacts/{id}/content?download=true` | 需 JWT · 正确 content 路径 |
| 虚构 `…/artifacts/{id}/download` | **不要用** |

- 真文件：`kind=html|docx|pptx` + `content_sha256` + 非空 `byte_size`
- 最小测（R8）：`bash scripts/run-min-tests.sh`（host 无 py3.12 时走 docker/CI）

---

## 6. 本阶段不写

- 全球 product PASS（定义见 [PRODUCT-PASS-CONTRACT.md](./PRODUCT-PASS-CONTRACT.md)）  
- 「emergency 可回 loop」（**禁止**；health 仅 `legacy_loop_unavailable=true`）  
- 假 ENGINEERING complete（须证据矩阵，见 KIMI-AGENT-GAP）
