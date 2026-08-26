# 任务卡格式（指针 · 不再贴 315）

```text
DOC: docs/TASK-CARD-STANDARD.md
STATUS: BINDING v2.2 — 2026-08-24
FROZEN 卡面 — 禁止改本文件形状、复活 315
EXEC 三刀 BINDING:
  证据贴 Issue 评论 · 无 ECS 拒领 · 过门=老师手 · DONE=curl tip=main
SUPERSEDES: 四行短卡当派发形态
真源: docs/ONEFLOW.md v2.1 · 现况: docs/STATE-NOW.md
模板: .github/ISSUE_TEMPLATE/ · docs/templates/card-build.md · docs/templates/dispatch-slip.md
经验: docs/MEMORY-RESET.md（不进卡面；派发条只点名坑）
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok · 禁定向猜任务
```

点 **New Issue** 选「执行卡」或贴 **标准任务卡**（#627 体例）。卡必须自含【已锁事实】【IN】【验收】——执行窗零记忆，总管聊天里的调查它看不见。

派给执行窗时：派发条贴合同 Issue（`## 派发`），总管再 `spawn-executor --issue N`；无钥则评 `@cursor`。模板 [`docs/templates/dispatch-slip.md`](./templates/dispatch-slip.md)。卡上无 `## 派发` = 没派。

## 卡面（Issue 合同）

标准任务卡体例（对齐 #627），骨架仍是四行：

```text
结果：老师在 pico.aivia.asia 能看见什么
不准：最多 5 条（必含：自签 PASS · 直推 main · ship-bff-web）
过门：最多 4 条人路径
部署：PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh
       没差写「不部」
```

禁止用只有这四行的短卡替代整张标准任务卡。

总管戳（卡顶两问 + stamp-ok，无则拒领）：

```text
同域在飞？ 无 / 本卡续 / #<n>
残债新卡？ 否
```

回执五句，禁超 15 行：

```text
CLAIM T-ID · 窗名 · DONE
PR：#
SHA：live = origin/main =
过门：T1 过/不过 · 证据
剩下：无
PASS：未签
```

## 从 315 留下的（纪律，不填表）

这些是旧卡真正有用的部分，写进门禁，不要再贴 S/G/E：

| 留下 | 怎么守 |
|------|--------|
| 一张结果一张卡 | 「结果」只能一句老师能看见的 |
| 残债同卡续 | 禁 `T-*-DEBT`；不过就在本卡评论续 |
| 改 + 测 + 部同一张 | 禁「码已合、本卡只部」另开 |
| GitHub 是合同 | Issue / PR / SHA；**派发条只做入口**；聊天不算状态 |
| 总管两问才能领 | 无 stamp-ok 拒领 |
| 执行窗零记忆 | 调查写进 Issue 已锁事实；派发条点名必读 + ≤3 坑 |
| 生产认 40 位 SHA | `curl -fsS https://pico.aivia.asia/api/pico/tip` |
| 合了没装 = 没做完 | live tip 对不上 origin/main 不算过 |
| 写入不自签 | `PASS：未签`；`CLAIM-WB-DEGREE-WEB: NO` |
| 同域一张在飞 | 两问第一句 |
| 视觉默认关 | 过门用 API/SHA；非业主点名不开浏览器 |

**故意不贴回卡面：** 工具 ID 清单、经验全文、S4 缓冲 30 分钟、F/T 大表。  
工具自己翻手册。本周坑在 [`MEMORY-RESET.md`](./MEMORY-RESET.md)。挡这张卡的坑，写进「不准」最多一条。

## 不要做

- 把本文件旧长表、`DAY-TASK-*.md`、已关 Issue 当现行格式
- 把 edu 的 315 卡面抄进 pico
- 经验写进 Issue 模板默认值
- 用四行短卡当已派
- 对执行窗贴 Issue 全文，或不贴派发条
- 把调查留在总管聊天
- **定向卡**：读正文猜任务、force_agent 自动挂交付、把「必须交文件」焊进 user prompt（北极星 DIRECTION-NOW §0-star）
- 问题没讨论清就开执行 PR（调查先写 Issue；无 stamp-ok 禁开工）
