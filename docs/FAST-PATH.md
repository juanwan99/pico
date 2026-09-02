# 快路径（BINDING · 砍流程税）

```
DOC: docs/FAST-PATH.md
STATUS: BINDING — 技术步骤节奏（装 tip / 点聊）
ORG: docs/STAGE-PACKAGE-MODE.md — **本窗合一**；本文步骤由同一窗串行
MEMORY: docs/MEMORY-RESET.md — 废「必须多窗并行派工」
UPDATED: 2026-08-06
OWNER_ORDER: 在必要安全下砍掉一切阻碍
AUTONOMOUS: docs/AUTONOMOUS-GOAL.md — 成功门禁 A–I
STAGE_PACKAGE: docs/STAGE-PACKAGE-MODE.md — BINDING 单窗阶段包
```

## 一句话

**改 → CI 绿 → 合 → 装 tip → 点聊/停 → 三行回执。**  
**同一执行窗串行完成**（不默认拆窗1/2/4 三张卡）。能并刀并刀；能一个 PR 做完绝不拆五张卡。

---

---

## KEEP · 必要安全（不可砍）

| 门禁 | 为什么留 |
|------|----------|
| 密钥 / JWT / `.env` 不进 GitHub、不进 Issue | 泄露即事故 |
| 生产 `PICO_KIMI_AGENT_RUNTIME` 默认 **OFF**；canary 名单默认 **空** | 防全量误切 Agent |
| **未业主书面授权** 不得生产开 flag / 默认切 KA-3 / 清 zombie DB | 授权边界 |
| 工具 **AllowlistGateway**；危险 host 工具关断证明 | 学校场景底线 |
| `prod-update` **exact SHA** + health.git_sha 对齐 | 防假部署 |
| CI 绿再合 main（lint/test） | 防直接推坏 main |
| GitHub 只 squash；合完自动删头枝 | 防整枝合、防死枝当在飞。仓库设置，不另做清理器 |
| PR/commit 不写 Closes / Fixes / close #n | GitHub 会关 Issue；「Do not close #n」也会关。过门后手关 |
| 窗4 对用户路径：login / 真聊 / 停 至少各一次（改动碰运行时/UI 时） | 防「合了但不能用」 |
| 禁 edu-cloud 写仓；禁 PROXY=1 进应用；禁 Plan B 换核 | 真源红线 |
| 禁宣称「WB 程度 / CLAIM-WB-DEGREE-WEB」除非六条+GitHub 证据 | 防假完成 |
| 禁宣称默认核仍是 Kimi（产品叙事） | 默认 = Pi + DeepSeek |

除此以外的「流程」默认视为 **可砍税**。

---

## CUT · 已砍 / 禁止再搞（阻碍速度）

| 砍掉 | 说明 |
|------|------|
| 自动 E1 队列当派工权威 | SUPERSEDED |
| 同一功能默认拆：调查卡+写入卡+部署卡+烟测卡+视觉卡+文档卡 | **禁止**；最多「写一 PR + 装一次 + 点一次」 |
| KA 再拆 3A/3B/3C… 每缺口一张 Issue 等一轮 | **禁止**；同主题 **一个 PR 打尽** |
| 总管每刀必「深度审查长文」 | 仅黄/红/换核/授权变更才长审；绿档 CI+扫一眼合 |
| 无登录态的窗1 硬跑 chat/stop | 必 BLOCKED，纯浪费 |
| 为清理而写的第三套 CONTROLLER OS / RACI / 状态机 | 禁止 |
| 文档轮转代替用户价值 | 禁止用长文冒充进度 |
| 未授权生产开 flag「为了快」 | **不是快，是炸** |

**PR 本身不砍。** 慢的是「碎 PR + 等人贴卡」，不是「有一个 PR」。

---

## 默认动作（人）

| 谁 | 做什么 | 不做 |
|----|--------|------|
| **本窗** | 写 PR → CI → 合 → prod-update → 登录聊/停 → 收工对账 | 不拆多窗；不设主管/执行者编制 |
| **业主** | 目标与阶段成果包验收；CLAIM-WB | 少被技术假流程打扰 |
| **黄/红审** | 另一双眼睛、exact SHA（非常设岗位） | 不日常碎派 |

### 职责别名（非并行编制 · 本窗合一）

| 旧称 | 职责 | 谁做 |
|------|------|------|
| 窗2/3 | 写入 | **本窗** |
| 窗1 | 部署 | **本窗** |
| 窗4 | 验证 | **本窗** |
| 主管/执行者 | 开卡/合/部/卫生 | **本窗**（编制已废） |

历史多窗表 **SUPERSEDED** 为日常编制。见 [MEMORY-RESET.md](./MEMORY-RESET.md)。

---

## 命令（部署 · SOLO）

```bash
# /opt/pico 与 .git 属部署用户（非 root）
git fetch origin main
TIP=$(git rev-parse origin/main)
PICO_DEPLOY_SHA=$TIP bash scripts/prod-update.sh
# 跳板：bash scripts/remote-health.sh
```

## 回执（最少）

```text
SHA: <health.git_sha>
chat: OK/FAIL
stop: OK/FAIL
```

有 Issue 就贴评论；**不要**为回执再开新流程 Issue。

---

## 编排（Pi + DeepSeek）加速而不降安全

```text
仓内：能并的缺口并成少数大 PR；默认核 Pi（#309）
生产：tip 勤装；PICO_PI_AGENT_RUNTIME=1；DEEPSEEK 实钥（密码器）
验收：SOLO 登录开放域当场题 + stop；health default_runtime=pi-agent
禁：Kimi 主叙事假绿 · 场景卷冒充 CLAIM-WB-DEGREE-WEB · 多窗碎卡
```

---

## 权威顺序

业主授权 > TRUTH-FREEZE 目标/禁项 > AGENTS 文首工作法 > **本页节奏** > STATE-NOW 索引 > 聊天  
与本页冲突的「多卡仪式 / 主管执行者八股」以本页为准废止。

---

## 单关键路径极速模式（BINDING · 2026-08-01 业主确认）

**主线：Pi + DeepSeek 真接 + 单窗 SOLO。** 日常默认即本模式。

| 规则 | |
|------|--|
| 一目标一 PR | 代码+测试+必要观测一次收完 |
| 绿档 | CI 绿即合 |
| 黄档 | 仅一次 exact-SHA 审查 |
| 部署 | 窗1 **一次** |
| 验收 | 窗4 **一次** |
| 失败 | 关闸 + **一个**修复 PR |
| 禁止 | 流程文档轮转、准备性 Issue、3A/3B 微切片、重复草稿 PR |

### 遗产：Kimi canary（仅回滚 · 非产品主路径）

```text
1) 窗1：prod-update tip（flag 仍可先 OFF 装码）
2) 窗1：仅当已授权 → RUNTIME=1 + CANARY_MEMBERSHIP_IDS=单会员
3) recreate pico-api；health 核 SHA + runtime_enabled + canary_configured
4) 窗4：一次验完真 provider / runtime / 账本 / deny / cap / cancel
5) 失败：RUNTIME=0、名单空、recreate，基线 chat/stop
6) 通过后再议扩名单或 #170 默认切流；此前不宣称接入完成
```

**五条底线：** 单会员白名单 · 危险工具关 · 只经 AllowlistGateway · 限额/取消/审计 · exact SHA 可回滚。


