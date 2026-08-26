# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-26
仓: juanwan99/pico ONLY
── 现况三行（开窗先对；禁止凭记忆）──
在飞: 无
live: curl -fsS https://pico.aivia.asia/api/pico/tip
      → 590772fea8a79f044c49a4fc69f6ec759c382713 = origin/main
阻塞: 无 · 无在飞则讨论不开卡
────────────────────────────────────
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: #682 业主已签 · #449 / #316 仍仅业主 · CLAIM-WB 仍 NO
经验: docs/EXPERIENCE.md（唯一 · 按域）
工具: docs/TOOLING-CATALOG.md（派发只认 ID）
北极星: DIRECTION-NOW §0-star · 用法 = Grok
真源优先级: 本页三行 + #634 > 任何 HANDOFF-*.md > 聊天
juanwan99/oneflow: 不当真源（已 Archive）
```

## 执行纪律（BINDING）

卡面四行。**怎么跟业主说话不限。**

1. **证据禁止进 PR。** 只贴 Issue 评论。
2. **无部署权拒领。** DONE 必须 live SHA = origin/main。合了未部 = 没完。禁 `Closes` 部前关卡。
3. **过门必须是老师手。** 写 1px 轨/选择器 = 退回。
4. **1 卡 1 PR。** CI/测/部的修补走原 PR。同卡续只在业主说还差。
5. **聊天默认易失。** 约束下一窗的结论必须落 Issue 评论或本页/`EXPERIENCE`/`TOOLING-CATALOG`。
6. **合与部只归执行窗。** 总管不合 main、不 prod-update；P0 可调查/起候选 PR，合部仍交执行窗（经验 §10）。
7. **自循环。** 总线=合同 Issue（`## 派发`/`CANDIDATE`/`DEPLOYED`/五句）。起窗=`spawn-executor`，无钥=`@cursor`。订约读回执；不合不部；合了未部关卡打回。禁 mailbox / ECS 常驻。

失真 = 证据 PR / 合了报 DONE / 过门写控件 / 拆 PR / 凭聊天当真源。总管打回。

## 冻结令（卡面 · 仍有效至 2026-09-07）

1. 禁止复活 315、新 `HANDOFF-NEW-WINDOW-*.md`。
2. 同域第二张 `stamp-ok` = 废派。
3. **`juanwan99/oneflow` 不当真源（已 Archive）。**
4. **不改卡面四行形状**（#634）。现况三行可刷；不当知识库加长。

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

## 开窗顺序

```text
STATE-NOW（本页三行）→ EXPERIENCE（点名≤3）→ curl tip
→ 有 stamp-ok 才领 · 无在飞则讨论不开卡
```

## 当前活动主线

| 优先级 | Issue | 说明 |
|--------|-------|------|
| 已收口 | [#682](https://github.com/juanwan99/pico/issues/682) | A1 T-KB-ENGINE-ON · 业主 PASS · tip=`590772fe…` |
| 已收口 | [#671](https://github.com/juanwan99/pico/issues/671) | T-FILES-PLACE · 业主令收口 |
| 运维 | [#679](https://github.com/juanwan99/pico/pull/679) | Cloud Agent TS + ssh ecs · 待执行窗合 |
| 真源 docs | [#680](https://github.com/juanwan99/pico/pull/680) | 现况/经验/工具 · 待执行窗合 · 不部 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | 仅业主 · **勿关** |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | 须业主书面 · **勿关** |
| 冻结钉 | [#634](https://github.com/juanwan99/pico/issues/634) | 卡面冻到 9/7 · 可钉现况三行评论 |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) | controller-bot · 长期开 |

**不当现况：** `#646`（已关）· `#671`（已关）· `DAY-TASK-*` · 任何 HANDOFF 长文 · 聊天 SHA。
