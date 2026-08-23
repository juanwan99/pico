# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-23（晚）
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 等业主 OWNER DECISION（#449）
公网 tip（本次刷新时）: 735dd363a67681900f5364a2a06353a2ef3eaa51（= main）
  · 开工必 curl 实查：curl -fsS https://pico.aivia.asia/api/pico/tip
活动主线: ① #623 尾段复验中（关卡后）② 阶段 1.5「AI 本体 + 知识库」两包
  · 方向真源 DIRECTION-NOW §0b · 卡序：T-CI-UI-GATE → A1 → A2 → B1 → A3 → B2 → B3
工作流: OneFlow v2（#619 已合）— 四行卡 · 禁 315 填表
```

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线（阶段 1.5 · 2026-08-23 晚）

| 优先级 | Issue / PR | 说明 |
|--------|-------|------|
| **收尾中** | [#623](https://github.com/juanwan99/pico/issues/623) | T-ARTIFACT-FIX-V2：三波已合已部（#624/#625 · tip `735dd363…`），差最后人路径复验回执后关卡 |
| **下一张** | T-CI-UI-GATE | `ci.yml` 补前端 jest/tsc + 工作区包构建门（红路径 `.github/workflows` · 业主 2026-08-23 已授权） |
| 排队 | 包 A 知识库 A1→A2→A3 · 包 B AI 本体 B1→B2→B3 | 见 [DIRECTION-NOW §0b](./DIRECTION-NOW.md)；SOLO 一张在飞，禁并行抢仓 |
| 等业主配钥 | `SILICONFLOW_API_KEY` | ECS `.env`（compose 已留位）；有钥 A1 上 hybrid，无钥先纯全文诚实降级 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | CLAIM 材料等**业主** · 工程禁代签 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | KA-3 默认切流须业主书面授权 · 未执行 · **勿关** |
| 规划/讨论 | [#505](https://github.com/juanwan99/pico/issues/505) · [#530](https://github.com/juanwan99/pico/issues/530)（序1/序2 已激活） · [#498](https://github.com/juanwan99/pico/issues/498) · [#600](https://github.com/juanwan99/pico/issues/600) | 规划稿/指针 · **勿关** |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) · [#573](https://github.com/juanwan99/pico/issues/573) | controller-bot poll log · 总管交接 · 长期开 |

```text
2026-08-23 已收口：#615 #613 #619 #620 #621 #622 #624 #625 · #586 关闭不合（业主决定 · 分支保留）
现网 tip 735dd363… 已含：十轮收尾 · 中文进度 · 三修 + 租户钥同柜 + PDF Authorization
禁止误关：#316 #449 #498 #505 #530 #170 #475 #573 #600
禁止把已 close 卡当活动主线
```

## 业主方向（最新 BINDING）

见 **[docs/DIRECTION-NOW.md](./DIRECTION-NOW.md)**（四条目标收窄）。

```text
1) 通用开放域 · 教育仅之一
2) Pi + DeepSeek
3) 通用能力 + 复杂问题（办公优先）
4) 对标 WorkBuddy · 本阶段只打牢 Agent + UI/UX
   不做：连接器 / MCP / Skill 摊子
```

## 锁定句

```text
目标：Web 上对标 WorkBuddy 的办事能力（体验向）
方案：Pico 整车 + Pi + DeepSeek
本阶段：基础能力（Agent 优化 + 交互体验）
不做：Dify 门脸 · 场景卷对标 · 双核 · MCP/Skill/连接器铺开
验收秤：阶段一底座全优 → 阶段二加压；基建是手段
CLAIM-WB-DEGREE-WEB: NO
```

## 工程快照

| 项 | 值 |
|----|-----|
| 公网 tip | `GET /api/pico/tip` → 须 40 位实查（派卡时 `78441483…`） |
| multi-step 默认 | **pi-true**（`PICO_TRUE_PI_DEFAULT=1`） |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| 钉版 | `@mariozechner/pi-coding-agent@0.73.1` |
| drain | 45s inflight · grace 60s · **≠ 零中断** |
| 真源主机 | ECS `47.121.197.52`（`ssh ecs` · `/opt/pico` · 18765）；dmit 仅 443 反代 |
| 搜索 | gateway `web_search` / `web_fetch` · 来源链接或「未检索到可用来源」 |
| P4 出图 | **HOLD** · 禁当交件 |
| CLAIM-WB | **NO** |

## 错误记忆

见 MEMORY-RESET：禁止 edu 串仓；禁止工程代签 CLAIM-WB YES；禁止把冻结 tip 当现网 tip；禁止把已关空壳当活动主线；禁止 315 填表卡面（OneFlow v2 后四行卡）。
