# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-23（v1.2 两卡压缩）
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 等业主 OWNER DECISION（#449）
公网 tip（本次刷新 curl）: b713464ca05cb54fc2c30309cf05dc8f3710a825（#629 SSO 聊天 403）
origin/main: 6e2adda6e47d7b932ca35f38b90ff0f3acee3773（#627 CI 门已合 · 不部）
  · 开工必 curl 实查：curl -fsS https://pico.aivia.asia/api/pico/tip
活动主线: ① #627 已关 ② 下一张 #628 T-KB-CATCH（无 stamp-ok）③ 排队 #637 T-RUNTIME-CATCH（须 628 关卡）
  · 方向真源 DIRECTION-NOW §0b v1.2 · 卡序：#628 → #637
工作流: OneFlow v2（#619 已合）— 四行卡 · 禁 315 填表
本窗交接: docs/HANDOFF-NEW-WINDOW-2026-08-23.md · Issue #634（#573 作废）
```

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线（阶段 1.5 · v1.2 两卡）

| 优先级 | Issue / PR | 说明 |
|--------|-------|------|
| **下一张** | [#628](https://github.com/juanwan99/pico/issues/628) | T-KB-CATCH 知识库整包（原 A1+A2+A3）· **无 stamp-ok** |
| 排队 | [#637](https://github.com/juanwan99/pico/issues/637) | T-RUNTIME-CATCH 运行质量+效率（原 B1+B2+B3）· 须 628 关卡 · 无章 |
| 已关前置 | [#627](https://github.com/juanwan99/pico/issues/627) | T-CI-UI-GATE 已合 `6e2adda…` · 不部 |
| 收口差人眼 | [#623](https://github.com/juanwan99/pico/issues/623) 已关 | 三波+#629 已部 tip `b713464…`；老师侧 PDF/HTML 为**执行回执**，总管未亲自登录复点 |
| 等业主配钥 | `SILICONFLOW_API_KEY` | ECS `.env`（compose 已留位）；有钥 #628 hybrid，无钥先纯全文诚实降级 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | CLAIM 材料等**业主** · 工程禁代签 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | KA-3 默认切流须业主书面授权 · 未执行 · **勿关** |
| 规划/讨论 | [#505](https://github.com/juanwan99/pico/issues/505) · [#530](https://github.com/juanwan99/pico/issues/530)（序1/序2 已并入 628/637） · [#498](https://github.com/juanwan99/pico/issues/498) · [#600](https://github.com/juanwan99/pico/issues/600) | 规划稿/指针 · **勿关 · 勿当本周执行** |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) · [#634](https://github.com/juanwan99/pico/issues/634) | controller-bot poll log · **现行总管交接** · 长期开（#573 作废仍勿关） |

```text
2026-08-23 已收口：#615 #613 #619 #620 #621 #622 #623 #624 #625 #627 #629 #630 #631 #632 #633 · #586 关闭不合（业主决定 · 分支保留）
现网 tip b713464… 已含：#623 三波 + #629 SSO 聊天 403
禁止误关：#316 #449 #498 #505 #530 #170 #475 #573 #600 #634
禁止把已 close 卡当活动主线
#573 作废不当现况（仍勿关，防旧窗当现役）
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
| 公网 tip | `GET /api/pico/tip` → 须 40 位实查（写窗 `b713464ca05cb54fc2c30309cf05dc8f3710a825`；main `ff2c6bca…` 故意不部） |
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
