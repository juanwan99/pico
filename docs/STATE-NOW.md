# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-23
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 等业主 OWNER DECISION（#449）
公网 tip（派卡时）: 78441483720f4e82de1c48a71838a3a49b07daec
main tip（派卡时 · 待部）: 5e2de87a086b931ce568373273d12c5ee95952e6
  · 开工必 curl 实查：curl -fsS https://pico.aivia.asia/api/pico/tip
活动主线: 收口（#621 部一次 + 复验 #620/#615/#613 后关卡）
工作流: OneFlow v2（#619 已合）— 四行卡 · 禁 315 填表
```

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线（收口 · 2026-08-23）

| 优先级 | Issue / PR | 说明 |
|--------|-------|------|
| **P0 进行中** | [#621](https://github.com/juanwan99/pico/issues/621) | T-CLOSEOUT-VERIFY-0823：部一次 tip `5e2de87a…` + 人路径复验三卡后关 #615/#613 |
| 已合待部 | [#620](https://github.com/juanwan99/pico/pull/620) | T-ARTIFACT-VISIBILITY：PDF 预览 + 生成 HTML 落老师盘 + 主栏下载条（独立审查 PASS） |
| 码在现网 · 等复验关卡 | [#615](https://github.com/juanwan99/pico/issues/615) | T-AGENT-PLAIN-V1 十轮复杂任务（审查「倾向过」·差独立复验） |
| 码在现网 · 等复验关卡 | [#613](https://github.com/juanwan99/pico/issues/613) | T-AGENT-FACE-V1 跑时中文进度（审查「半过」·差 UI 复验） |
| 等业主二选一 | [#586](https://github.com/juanwan99/pico/pull/586) | Grok identity bridge（红档 auth · 技术审查 PASS · 合/关归业主） |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | CLAIM 材料等**业主** · 工程禁代签 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | KA-3 默认切流须业主书面授权 · 未执行 · **勿关** |
| 规划/讨论 | [#505](https://github.com/juanwan99/pico/issues/505) · [#530](https://github.com/juanwan99/pico/issues/530) · [#498](https://github.com/juanwan99/pico/issues/498) · [#600](https://github.com/juanwan99/pico/issues/600) | 规划稿/讨论稿/指针 · **勿关 · 非执行主线** |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) · [#573](https://github.com/juanwan99/pico/issues/573) | controller-bot poll log · 总管交接 · 长期开 |

```text
已装功能到现网 tip 78441483… ：
  #613 跑时中文进度 · #615 十轮收尾+藏口令+上传进 Agent 可读盘（#616/#617/#618）
已合未部（在 main tip 5e2de87a…）：#620 三修 + OneFlow v2 文档
禁止误关：#316 #449 #498 #505 #530 #170 #475 #573 #600
禁止把已 close 卡当活动主线（#468 #470 #476 #479 #474 #513 等）
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
