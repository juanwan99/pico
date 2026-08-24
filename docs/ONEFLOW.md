# Pico OneFlow（瘦身 · 绑定）

```text
DOC: docs/ONEFLOW.md
STATUS: BINDING v2.1 — 2026-08-23
REPO: juanwan99/pico ONLY
ALIGN: edu-core TASK-DISPATCH v2（派发条 + 合同在 Issue）
NORTH: docs/DIRECTION-NOW.md §0-star（用法 = Grok · 禁定向猜任务）
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

## 2. 合同在 Issue，派发条在对话

执行窗**每次新开、零记忆**。看不见总管聊天，找不到你没写进 Issue 的调查。

```text
总管调查 → 写入 Issue 标准任务卡（已锁事实 / IN / 验收）
         → stamp-ok
         → 对执行窗的对话只贴派发条
执行窗只认：派发条 + 合同 Issue
```

**Issue 合同**用标准任务卡体例（#627：锁定句 / 已锁事实 / IN / OUT / 验收 / CLAIM / 回写）。四行（结果 / 不准 / 过门 / 部署）是骨架，嵌在卡里，**禁止用四行短卡替代合同**——无状态窗会丢已锁事实。

**对话只贴** [`docs/templates/dispatch-slip.md`](./templates/dispatch-slip.md)：合同链接 + 一句话 + 禁止 + **必读手册点名** + **最多 3 个坑名** + 回执五句。禁止贴 Issue 全文。

缺任一则没派：Issue 未开 · 无 stamp-ok · 没贴派发条 · 条上无必读/坑名。

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
| 业主 | 目标；签 PASS | 当信使 |
| 总管 | 调查写入 Issue；打章；对话只贴派发条；核 SHA | 自签；当执行窗写业务码；把调查留在聊天 |
| 写入 | 改、测、PR、部、五句回执 | 自签 PASS；直推 main；写 edu-core 业务 |

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
- 对执行窗贴 Issue 全文，或不贴派发条
- 总管自己当执行窗写业务码
