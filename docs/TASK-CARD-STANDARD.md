# 任务卡格式（指针 · 不再贴 315）

```text
DOC: docs/TASK-CARD-STANDARD.md
STATUS: BINDING v2 — 2026-08-23
SUPERSEDES: 本文件旧长表（CLAIM/BASE/PRODUCT 头 + IN/OUT 填表）
真源: docs/ONEFLOW.md
模板: .github/ISSUE_TEMPLATE/ · docs/templates/card-build.md
经验: docs/MEMORY-RESET.md（不进卡面）
```

点 **New Issue** 选「执行卡」或「调查卡」。卡顶有「开工先读」三份链接。没读手册就填卡 = 拒领。不要从聊天里发明第三套格式。

## 卡面只四行

```text
结果：老师在 pico.aivia.asia 能看见什么
不准：最多 5 条（必含：自签 PASS · 直推 main · ship-bff-web）
过门：最多 4 条人路径
部署：PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh
       没差写「不部」
```

总管戳（卡顶两问，无则拒领）：

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
| GitHub 是合同 | Issue / PR / SHA；聊天不算状态 |
| 总管两问才能领 | 无 stamp-ok 拒领 |
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
