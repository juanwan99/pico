# Pico OneFlow（瘦身 · 绑定）

```text
DOC: docs/ONEFLOW.md
STATUS: BINDING v2.1 — 2026-08-23
EXEC: 2026-08-24 三刀 BINDING（卡面不改）
REPO: juanwan99/pico ONLY
ALIGN: edu-core TASK-DISPATCH v2（派发条 + 合同在 Issue）
NORTH: docs/DIRECTION-NOW.md §0-star（对标 WB · 办公核心 · 编程兼顾 · 禁焊死路径）
```

```text
执行三刀（开窗先看）
1. 证据贴 Issue 评论。禁止 docs PR 专贴截图。
2. 无 ECS / 不能 prod-update = 拒领。DONE 必须 curl tip = origin/main。
3. 过门 = 老师手。写控件清单 = 退回调查，禁开工。
现况: docs/STATE-NOW.md
```

> GitHub Flow + 生产认 SHA。不是 Git Flow。不是 315 填表。

## 0. 第一性原理

1. **用户看见的结果** 是唯一工作单元。
2. **GitHub 是唯一账本。** Issue / PR / SHA。聊天不算状态。
3. **生产只认 40 位 SHA。** `curl -fsS https://pico.aivia.asia/api/pico/tip`。
4. **证据选最便宜的真证据。** 能 API 就不开浏览器。视觉默认关。
5. **写入不自签过。** CI 红不合。

单人小改：分支 → PR → CI 绿 → 合。不强制开卡。

## 1. 主路径

```text
一句人话目标
  → 一张卡（四行）或直接 PR
  → 一分支一 PR
  → CI 绿
  → 合 main
  → 有差才 prod-update.sh 一次
  → live tip == origin/main
  → 回执五句
```

未 MERGED 不算做完。合了没部署 = 用户看不见。

## 2. 合同在 Issue，派发条在卡评

执行窗**每次新开、零记忆**。看不见总管聊天，找不到你没写进 Issue 的调查。

```text
总管调查 → 写入 Issue 标准任务卡（已锁事实 / IN / 验收）
         → stamp-ok
         → 派发条贴合同 Issue（## 派发）
         → 总管 spawn-executor（官方 API · 首条=派发条）；无钥则 `@cursor`
执行窗只认：派发条 + 合同 Issue
总管环：订 PR/CI + timer 读 ## CANDIDATE/DEPLOYED/DONE → tip-pin → CLEAR
         合了未部关卡=打回 OPEN · 总管不合不部
```

**Issue 合同**用标准任务卡体例（#627：锁定句 / 已锁事实 / IN / OUT / 验收 / CLAIM / 回写）。四行（结果 / 不准 / 过门 / 部署）是骨架，嵌在卡里，**禁止用四行短卡替代合同**——无状态窗会丢已锁事实。

**派发条** [`docs/templates/dispatch-slip.md`](./templates/dispatch-slip.md) 贴两处：合同 Issue `## 派发` + 执行窗首条。业主聊天可贴同一段，不当账本。禁止贴 Issue 全文。

缺任一则没派：Issue 未开 · 无 stamp-ok · 卡上无 `## 派发` · 条上无必读/坑名。

模板：`.github/ISSUE_TEMPLATE/` · `docs/templates/card-build.md` · `docs/templates/dispatch-slip.md`。指针：`docs/TASK-CARD-STANDARD.md`。

## 2b. 一张卡四行（骨架，不是派发形态）

```text
结果：老师在 pico.aivia.asia 能看见什么
不准：最多 5 条（必含：自签 PASS · 直推 main · ship-bff-web）
过门：最多 4 条人路径
部署：PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh
```

## 3. 角色（最小）

| 谁 | 做什么 | 禁止 |
|----|--------|------|
| 业主 | 目标；黄红争议；老师手过门；签 PASS | 当粘贴中继（终态） |
| 总管 | 调查写入 Issue；打章；`## 派发`；spawn-executor / `@cursor`；订约读回执；刷现况 | 自签；合 main；prod-update；代合代部；当执行窗写业务码 |
| 写入 | 改、测、PR、部、五句回执贴合同 | 自签 PASS；直推 main；写 edu-core 业务 |

## 4. 发布

```bash
cd /opt/pico
PICO_DEPLOY_SHA=<已合 main 的 40 位> bash scripts/prod-update.sh
curl -fsS https://pico.aivia.asia/api/pico/tip
```

`git_sha` 对不上 = 没上线。真源在 ECS `/opt/pico`，不是边缘 IP。

## 5. 不做

- 假装已有 GHCR 全自动发布
- 用聊天当账本
- 写入自审后直接合
- 合 main 不部署却声称用户已用上
- 把 edu 的 315 卡面抄进 pico
- 用四行短卡当已派（执行窗找不到已锁事实）
- 把调查留在总管聊天、不写进 Issue
- 对执行窗贴 Issue 全文，或合同上无 `## 派发`
- 总管自己当执行窗写业务码 / 合 main / prod-update
- 造 mailbox、ECS 常驻 Grok、与 GitHub 平行的进度总线
