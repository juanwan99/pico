# ADR · 真 Pi 核嵌入选型（阶段1）

```text
DOC: docs/ADR-PI-TRUE-KERNEL-RPC.md
ID: ADR-PI-TRUE-KERNEL-RPC
DATE: 2026-08-10
STATUS: Proposed → 施工中（#431 P1）
Issue: https://github.com/juanwan99/pico/issues/431
调查: docs/INVESTIGATE-PI-TRUE-KERNEL-2026-08-10.md · #430
计划: docs/PLAN-PI-TRUE-KERNEL-2PHASE.md
基线 tip: 27954b2a59a5dcf8f5c57c1d51b176d205ff9e50
CLAIM-WB: NO
```

---

## 决策

| 项 | 选定 |
|----|------|
| **嵌入方式** | **`pi --mode rpc` sidecar**（stdin/stdout JSONL） |
| 未选 | 长期把编排侧迁 Node；Python 重写 Pi 内核；默认 Node SDK 微服务（二期可再评估） |
| **镜像** | 阶段1：宿主机/预发可选安装 `@mariozechner/pi-coding-agent@0.73.1`（钉版本）；生产默认镜像**不强制**装 Pi（旁路未开时零影响） |
| **模型** | 真 Pi 用内建 **deepseek** provider（`DEEPSEEK_API_KEY`）；与 hosted 同一密钥/模型环境 |
| **工具** | `--no-builtin-tools` + 仓内 extension 仅注册 Pico gateway 白名单工具；经 127.0.0.1 回调 Python 工具服 |
| **默认路径** | **不变**：`default_runtime=pi-agent` · hosted `pi_runtime.run_pi_agent` |
| **旁路开关** | `PICO_TRUE_PI_SHADOW=1` 双跑；`PICO_TRUE_PI_BYPASS=1` 仅显式旁路入口（非生产默认） |

## 理由

1. 调查结论：真 Pi 是 TS harness；非 Node 集成官方路径即 **RPC**。
2. RPC 进程可监督、可超时杀进程组、session 目录可隔离。
3. 工具回调留在 Python gateway → 账本/门闩/租户隔离不搬迁。
4. 桥保持薄：只做进程 + JSONL + 7 个工具回调 + 事件映射；不做第二 OS。

## 否决

| 方案 | 原因 |
|------|------|
| Python 重写 Pi 内核 | 失去 compaction/会话树/生态；与「换回真 Pi」目标相反 |
| 公网默认 bash / 内建 read·write·edit | 多租户安全否决 |
| 阶段1 切 `default_runtime` | 计划硬禁止；须 P1 READY 后再开 P2 |
| 桥内再造 delivery_policy / skill 全家桶 | 膨胀成第二 OS |

## 超时策略

| 层 | 策略 |
|----|------|
| RunCaps.max_seconds | 旁路与 hosted 同一 `caps.max_seconds` |
| 进程 | deadline 到 → RPC `abort` → 宽限后 SIGTERM 进程组 → SIGKILL |
| 取消 | `is_cancelled` 轮询 → 同上 abort/kill |
| 工具回调 | 单次 HTTP 超时 ≤ min(60s, remaining) |

## 桥职责白名单（防膨胀）

**允许：** spawn RPC · JSONL prompt/abort · 事件映射 · 7 工具回调 · session 目录 · shadow diff 报告  
**禁止：** bash · 任意 FS · 未登记 MCP · 在桥内实现 min_artifacts 业务分支副本以外的政策 · 第二账本

详见 [`docs/TRUE-PI-BRIDGE-DUTIES.md`](./TRUE-PI-BRIDGE-DUTIES.md)。

## 后果

- 阶段1 可单测验证映射/门闩/假绿，真二进制可选。
- 阶段2 切主前须：镜像钉 Pi 版本、健康字段、回滚 flag。
