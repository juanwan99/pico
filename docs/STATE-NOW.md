# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-24（业主开干 · 执行三刀）
仓: juanwan99/pico ONLY
在飞执行卡: 无
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签 · 仅业主（#449 / #316）
生产: curl -fsS https://pico.aivia.asia/api/pico/tip  （禁止把本页旧 SHA 当现网）
工作流: 卡面仍冻 · 执行三刀 BINDING
北极星: DIRECTION-NOW §0-star · 用法 = Grok · 禁定向猜任务
真源优先级: 本页 + #634 > 任何 HANDOFF-*.md > 聊天
juanwan99/oneflow: 不当真源（已 Archive 2026-08-24）
```

## 执行三刀（业主 2026-08-24 开干 · BINDING）

卡面 / 表单 / 315 **仍冻**。只改执行纪律。下一张产品卡必须遵守：

1. **证据禁止进 PR。** 过门截图、日志、硬刷帧只贴 **Issue 评论**。禁止 `docs(…): live 帧` 这种 PR。功能码 PR 可以有测，证据不进仓。
2. **无部署权拒领。** 执行窗不能 `PICO_DEPLOY_SHA=… bash /opt/pico/scripts/prod-update.sh` = 不 stamp、不派条。报 DONE 必须 `live SHA = origin/main`（curl tip）。合了未部 = 没完。禁止拆「完成部署」续轮 / T-*-DEBT。
3. **过门必须是老师手。** stamp 前过门是人能点的一句（看见 A 不是 B）。禁止第一张卡写 1px 轨、词表、选择器。写不清 → 先调查卡，禁开工。半过 → 同卡续。

失真（执行）= 证据 PR / 合了报 DONE / 过门写控件。总管打回。

## 冻结令（卡面 · 仍有效）

1. 禁止改卡模板、复活 315、新 `HANDOFF-NEW-WINDOW-*.md`。
2. **pico 在飞 = 无**（[#646](https://github.com/juanwan99/pico/issues/646) 已关）。同域第二张 `stamp-ok` = 废派。
3. **`juanwan99/oneflow` 不当真源（已 Archive）。**

失真（过程）= 改卡模板 / 复活 315 / 第二张 stamp-ok / 新交接当现况 / 本页「在飞」对不上 stamped 卡 / oneflow 仓当真源。

## 收口账（2026-08-24）

| 卡 | PR | 过门 | 判 |
|----|----|------|----|
| pico [#646](https://github.com/juanwan99/pico/issues/646) | **1 产品 PR** #648 | live `929aa44`：通知+「这是什么」无 Word；点名 Word 有件。不签 PASS | **干净** · KEEP + 先调查 |
| edu [#922](https://github.com/juanwan99/edu-core/issues/922) | **7 PR** #923–#929 | 业主 PASS `b6c56f2` | **脏** · 证据 PR + 合≠部 + 过门写控件 |

三刀就是冲着 #922 那 7 PR 去的。

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 当前活动主线

| 优先级 | Issue | 说明 |
|--------|-------|------|
| 在飞 | 无 | 下一张等业主「开卡」三句 · 派时执行三刀 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | 仅业主 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | 须业主书面 · **勿关** |
| 冻结钉 | [#634](https://github.com/juanwan99/pico/issues/634) | 冻结令 + 执行三刀入口 |
| 规划/讨论 | #505 #530 #498 #600 | **勿关 · 勿当本周执行** |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) | controller-bot · 长期开 |

```text
新总管只读本页 + curl tip。无在飞则讨论。
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
| 公网 tip | `GET /api/pico/tip` → 须 40 位实查 |
| 发布 | `PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh` |
| multi-step 默认 | **pi-true** |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` |
| 钉版 | `@mariozechner/pi-coding-agent@0.73.1` |
| 真核主机 | ECS `47.121.197.52`（`ssh ecs` · `/opt/pico` · 18765） |
| P4 出图 | **HOLD** |
| CLAIM-WB | **NO** |

## 错误记忆

- 禁止把已关 #646 当在飞
- 禁止证据 PR、合了未部报 DONE、过门写控件
- 禁止改卡模板 / 新交接 / oneflow 仓当真源
- 禁止 edu 串仓；禁止代签 CLAIM-WB YES
- 禁止把本页历史 SHA 当现网 tip
