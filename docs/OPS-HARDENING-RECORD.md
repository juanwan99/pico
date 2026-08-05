# 运维 hardening 实测记录（#295 G · 无密钥）

```
DOC: docs/OPS-HARDENING-RECORD.md
STATUS: evidence record
STAGE: #295 P-POST-RESIDUAL-MEGA
DATE: 2026-08-05
PROD: https://pico.aivia.asia
```

**原则：** 本文件只记步骤与结果；**禁止**密文、完整 Bearer、原始 membership ID。

---

## 1. 测密轮换 — dry-run 步骤实测

按 [OPS-RUNBOOK-STABILIZE.md](./OPS-RUNBOOK-STABILIZE.md) §3，本包执行 **dry-run（不改生产密钥）**：

| 步 | 动作 | 结果 |
|----|------|------|
| 1 | 确认生产 tip 与 loopback health 可读 | `bash scripts/remote-health.sh` → `ok=true` · `git_sha` 40 位 |
| 2 | 列出轮换对象（名 only） | `PICO_JWT_SECRET` · `PICO_OPENAI_PROXY_KEY` · LibreChat JWT（均 ≥32、互不相同、非 `pico-dev`） |
| 3 | 确认写入面 | 仅服务器 `/opt/pico/.env`（或部署通道）；**不**进 git / Issue |
| 4 | 生效方式（口述 checklist） | recreate `pico-api`（JWT 也可能影响 LibreChat） |
| 5 | 验证清单（轮换后必做） | loopback health · 错密拒绝 · 一次正确登录或 proxy 短聊 · `git_sha` 仍对齐 |
| 6 | 回滚清单 | 恢复上一份 env 备份 + recreate · 时间线写 `## DEPLOYED`（无密钥） |

**本包结论：** dry-run **PASS**（步骤可走通；**未**在生产写入新密钥，避免演示中断）。实转须业主另令。

---

## 2. 限流演练

| 项 | 期望 | 证据形态 |
|----|------|----------|
| chat RPM | 超 `PICO_CHAT_RPM` → **429** | health `rate_limit.chat_rpm`（现网常见 30） |
| 并发 | 超 `PICO_CHAT_MAX_CONCURRENT` → 忙态/429 人话 | health `rate_limit.chat_max_concurrent`（现网常见 2） |
| 人话 | 用户可见繁忙/限流文案，非裸栈 | `user_errors` / UI |

**演练纪律（本包）：** 冒烟串行短任务；不并行轰炸生产。  
**健康默认可见：** loopback health 含 `rate_limit.key_scope=membership_or_ip`。

若需强制 429 压测：仅在业主批准窗口用受控脚本；结果记 run 指纹与 HTTP 码，**不**贴密钥。

---

## 3. 监控 / 告警建议

| 指标 | 来源 | 告警建议 |
|------|------|----------|
| 5xx rate on `/login` | 公网 nginx / `scripts/public-502-monitor.sh` | 15min 窗内 ≥2 次非 2xx → 查 LibreChat + pico-api loopback |
| `health.git_sha` drift | loopback `/health` via `remote-health.sh` | ≠ main tip → 停签 / 查部署 |
| login 5xx | 公网 `/login` | 先 loopback 再 nginx；**勿**先改 JWT |
| chat 429 突增 | API 日志 / rate_limit | 区分攻击与合法忙态 |
| `legacy_loop_unavailable` | loopback health | 必须为 `true`；缺字段 = 旧 tip |

**钩子：**

```bash
# 长窗 502 采样（默认 ~15min）
bash scripts/public-502-monitor.sh
# 单点
ONCE=1 bash scripts/public-502-monitor.sh
# tip 对齐
bash scripts/remote-health.sh pico-prod
```

---

## 4. 本包未做

- 生产实转密钥  
- 压测打爆 RPM  
- 假全球 product PASS
