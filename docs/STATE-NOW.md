# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-09-01
仓: juanwan99/pico ONLY
── 现况三行（开窗先对；禁止凭记忆）──
在飞: 无
live: curl -fsS https://pico.aivia.asia/api/pico/tip
      → 产品 SHA `8912c11ef3f82daba778265ae9d4ce43a44dc69e` = origin/main（#848 已部）
      → docs-only 合入不 prod-update，产品 SHA 未变
阻塞: 无
白名单勿关: #316 #449 #170 #634 #475
────────────────────────────────
CLAIM-WB-DEGREE-WEB: YES（业主 2026-08-26 · #449/#316 OWNER DECISION @ 本 tip）
PRODUCT PASS: #682/#684/#686/#690/#694/#697 业主已签 · #701 夜间/来源条业主 pass · #703/#706/#707/#708/#709/#710 业主 PASS 收口 · #733 夜包业主 PASS @ tip `a6bc83df…` · #752 业主 PASS @ tip `0c7943ac…` · #740 业主 PASS @ tip `2e668686…` · #776 业主 PASS @ tip `812360f6…` · #780 业主 PASS @ tip `e9e032b3…` · #785 业主 PASS @ tip `9d14329c…` · #788 积分门脸已关 · #824 T-UI-C-POLISH 业主 PASS @ tip `af3e8ad0…` · #829 T-UNMAIM-DRAFT 主管 PASS @ tip `c4953f2e…` · #834 T-FOUNDATION-GATES 业主 PASS @ tip `6236489f…` · #811 T-RESIDENT-SHRINK 主管 PASS @ tip `e5f840ef…` · #836 T-USAGE-THROUGH-PI 主管 PASS @ tip `adaca179…` · #821/#806/#808/#809/#807/#810 业主 PASS 已关 · #794 业主 PASS 已关
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
3. **过门 = 公网能看见结果句。** 主管自签 PASS。业主抽检不对开新卡。写 1px 轨/选择器 = 退回。
4. **1 卡 1 PR。** CI/测/部的修补走原 PR。同卡续只在业主说还差。卡别拆太细：同层薄适配并一张。
5. **聊天默认易失。** 约束下一窗的结论必须落 Issue 评论或本页/`EXPERIENCE`/`TOOLING-CATALOG`。
6. **合与部默认本窗。** 执行者 = 业主正在说话的这扇 Grok 沙箱。禁 spawn 子 agent / Cursor 云 Task / ECS grok。
7. **自循环。** 总线=合同 Issue（`## 派发`/`CANDIDATE`/`DEPLOYED`/五句）。执行者=本窗 Grok 沙箱。ECS 只部（ssh-ecs）。禁 mailbox / 第二账本。合了未部关卡打回。

失真 = 证据 PR / 合了报 DONE / 过门写控件 / 拆 PR / 凭聊天当真源。总管打回。

## 冻结令（卡面 · 仍有效至 2026-09-07）

1. 禁止复活 315、新 `HANDOFF-NEW-WINDOW-*.md`。
2. 同域第二张 `stamp-ok` = 废派。
3. **`juanwan99/oneflow` 不当真源（已 Archive）。**
4. **不改卡面四行形状**（结果/不准/过门/部署）。现况三行可刷。
5. **流程以 EXPERIENCE §80–89 为准**（#634）：执行者=本窗 Grok 沙箱 · ECS 只部 · 主管闭环自签 PASS。旧「双沙箱额度切换 / Cursor 云 Task 执行者 / ECS grok 执行者」作废。

## 架构法律（BINDING）

**禁止自研 · 只做薄适配：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md)  
**能力加载纪律：** [`ADR-CAPABILITY-LOADING.md`](./ADR-CAPABILITY-LOADING.md)（少常驻 · Skill 先目录后全文 · 不当在飞）

## 开窗顺序

```text
STATE-NOW（本页三行）→ EXPERIENCE（点名≤3）→ curl tip
→ 三行≠tip 先刷三行 · 有 stamp-ok 才领 · 无在飞则讨论不开卡 · 无收尾不准派下一张
```

## 当前活动主线

| 优先级 | Issue | 说明 |
|--------|-------|------|
| 已收口 | [#686](https://github.com/juanwan99/pico/issues/686) | T-LONG-OFFICE 长任务办公 · 业主 PASS · tip=`dcb47c00…` |
| 已收口 | [#684](https://github.com/juanwan99/pico/issues/684) | T-KB-USABLE 库能用 · 业主 PASS · tip=`c8acc46b…` |
| 已收口 | [#682](https://github.com/juanwan99/pico/issues/682) | A1 T-KB-ENGINE-ON · 业主 PASS · tip=`590772fe…` |
| 已收口 | [#680](https://github.com/juanwan99/pico/pull/680) | 现况/经验/工具 · 已合 main |
| 已收口 | [#679](https://github.com/juanwan99/pico/pull/679) | Cloud Agent TS + ssh ecs · 已合 main |
| 已收口 | [#671](https://github.com/juanwan99/pico/issues/671) | T-FILES-PLACE · 业主令收口 |
| 产品签 | [#449](https://github.com/juanwan99/pico/issues/449) · [#316](https://github.com/juanwan99/pico/issues/316) | 业主 YES · **勿关** |
| 已收口 | [#690](https://github.com/juanwan99/pico/issues/690) | T-OFFICE-KERNEL 办公文档核 · 业主 PASS · tip=`0acf8f62…` |
| 已收口 | [#694](https://github.com/juanwan99/pico/issues/694) | T-OFFICE-COVER 办公文档覆盖 · 业主 PASS · tip=`18537f47…` |
| 已收口 | [#697](https://github.com/juanwan99/pico/issues/697) | T-HTML-PUBLIC HTML 公网页 + 收数 · 业主 PASS · tip=`837443f4…` |
| 已收口 | [#701](https://github.com/juanwan99/pico/pull/701) | 来源条对齐 + 夜间整页 · 业主 pass · tip=`88160b31…` |
| 已收口 | [#703](https://github.com/juanwan99/pico/issues/703) · [#704](https://github.com/juanwan99/pico/pull/704) | T-UNMASK-PI · 业主 PASS · tip 含于 `97e421c6…` |
| 已收口 | [#706](https://github.com/juanwan99/pico/issues/706) | 夜战母卡 · 业主 PASS · 四子卡已部 |
| 已收口 | [#707](https://github.com/juanwan99/pico/issues/707) · [#711](https://github.com/juanwan99/pico/pull/711) | T-VISION-SANDBOX · 业主 PASS · tip `97e421c6…` |
| 已收口 | [#708](https://github.com/juanwan99/pico/issues/708) · [#713](https://github.com/juanwan99/pico/pull/713) | T-VISION-IN-FILE · 业主 PASS · tip `97e421c6…` |
| 已收口 | [#709](https://github.com/juanwan99/pico/issues/709) · [#712](https://github.com/juanwan99/pico/pull/712) | T-PPT-IMAGE-IN-DECK · 业主 PASS · tip `97e421c6…` |
| 已收口 | [#710](https://github.com/juanwan99/pico/issues/710) · [#714](https://github.com/juanwan99/pico/pull/714) | T-PPT-SANDBOX-LIB · 业主 PASS · tip `97e421c6…` |
| 已收口 | [#733](https://github.com/juanwan99/pico/issues/733) | T-NIGHT-CORE-3 · 业主 PASS @ tip `a6bc83df…` |
| 已关 | [#752](https://github.com/juanwan99/pico/issues/752) | T-OFFICE-THICK · 业主 PASS @ tip `0c7943ac…` · 卫生关 |
| 已关 | [#740](https://github.com/juanwan99/pico/issues/740) | T-PPT-CONTRACT · 业主 PASS @ tip `2e668686…` · 卫生关 |
| 已收口 | [#776](https://github.com/juanwan99/pico/issues/776) · [#775](https://github.com/juanwan99/pico/pull/775) | T-SANDBOX-OFFICE-BOX · 业主 PASS @ tip `812360f6…` |
| 已收口 | [#780](https://github.com/juanwan99/pico/issues/780) · [#781](https://github.com/juanwan99/pico/pull/781) · [#782](https://github.com/juanwan99/pico/pull/782) | T-HTML-OFFLINE-ENGINE · 业主 PASS @ tip `e9e032b3…` |
| 已收口 | [#785](https://github.com/juanwan99/pico/issues/785) · [#786](https://github.com/juanwan99/pico/pull/786) | T-UI-CHROME · 业主 PASS @ tip `9d14329c…` |
| 已收口 | [#788](https://github.com/juanwan99/pico/issues/788) | T-POINTS-FACE 对话积分门脸 · 业主关 |
| 已收口 | [#824](https://github.com/juanwan99/pico/issues/824) · [#825](https://github.com/juanwan99/pico/pull/825) · [#826](https://github.com/juanwan99/pico/pull/826) · [#827](https://github.com/juanwan99/pico/pull/827) | T-UI-C-POLISH 方案C · 业主 PASS @ tip `af3e8ad0…` |
| 已收口 | [#829](https://github.com/juanwan99/pico/issues/829) · [#830](https://github.com/juanwan99/pico/pull/830) | T-UNMAIM-DRAFT 别残模型稿 · 主管 PASS @ tip `c4953f2e…` |
| 已收口 | [#834](https://github.com/juanwan99/pico/issues/834) · [#833](https://github.com/juanwan99/pico/pull/833) | T-FOUNDATION-GATES 假绿门补基础 · 业主 PASS @ tip `6236489f…` |
| 规划 | [#805](https://github.com/juanwan99/pico/issues/805) | 活核+记忆+问清+计划+过程可见 · 六刀指针 · 不派 |
| 规划 | [#744](https://github.com/juanwan99/pico/issues/744) | 北极星升 v1.3 · DIRECTION-NOW 仍 v1.2 · 留开 |
| 已关 | [#806](https://github.com/juanwan99/pico/issues/806) | T-PI-KERNEL-BUMP 0.84.4 · 业主 PASS 卫生关 |
| 已关 | [#810](https://github.com/juanwan99/pico/issues/810) | T-PROCESS-VISIBLE · 业主 PASS 卫生关 |
| 已关 | [#807](https://github.com/juanwan99/pico/issues/807) | T-MEMORY-UPSTREAM · 业主 PASS 卫生关 |
| 已关 | [#809](https://github.com/juanwan99/pico/issues/809) | T-PLAN-WIRE · 业主 PASS 卫生关 |
| 已关 | [#808](https://github.com/juanwan99/pico/issues/808) | T-ASK-USER · 业主 PASS 卫生关 |
| 已关 | [#821](https://github.com/juanwan99/pico/issues/821) | T-P0-ASK-IN-MAIN · 业主 PASS 卫生关 |
| 已收口 | [#811](https://github.com/juanwan99/pico/issues/811) · [#835](https://github.com/juanwan99/pico/pull/835) | T-RESIDENT-SHRINK 收常驻 · 主管 PASS @ tip `e5f840ef…` |
| 已收口 | [#836](https://github.com/juanwan99/pico/issues/836) · [#837](https://github.com/juanwan99/pico/pull/837) | T-USAGE-THROUGH-PI 真 Pi 用量进唯一账本 · 主管 PASS @ tip `adaca179…` |
| 已收口 | [#838](https://github.com/juanwan99/pico/issues/838) · [#839](https://github.com/juanwan99/pico/pull/839) | T-POINTS-THIS-TURN 精确 token 列 + 加权换算 · 业主令先收 · 已部 tip `c4390454…` |
| 已关 | [#840](https://github.com/juanwan99/pico/issues/840) · [#841](https://github.com/juanwan99/pico/pull/841) | T-ASK-HONEST 等选不假跑 · 已部 tip `c7b6a6a5…` · 卫生关 |
| 已收口 | [#842](https://github.com/juanwan99/pico/issues/842) · [#843](https://github.com/juanwan99/pico/pull/843) | T-PAGE-COLLECT-LAND land 带 @ 材料 id · 主管 PASS @ tip `d206b70c…` |
| 已收口 | [#844](https://github.com/juanwan99/pico/issues/844) · [#845](https://github.com/juanwan99/pico/pull/845) | T-SCHOOL-FIELDS-SPLIT 聊天学校材料左管右订 · 主管 PASS @ tip `16d0c7fa…` |
| 已收口 | [#846](https://github.com/juanwan99/pico/issues/846) · [#847](https://github.com/juanwan99/pico/pull/847) | T-ASK-FAIL-PICO-FACE 问选超时失败 · 身份只叫 Pico · 主管 PASS @ tip `cbc0000a…` |
| 已关 | [#848](https://github.com/juanwan99/pico/issues/848) | T-HTML-PICO-CSS · 已部 tip `8912c11e…` |
| 已关 | [#748](https://github.com/juanwan99/pico/issues/748) | T-LOAD-HONEST · D 过 · 产品尺未过 · 不续债卫生关 |
| 已关 | [#794](https://github.com/juanwan99/pico/issues/794) | T-SUB2API-FACE · 业主 PASS @ `c2a2e439…` |
| 挂起 | [#778](https://github.com/juanwan99/pico/issues/778) | 出图链 · 不在三行 · 要做另开 |
| 挂起 | [#850](https://github.com/juanwan99/pico/issues/850) | 二进制不进脑 · 业主令先停 · CI 红未合 |
| 挂起 | 自研记忆 OS | 禁 · 文件型上游 #807 已部 |
| HOLD | [#170](https://github.com/juanwan99/pico/issues/170) | 须业主书面 · **勿关** |
| 冻结钉 | [#634](https://github.com/juanwan99/pico/issues/634) | 卡面四行冻到 9/7 · 流程 EXPERIENCE §80–89 |
| 运行线程 | [#475](https://github.com/juanwan99/pico/issues/475) | controller-bot · 长期开 |

**不当现况：** `#646`（已关）· `#671`（已关）· `DAY-TASK-*` · 任何 HANDOFF 长文 · 聊天 SHA。
