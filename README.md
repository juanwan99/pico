
## Product shell (current)

**Default UI = `apps/workbench`** — task workbench IA (inspired by desktop agent workspaces like WorkBuddy: 新建任务 / 模式切换 / 能力 chip / 大输入卡).  
Branding is **Pico only** (not a fork of any commercial client).  
NextChat remains under `apps/nextchat` as legacy chat shell.

# Pico

**Standalone AI foundation** for the 微与积 / edu product line.

Pico is **not** a second school SaaS and **not** a teacher netdisk product.  
It is the **AI space**: experience + agent orchestration + model API access.

## Product shape

| Layer | Responsibility |
|-------|----------------|
| Experience | Claude-style IA (chat + artifacts) + Kimi-like density |
| Agent orchestration | **Kimi open-source Agent runtime** (thin adapters only) |
| Governance facts | Task / Run / Event owned in Pico DB (unique AI ledger) |
| Models | **HTTP APIs only** (Kimi / DeepSeek); keys never in the browser |
| Education SaaS | **[edu-cloud](https://github.com/juanwan99/edu-cloud)** — Phase 3 wire-up |

## Status

**3-Day MVP plan: FIXED v1.2** — [`docs/MVP-3DAY.md`](docs/MVP-3DAY.md)

| Phase | Goal |
|-------|------|
| **1 (this repo now)** | Independent Pico: Agent + model API + UI + ledger + CI |
| **2** | Integration contracts |
| **3** | edu-cloud wire-up + retire edu AI |

Handoff: [`docs/HANDOFF.md`](docs/HANDOFF.md)  
D1 freeze: [`docs/D1-FREEZE.md`](docs/D1-FREEZE.md)  
Demo: [`docs/DEMO.md`](docs/DEMO.md)  
Phase 1 status: [`docs/PHASE1-STATUS.md`](docs/PHASE1-STATUS.md)  
Phase 2 contracts: [`docs/PHASE2-CONTRACTS.md`](docs/PHASE2-CONTRACTS.md) **FROZEN v1.0**  
Phase 3 integrate: [`docs/PHASE3-INTEGRATION.md`](docs/PHASE3-INTEGRATION.md)

## Product UI (binding)

| Use | Do not use |
|-----|------------|
| **`apps/nextchat`** | ~~`apps/web`~~ **deleted** — hand-rolled 三栏 scaffold |

## Layout

```text
apps/nextchat/            **Product UI** (NextChat OSS · Claude/Codex-class)
services/api/             FastAPI control plane
services/orchestrator/    Kimi Agent pin + allowlist gateway
docs/contracts/           Phase 2 contract skeletons
tests/security/           Shell/File/Web/MCP-off proofs
```

## Prerequisites

- **Python 3.12+** (kimi-agent-sdk requires ≥3.12; plan floor was 3.11+)
- Node 20+ (22 recommended)
- Optional: `KIMI_API_KEY` for S1 real-model streaming

## Quick start — 产品预览

```bash
cp .env.example .env   # set KIMI_API_KEY
make product           # API :8000 + **NextChat** :8080
# open http://127.0.0.1:8080  （完整 AI 产品壳，不是三栏脚手架）
make demo              # headless API proof
```

**禁止** 再引入 `apps/web` 自研三栏壳。产品 UI = `apps/nextchat` only.

Demo: [`docs/DEMO.md`](docs/DEMO.md)

### Manual two-terminal

```bash
make install
make api    # terminal A → :8000
make ui     # terminal B → NextChat :8080
```

### Useful commands

```bash
make test            # unit + security
make security-check  # agent tools OFF proof
make freeze-check    # pinned SDK/runtime versions
make hello           # real model hello or honest S1 BLOCKED
```



## Preview port rule (Grok live preview)

The live preview **probes local ports** and will attach to **:8000** if anything answers there
(typically FastAPI JSON). Product UI must be the **only** service on **:8080**.

| Port | Bind | Role |
|------|------|------|
| **8080** | `0.0.0.0` | **NextChat product UI only** |
| **18765** | `127.0.0.1` | Pico API (internal) |
| **8000** | — | **MUST be free** |


## One-stop runbook（L2）

### 起服务

```bash
cp .env.example .env
# 必填（S1 真模型）：KIMI_API_KEY=sk-...
# 可选：PICO_ENV=development
# 可选（NextChat 代理）：PICO_OPENAI_PROXY_KEY=  # 生产勿用；开发可用 pico-dev 作为 UI 侧 key 名约定

make install          # Python 3.12+
make api              # 终端 A → http://127.0.0.1:8000
make ui               # 终端 B → NextChat http://127.0.0.1:8080
```

或：`make proto`（若 Makefile 提供一键）。

### 主路径

1. 打开 Web → 自动/设置页领取 dev JWT（`/v1/dev/token`）
2. 发送「列出我学校的班级」
3. NextChat 经 OpenAI 兼容 `POST /v1/chat/completions` 走 Pico Agent + 账本
4. 流式/停止由 NextChat + 后端 cancel/流式语义承担

### 端口

| 服务 | 地址 |
|------|------|
| API | `http://127.0.0.1:8000` |
| Product UI（NextChat） | `http://127.0.0.1:8080` |
| 健康检查 | `GET /health` |

### 失败对照

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| 「无法连接 Pico」 | API 未起 / 端口错 | `make api`；查 8000 |
| 「模型服务未配置」 | 无 `KIMI_API_KEY` | 写入 `.env` 后重启 API |
| 401 / 登录 | 无 JWT | 设置页重新 mint token |
| 跨校拒绝 | 预期 fail-closed | 用建议「跨校拒绝演示」 |
| 停止无反应 | 代理/模型卡住 | 刷新；查 API 日志；确认 :8080 是 NextChat |
| NextChat 401 | 生产禁 proxy key | 用 Pico JWT；dev 仅 `pico-dev` / `PICO_OPENAI_PROXY_KEY` |

### 证据命令

```bash
make test
make security-check
curl -s localhost:8000/health
curl -s localhost:8000/v1/meta/agent-safety
```

工作流：见 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)（CANDIDATE → CI → 审查 → 值守合）。


## Agent pin (D1)

| Package | Version |
|---------|---------|
| `kimi-agent-sdk` | **0.0.5** |
| `kimi-cli` | **1.12.0** |

Dangerous host tools (Shell / File / Web / MCP) are **off** in  
`services/orchestrator/agents/pico.yaml`. See CI job + `tests/security`.

## Phase 1 success criteria

S1–S8 are defined in [`docs/MVP-3DAY.md`](docs/MVP-3DAY.md).  
Write windows have **`VERDICT_AUTHORITY: NONE`** — do not self-PASS.

## Non-goals (Phase 1)

- Daily edu-cloud integration / dual AI ledger
- Netdisk product center
- Custom agent OS
- Unattended merge to `main`
