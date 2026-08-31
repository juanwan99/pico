# 运维 · 真 Pi 核 · 部署与一页回滚

```text
DOC: docs/OPS-TRUE-PI-ROLLBACK.md
DATE: 2026-08-10
Issue: #433 · #431 · #435 · #436
钉版: @earendil-works/pi-coding-agent@0.84.4
CLAIM-WB: NO
```

---

## 常态（清场后）

| 态 | 条件 | health.default_runtime | health.true_pi_phase |
|----|------|------------------------|---------------------|
| **真核默认** | `PICO_TRUE_PI_DEFAULT=1` · `HOSTED_LOOP` 未设 | `pi-true` | `p2-default` |
| **事故回滚** | **`PICO_HOSTED_LOOP=1`**（唯一事故路径） | `pi-agent` | `hosted-rollback` |

生产**不**长期开：`BYPASS` · `SHADOW` · 与 DEFAULT 双开的装饰性 `CANARY=*`。

---

## 开关一览

| 环境变量 | 作用 | 生产常态 |
|----------|------|----------|
| `PICO_TRUE_PI_DEFAULT=1` | multi-step **默认真核** | **开** |
| **`PICO_HOSTED_LOOP=1`** | **一键回滚 hosted `pi_runtime`** | **关**（事故时开） |
| `PICO_TRUE_PI_CANARY=school:member,...` | 灰度（DEFAULT 关时名单走真核） | **关**（DEFAULT 已开时忽略/勿装饰） |
| `PICO_TRUE_PI_BYPASS=1` | 强制全量真核（运维窗口） | **关** |
| `PICO_TRUE_PI_SHADOW=1` | hosted 后旁路对账 | **关** |
| `PICO_TRUE_PI_BIN` | pi 可执行路径 | 镜像内 PATH 即可 |
| `PICO_TRUE_PI_SESSION_ROOT` | session 目录父路径 | 可选 |
| `DEEPSEEK_API_KEY` | 模型密钥（与 hosted 同） | 生产已有 |

优先级：`HOSTED_LOOP` > `BYPASS` > `DEFAULT` > `CANARY` > hosted。

---

## 镜像 / 部署真源

### 生产 compose（host）

- `docker-compose.host.yml` → **`Dockerfile.pico-api.true-pi`**
- 钉版：`@earendil-works/pi-coding-agent@0.84.4`（Node ≥ 20，镜像装 22）
- `scripts/prod-update.sh` 部署后校验：`health.true_pi_binary_available=true`（失败 exit 8）

### Lean 镜像

- `Dockerfile.pico-api` = 纯 Python，**不含** pi
- **禁止**在 `DEFAULT=1` 的公网路径用 lean 覆盖 true-pi 镜像

### health 自证

```text
GET /health  (loopback 18765 或 SSH 通道)
default_runtime: pi-true | pi-agent
true_pi_binary_available: true|false
true_pi_default_enabled: true|false
true_pi_hosted_loop_forced: true|false
true_pi_phase: p2-default | hosted-rollback | p2-canary | p2-bypass | p1-shadow | idle
true_pi_package_pin: @earendil-works/pi-coding-agent@0.84.4
```

---

## 事故回滚（唯一路径）

```bash
# 1) 立即回 hosted（无需重新部署代码）
# 在 /opt/pico/.env：
#   PICO_HOSTED_LOOP=1
# 保留 PICO_TRUE_PI_DEFAULT=1 亦可（HOSTED 优先）
cd /opt/pico
docker compose -f docker-compose.host.yml up -d --force-recreate --no-deps pico-api

# 2) 验证（loopback）
curl -sf http://127.0.0.1:18765/health | python3 -c \
  'import json,sys; h=json.load(sys.stdin); print({k:h.get(k) for k in
   ["default_runtime","true_pi_hosted_loop_forced","true_pi_binary_available","true_pi_phase"]})'
# 期望: default_runtime=pi-agent · true_pi_hosted_loop_forced=true · phase=hosted-rollback

# 3) 开放域 1 题冒烟（hosted）
# 4) Issue 贴 ## ROLLBACK · tip · 原因

# 恢复真核：删 .env 中 PICO_HOSTED_LOOP 行 → 再 recreate pico-api
```

**禁止：** 为回滚删除 `pi_runtime.py`；为刷绿关闭落盘门闩；用关 `DEFAULT` 代替 `HOSTED_LOOP` 当唯一文档路径（可关，但事故首选 HOSTED）。

---

## 切主后观察（已完成见 #435）

```text
1. tip 含 true_pi 代码
2. 镜像 Dockerfile.pico-api.true-pi · binary=true
3. PICO_TRUE_PI_DEFAULT=1 · HOSTED/BYPASS/SHADOW 关 · 无装饰 CANARY
4. health: default_runtime=pi-true · phase=p2-default
5. 任一红 → PICO_HOSTED_LOOP=1
```
