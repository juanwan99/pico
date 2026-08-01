# Pico

独立 **AI 底座 / AI 工作台**（非网盘、非教务 SaaS）。

## 目标（校正）

详见 **[docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md)**（冻结真源）· **[docs/README.md](docs/README.md)** · **[docs/WHAT-IS-PICO.md](docs/WHAT-IS-PICO.md)** · **[docs/CORRECTED-GOALS.md](docs/CORRECTED-GOALS.md)** · **[docs/MVP-3DAY.md](docs/MVP-3DAY.md) v1.2** · **[AGENTS.md](AGENTS.md)**

任务进度与证据以 **GitHub PR/SHA/CI** 为准（[OneFlow](docs/ONEFLOW.md)）；勿用交接 MD。

| | |
|--|--|
| 产品 | Claude / Codex / WorkBuddy **品类**的 AI 工作台 + 产物 + **唯一 AI 账本** |
| 模型 | HTTPS API（**Kimi 优先**，已用） |
| 编排 | **目标** = 开源 Kimi Agent 真接入；**现状** = 过渡自研环（见 [docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md) · [docs/WHAT-IS-PICO.md](docs/WHAT-IS-PICO.md)） |
| 账本 | **仅 Pico**（禁止与 edu 双 AI） |
| 范围 | **只写本仓**；edu 对接后置 |
| 真源冻结 | **[docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md) v1.0**（防丢失） |

## 当前产品壳

**LibreChat** → [`apps/librechat`](apps/librechat)（MIT 魔改，接 Pico OpenAI 兼容 API）

| 服务 | 地址 |
|------|------|
| 产品 UI | `0.0.0.0:8080`（LibreChat） |
| Pico API | `127.0.0.1:18765`（内网；勿当预览首页） |

```bash
./scripts/run-product.sh
```

生产默认关闭开放注册和演示账号播种。仅在获批演示窗显式设置
`PICO_DEMO_SEED=1`、邮箱及 12 位以上随机密码；不要使用仓库内固定密码。

## 禁止

- 改 edu-cloud  
- 恢复 `apps/web` 自研三栏  
- 拆闭源 WorkBuddy  
- 自 PASS / 无人合 main  
