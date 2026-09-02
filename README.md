# Pico

独立 **AI 底座 / AI 工作台**（非网盘、非教务 SaaS）。

## 目标（校正）

详见 **[docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md](docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md) §0-supreme**（最高：禁止自搞一套 / 禁止重体系）· **[docs/HANDOFF-WB-PI.md](docs/HANDOFF-WB-PI.md)** · **[docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md) v1.4** · **[docs/WHAT-IS-PICO.md](docs/WHAT-IS-PICO.md)** · **[AGENTS.md](AGENTS.md)**

任务进度与证据以 **GitHub PR/SHA/CI** 为准（[OneFlow](docs/ONEFLOW.md)）。

| | |
|--|--|
| 产品 | 任务型 AI 工作台（Web）· **WorkBuddy 程度六条** |
| 模型 | HTTPS API（**DeepSeek 为主**；Kimi 可选后备） |
| 编排 | **默认 = Pi Agent harness**；Kimi Agent = 遗产回滚 |
| 账本 | **仅 Pico**（禁止与 edu 双 AI） |
| 范围 | **只写本仓**；edu 对接后置 |
| 真源冻结 | **[docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md) v1.4** |
| 最高法律 | 禁止自搞一套体系 · 禁止做重体系 · 只允许薄适配 |

```text
最高：禁止自搞一套体系。禁止做重体系。
目标：Web 上 WorkBuddy 程度（六条）· 用法 = Grok
方案：回 Pico 整车 + 默认编排核 Pi + DeepSeek
不做：自研第二套能力核、Dify 门脸终局、场景考卷当对标、双核并列真源
```

## 当前产品壳

**LibreChat** → [`apps/librechat`](apps/librechat)（MIT 魔改，接 Pico OpenAI 兼容 API）

| 服务 | 地址 |
|------|------|
| 产品 UI | `0.0.0.0:8080`（LibreChat） |
| Pico API | `127.0.0.1:18765`（内网；勿当预览首页） |

```bash
./scripts/run-product.sh
```
