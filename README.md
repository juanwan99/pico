# Pico

独立 **AI 底座 / AI 工作台**（非网盘、非教务 SaaS）。

## 目标（校正）

详见 **[docs/CORRECTED-GOALS.md](docs/CORRECTED-GOALS.md)** · 计划 **[docs/MVP-3DAY.md](docs/MVP-3DAY.md) v1.2** · 规则 **[AGENTS.md](AGENTS.md)**

| | |
|--|--|
| 产品 | Claude / Codex / WorkBuddy **品类**的 AI 空间 + Agent + 产物 |
| 编排 | 开源 Kimi Agent（钉版本） |
| 模型 | HTTPS API（Kimi 优先） |
| 账本 | **仅 Pico**（禁止与 edu 双 AI） |
| 范围 | **只写本仓**；edu 对接后置 |

## 当前产品壳

**LibreChat** → [`apps/librechat`](apps/librechat)（MIT 魔改，接 Pico OpenAI 兼容 API）

| 服务 | 地址 |
|------|------|
| 产品 UI | `0.0.0.0:8080`（LibreChat） |
| Pico API | `127.0.0.1:18765`（内网；勿当预览首页） |

```bash
./scripts/run-product.sh
```

演示账号（LibreChat）：`teacher@example.com` / `pico-demo-123`

## 禁止

- 改 edu-cloud  
- 恢复 `apps/web` 自研三栏  
- 拆闭源 WorkBuddy  
- 自 PASS / 无人合 main  
