# Pico OneFlow（瘦身 · 绑定）

```text
DOC: docs/ONEFLOW.md
STATUS: BINDING v2.2 — 2026-08-31
EXEC: 2026-08-31 收成：执行者=本窗 Grok 沙箱 · ECS 只部 · 主管闭环 PASS
REPO: juanwan99/pico ONLY
ALIGN: edu-core TASK-DISPATCH v2（派发条 + 合同在 Issue）
NORTH: docs/DIRECTION-NOW.md §0-star（用法 = Grok · 禁定向猜任务）
```

```text
执行三刀（开窗先看）
1. 证据贴 Issue 评论。禁止 docs PR 专贴截图。
2. 无 ECS SSH / 不能 prod-update = 拒领部。DONE 必须 curl tip = origin/main。
3. 过门 = 公网能看见结果句。主管自签 PASS。写控件清单 = 退回。
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
  → 和业主对齐（没对齐不开卡）
  → 一张卡（四行；同层薄适配并一张，别拆太细）或直接 PR
  → 一分支一 PR
  → CI 绿
  → 合 main（本窗）
  → 有差才 prod-update.sh 一次（ECS 只部）
  → live tip == origin/main
  → 回执五句
  → 主管：结果句公网可见则自签 PASS 关；CI/API 不算。业主抽检不对开新卡
```

未 MERGED 不算做完。合了没部署 = 用户看不见。CI/API 200 不算过门。CLAIM-WB / 全球 PASS 仍只业主签。

## 2. 合同在 Issue，派发条在卡评

执行窗**切到新 Grok 窗才零记忆**。本窗不零记忆。钉评 + 合同 Issue 是跨窗正源。

```text
总管调查 → 写入 Issue 标准任务卡（已锁事实 / IN / 验收）
         → stamp-ok（需求已对齐）
         → 本窗 grok-sandbox-exec（改/测/PR/合/部）
总管环：自驱动盯 CANDIDATE/CI → 合 → 部 → tip-pin → 自签 PASS
         合了未部关卡=打回 OPEN
         ECS 只部 · 禁 ECS grok / Cursor 云 Task / spawn-executor
```

**Issue 合同**用标准任务卡体例（#627：锁定句 / 已锁事实 / IN / OUT / 验收 / CLAIM / 回写）。四行（结果 / 不准 / 过门 / 部署）是骨架，嵌在卡里，**禁止用四行短卡替代合同**——无状态窗会丢已锁事实。

**派发条** [`docs/templates/dispatch-slip.md`](./templates/dispatch-slip.md) 贴两处：合同 Issue `## 派发` + 执行窗首条。业主聊天可贴同一段，不当账本。禁止贴 Issue 全文。

缺合同或无 stamp-ok 则没派。本窗执行不要求另起 spawn。

模板：`.github/ISSUE_TEMPLATE/` · `docs/templates/card-build.md` · `docs/templates/dispatch-slip.md`。指针：`docs/TASK-CARD-STANDARD.md`。

## 2b. 一张卡四行（骨架，不是派发形态）

```text
结果：老师在 pico.aivia.asia 能看见什么
不准：最多 5 条（必含：执行窗关卡 · 直推 main · ship-bff-web）
过门：最多 4 条人路径
部署：PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh
```

## 3. 角色（最小）

| 谁 | 做什么 | 禁止 |
|----|--------|------|
| 业主 | 对齐需求；用产品；PASS 后抽检；不对开新卡 | 盯合、盯部、当执行窗闹钟 |
| 主管 / 执行者 | 同一扇 Grok 沙箱：对齐后开卡；改、测、PR、部、tip-pin；结果可见则自签 PASS | 没对齐就 stamp；CI 绿当 PASS；请业主签卡 PASS；spawn 空转；Cursor 云 Task；ECS grok；mailbox |

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
- 造 mailbox、把 ECS Grok 当第二账本、与 GitHub 平行的进度总线
