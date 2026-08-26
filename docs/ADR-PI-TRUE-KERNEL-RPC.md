# ADR · 真 Pi 核嵌入选型

```text
DOC: docs/ADR-PI-TRUE-KERNEL-RPC.md
ID: ADR-PI-TRUE-KERNEL-RPC
DATE: 2026-08-10
STATUS: Accepted
Issue: #431 P1 · #433 P2 · #435 CUTOVER · #436 HYGIENE
调查: docs/INVESTIGATE-PI-TRUE-KERNEL-2026-08-10.md · #430（superseded for phase plan）
计划: docs/PLAN-PI-TRUE-KERNEL-2PHASE.md（superseded · 阶段完成）
钉版: @mariozechner/pi-coding-agent@0.73.1
CLAIM-WB: NO
```

---

## 决策

| 项 | 选定 |
|----|------|
| **嵌入方式** | **`pi --mode rpc` sidecar**（stdin/stdout JSONL） |
| 未选 | 长期把编排侧迁 Node；Python 重写 Pi 内核；默认 Node SDK 微服务 |
| **镜像** | 生产 host 路径：`Dockerfile.pico-api.true-pi`（Node 22 + 钉版 pi）；lean `Dockerfile.pico-api` 仅无真核场景 |
| **模型** | 真 Pi 用内建 **deepseek** provider（`DEEPSEEK_API_KEY`）；与 hosted 同一密钥环境 |
| **工具** | `--no-builtin-tools` + 仓内 extension 仅注册 Pico gateway 白名单（workspace/generate/verify + #507 `web_search`/`web_fetch`）；经 127.0.0.1 回调 Python。`prompt()` 可带 `images[]`（#703）；仍禁 host bash |
| **默认路径** | **`default_runtime=pi-true`**（`PICO_TRUE_PI_DEFAULT=1`） |
| **回滚** | **唯一事故路径** `PICO_HOSTED_LOOP=1` → hosted `pi_runtime`（`default_runtime=pi-agent`） |
| **过渡开关** | `SHADOW` / `BYPASS` / `CANARY` 非生产常态；禁止与 DEFAULT 双开装饰 |

## 理由

1. 调查结论：真 Pi 是 TS harness；非 Node 集成官方路径即 **RPC**。
2. RPC 进程可监督、可超时杀进程组、session 目录可隔离。
3. 工具回调留在 Python gateway → 账本/门闩/租户隔离不搬迁。
4. 桥保持薄：进程 + JSONL + 白名单工具回调 + 事件映射；不做第二 OS。
5. #507：`web_search` 是 DeepSeek Responses 官方工具的薄转发，不是自研搜索核；`web_fetch` 是网关 SSRF 护栏下的读页。

## 否决

| 方案 | 原因 |
|------|------|
| Python 重写 Pi 内核 | 失去 compaction/会话树/生态；与「换回真 Pi」目标相反 |
| 公网默认 bash / 内建 read·write·edit | 多租户安全否决 |
| 双默认核并列 | 失败模式×N；hosted 仅回滚 |
| 桥内再造 delivery_policy / skill 全家桶 | 膨胀成第二 OS |
| lean 镜像覆盖 DEFAULT=1 生产 | 静默丢 pi（#436 D1） |

## 超时策略

| 层 | 策略 |
|----|------|
| RunCaps.max_seconds | 真核与 hosted 同一 `caps.max_seconds` |
| 进程 | deadline → RPC `abort` → 宽限后 SIGTERM 进程组 → SIGKILL |
| 取消 | `is_cancelled` 轮询 → 同上 abort/kill |
| 工具回调 | 单次 HTTP 超时 ≤ min(60s, remaining) |

## 桥职责白名单（防膨胀）

**允许：** spawn RPC · JSONL prompt/abort · 事件映射 · 白名单工具回调（含 web_search/web_fetch）· session 目录 · 显式 shadow diff  
**禁止：** bash · 任意 FS · 未登记 MCP · 在桥内实现政策副本 · 第二账本

详见 [`docs/TRUE-PI-BRIDGE-DUTIES.md`](./TRUE-PI-BRIDGE-DUTIES.md)。  
运维/回滚：[`docs/OPS-TRUE-PI-ROLLBACK.md`](./OPS-TRUE-PI-ROLLBACK.md)。

## 后果

- P1：薄桥 + 单测 + 可选 live。
- P2：canary / DEFAULT / HOSTED 回滚 + live smoke。
- 切流 #435：公网 DEFAULT=1。
- 清场 #436：部署固化 true-pi 镜像 · 去掉过渡装饰开关 · 文档正名。
