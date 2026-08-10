# 运维 · 真 Pi 核 · 部署与一页回滚

```text
DOC: docs/OPS-TRUE-PI-ROLLBACK.md
DATE: 2026-08-10
Issue: #433 · #431
钉版: @mariozechner/pi-coding-agent@0.73.1
CLAIM-WB: NO
```

---

## 开关一览

| 环境变量 | 作用 |
|----------|------|
| `PICO_TRUE_PI_DEFAULT=1` | multi-step **默认真核** |
| `PICO_TRUE_PI_CANARY=school:member,...` 或 `*` | 灰度（默认仍 hosted，仅名单走真核） |
| `PICO_TRUE_PI_BYPASS=1` | 强制全量真核（运维/预发） |
| `PICO_TRUE_PI_SHADOW=1` | hosted 主路径后旁路对账（不切主） |
| **`PICO_HOSTED_LOOP=1`** | **一键回滚 hosted `pi_runtime`** |
| `PICO_TRUE_PI_BIN` | pi 可执行文件路径 |
| `PICO_TRUE_PI_SESSION_ROOT` | session 目录父路径 |
| `DEEPSEEK_API_KEY` | 模型密钥（与现网一致） |

---

## 镜像 / 进程

### 最低要求（真核路径）

- Node.js ≥ 20（现网 22 OK）
- 全局或镜像内：`npm i -g @mariozechner/pi-coding-agent@0.73.1`
- `pi` 在 PATH，或设 `PICO_TRUE_PI_BIN`
- 扩展文件：`services/true_pi_bridge/pico-gateway-tools.ts` 随仓拷贝

### Dockerfile 备注

默认 `Dockerfile.pico-api` 仍是 **纯 Python lean 镜像**（公网未开真核时零影响）。  
开真核时使用 `Dockerfile.pico-api.true-pi`（含 Node + 钉版 pi），或宿主机 sidecar 安装 pi。

### health 自证

```text
GET /health
default_runtime: pi-true | pi-agent
true_pi_binary_available: true|false
true_pi_default_enabled: true|false
true_pi_hosted_loop_forced: true|false
true_pi_package_pin: @mariozechner/pi-coding-agent@0.73.1
```

---

## 回滚（事故 / R 红）

```bash
# 1) 立即回 hosted（无需重新部署代码）
export PICO_HOSTED_LOOP=1
# 或取消 true default:
unset PICO_TRUE_PI_DEFAULT
# 2) 重启 API 进程 / 容器使 env 生效
# 3) 验证
curl -sS https://pico.aivia.asia/health | jq '{default_runtime,true_pi_hosted_loop_forced,true_pi_binary_available}'
# 期望 default_runtime=pi-agent（或 true_pi_hosted_loop_forced=true）
# 4) 开放域 1 题冒烟
# 5) Issue 贴 ## ROLLBACK · tip · 原因
```

**禁止：** 为回滚删除 `pi_runtime.py`；为刷绿关闭落盘门闩。

---

## 推荐切主顺序

```text
1. 部署含 true_pi 的 tip（#432+）
2. 宿主机/镜像安装钉版 pi · health.true_pi_binary_available=true
3. LIVE L1–L5 绿（旁路 BYPASS 或 canary）
4. PICO_TRUE_PI_CANARY 灰度
5. PICO_TRUE_PI_DEFAULT=1 · 观察
6. R1–R7 回归
7. 任一红 → PICO_HOSTED_LOOP=1
```
