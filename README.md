# Pico

独立 **AI 底座 / AI 工作台**（非网盘、非教务 SaaS）。

## 目标（校正）

详见 **[docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md](docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md) §0-supreme**（最高：禁止自搞一套 / 禁止重体系）· **[AGENTS.md](AGENTS.md)** 文首工作法 · **[docs/DIRECTION-NOW.md](docs/DIRECTION-NOW.md) §0-star** · **[docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md) v1.8** · **[docs/WHAT-IS-PICO.md](docs/WHAT-IS-PICO.md)** · 开窗目录 **[docs/README.md](docs/README.md)**

任务进度与证据以 **GitHub PR/SHA/CI** 为准（[OneFlow](docs/ONEFLOW.md)）。

| | |
|--|--|
| 产品 | 通用 LLM 工作台（Web）· 用法 = Grok · 主线 = 真 Word/Excel/HTML/PPT · 体验上限 = WorkBuddy 六条 |
| 模型 | 云端 HTTPS API（现网 New API `openai-responses`，见 EXPERIENCE §34；对外只叫 Pico） |
| 编排 | **默认 = 真 Pi**（`health.default_runtime=pi-true`）；hosted / Kimi = 遗产回滚 |
| 办公 | 天花板 = 隔离 `sandbox_office_lib`；`generate_*` 不在默认常驻 |
| 账本 | **仅 Pico**（禁止与 edu 双 AI） |
| 范围 | **只写本仓**；edu 对接后置 |
| 真源冻结 | **[docs/TRUTH-FREEZE.md](docs/TRUTH-FREEZE.md) v1.8** |
| 最高法律 | 禁止自搞一套体系 · 禁止做重体系 · 只允许薄适配 |

```text
最高：禁止自搞一套体系。禁止做重体系。
目标：Web 上 WorkBuddy 程度（六条）· 用法 = Grok · 办公主线（Word/Excel/HTML/PPT）· 写代码是仆人 · 能力并列 · 办公计算机交成熟上游（阶段方案 docs/PLAN-WORKENV-UPSTREAM.md）
方案：回 Pico 整车 + 默认真 Pi + New API 脑/计量 + 隔离办公库
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
