# Pico OneFlow（瘦身 · 绑定）

```text
DOC: docs/ONEFLOW.md
STATUS: BINDING v2.4 — 2026-09-02
EXEC: 本窗合一 · GitHub 唯一真源 · 只有 origin/main 是生产线 · 卫生=对账
REPO: juanwan99/pico ONLY
NORTH: docs/DIRECTION-NOW.md §0-star v1.3（用法 = Grok · 能力并列 · 工作环境交成熟上游）
```

```text
开窗先看
1. curl tip。现网版本只认这一下。
2. 从 origin/main 开枝。旁支不准部。长分叉只移植。
3. CI 绿再 squash 合 main。产品有差才 prod-update。过门 = 公网看得见。
真源: GitHub Issue/PR/SHA/CI + 公网 tip。STATE-NOW 是索引。
```

> GitHub Flow。生产认 SHA。不是 Git Flow。不是填表。

## 0. 第一性原理

1. **用户看见的结果** 是唯一工作单元。
2. **GitHub 是唯一账本。** Issue / PR / SHA。聊天不算状态。
3. **生产只认 40 位 SHA。** `curl -fsS https://pico.aivia.asia/api/pico/tip`。
4. **证据选最便宜的真证据。** 能 API 就不开浏览器。视觉默认关。
5. **CI 红不合。** 绿档本窗合。黄/红另一双眼睛。CLAIM-WB 不代签。

单人小改：分支 → PR → CI 绿 → 合。不强制开卡。

## 1. 主路径

```text
一句人话目标（没对齐就先讨论）
  → 从 origin/main 开枝
  → 改 + 测
  → PR（一件事一张；小改可无卡）
  → CI 绿 → squash 合 main
  → 产品有差才 prod-update 一次
  → curl tip 确认 SHA 在 origin/main 上
  → 公网看得见再关
```

未合进 main 不算做完。合了没部署 = 用户看不见 = 没完。CI/API 200 不算过门。CLAIM-WB 仍只业主签。

## 2. 合同

有卡：事实写在 Issue。无卡：PR 说明即合同。不要 stamp-ok、派发条、CANDIDATE 标题当第二状态机。

禁 mailbox / Cursor 云 Task / 在 `/opt/pico` 改业务 / 旁支部 live / 整枝合长分叉。

## 3. 角色（最小）

| 谁 | 做什么 | 禁止 |
|----|--------|------|
| 业主 | 对齐需求；用产品；CLAIM-WB / 阶段成果包；抽检不对开新卡 | 盯合、盯部、当闹钟 |
| 本窗 | 改、测、PR、合、部、curl tip | CI 绿当过门；mailbox；在 /opt/pico 改业务；旁支部 live |

## 4. 发布

```bash
cd /opt/pico
PICO_DEPLOY_SHA=<已合 main 的 40 位> bash scripts/prod-update.sh
curl -fsS https://pico.aivia.asia/api/pico/tip
```

`git_sha` 对不上 = 没上线。生产输入是 `/opt/pico` 的 detached SHA，合同真源仍是 GitHub + 公网 tip。

## 5. 不做

- 假装已有 GHCR 全自动发布
- 用聊天当账本
- 绿档以外无第二双眼睛就合黄/红
- 合 main 不部署（业主看不见效果）
- 把 edu 的 315 卡面抄进 pico
- 把调查留在聊天、不写进 Issue
- 造 mailbox、把 ECS 磁盘当第二账本
- 在 `/opt/pico` 改业务或 `docker compose` 当发布
- 旁支部 live、整枝合长分叉、直推 main
- 再设主管/执行者日常编制
- stamp-ok / 派发条 / 收尾六步当日常门禁
