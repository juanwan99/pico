# STATE-NOW · Pico（本窗真源）

```text
FROZEN until 2026-09-07 · 开过程卡四字可拆
DATE: 2026-08-24（#646/#922 收口后）
仓: juanwan99/pico ONLY
在飞执行卡: 无
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 仅业主（#449 / #316）
生产: curl -fsS https://pico.aivia.asia/api/pico/tip  （禁止把本页旧 SHA 当现网）
工作流: 形状仍冻 · 无「开过程卡」四字则禁止改模板
北极星: DIRECTION-NOW §0-star · 用法 = Grok · 禁定向猜任务
真源优先级: 本页 + #634 冻结令 > 任何 HANDOFF-*.md > 聊天
juanwan99/oneflow: 不当真源（已 Archive 2026-08-24）
```

## 冻结令（业主 2026-08-24 · 本窗落账）

1. **卡面冻结** 至 2026-09-07，或业主说「开过程卡」。禁止复活 315。禁止新 `HANDOFF-NEW-WINDOW-*.md`。
2. **pico 在飞 = 无**（[#646](https://github.com/juanwan99/pico/issues/646) 已关）。同域第二张执行卡带 `stamp-ok` = 废派。
3. **`juanwan99/oneflow` 不当真源（已 Archive）**。

失真 = 改卡模板 / 复活 315 / 同域第二张 `stamp-ok` / 新交接当现况 / 本页「在飞」对不上 stamped 卡 / oneflow 仓当真源。

## 收口账（2026-08-24）

| 卡 | PR | 过门 | 判 |
|----|----|------|----|
| pico [#646](https://github.com/juanwan99/pico/issues/646) T-GROK-PATH | **1 产品 PR** #648（同 PR 一修）+ 北极星文档 #647 | live `929aa44`：通知+「这是什么」无 Word；点名 Word 有件。不签 PASS | **干净** · 先调查再 stamp 对了 |
| edu [#922](https://github.com/juanwan99/edu-core/issues/922) T-FIELD-SHEET-SEE | **7 PR** #923–#929 · 三轮本卡续 | 业主 PASS `b6c56f2` | **脏** · 过门写控件不是手感；脚本代替真人；合≠部 |

下一刀过程（若开卡）打 **过门+已部**，不打卡面。

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线

| 优先级 | Issue | 说明 |
|--------|-------|------|
| 在飞 | 无 | 下一张等业主「开卡」三句 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | 仅业主 · 工程禁代签 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | 须业主书面 · **勿关** |
| 冻结钉 | [#634](https://github.com/juanwan99/pico/issues/634) | 冻结令入口 |
| 规划/讨论 | #505 #530 #498 #600 | **勿关 · 勿当本周执行** |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) | controller-bot · 长期开 |

```text
新总管只读本页 + curl tip。无在飞则讨论，不开第二张。
禁止误关：#316 #449 #498 #505 #530 #170 #475 #600 #634
```

## 业主方向（最新 BINDING）

见 **[docs/DIRECTION-NOW.md](./DIRECTION-NOW.md)**。

```text
用法：Grok（通用 LLM · 挂载才办事 · 系统≠人话）
目标：Web 上对标 WorkBuddy 的办事能力
方案：Pico 整车 + 真 Pi + DeepSeek
不做：Dify 门脸 · 场景卷对标 · 双核 · MCP/Skill/连接器铺开 · 定向猜任务
CLAIM-WB-DEGREE-WEB: NO
```

## 工程快照

| 项 | 值 |
|----|-----|
| 公网 tip | `GET /api/pico/tip` → 须 40 位实查 · 禁止抄本页历史 SHA |
| 发布 | `PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh` |
| multi-step 默认 | **pi-true** |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| 钉版 | `@mariozechner/pi-coding-agent@0.73.1` |
| 真核主机 | ECS `47.121.197.52`（`ssh ecs` · `/opt/pico` · 18765） |
| P4 出图 | **HOLD** · 禁当交件 |
| CLAIM-WB | **NO** |

## 错误记忆

- 禁止把已关 #646 当在飞
- 禁止把 #627/#628 / 旧交接当现况
- 禁止过程 PR（无「开过程卡」）、新交接、oneflow 仓当真源
- 禁止 edu 串仓；禁止代签 CLAIM-WB YES
- 禁止把本页历史 SHA 当现网 tip
