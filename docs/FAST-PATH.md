# 快路径（BINDING · 砍流程税）

```
DOC: docs/FAST-PATH.md
STATUS: BINDING — 日常唯一默认节奏
UPDATED: 2026-08-01
OWNER_ORDER: 在必要安全下砍掉一切阻碍
AUTONOMOUS: docs/AUTONOMOUS-GOAL.md — 业主终验制已启用
```

## 一句话

**改 → CI 绿 → 合 → 窗1 装 tip → 窗4 点聊/停 → 三行回执。**  
能并刀并刀；能一个 PR 做完绝不拆五张卡。

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
| 窗4 对用户路径：login / 真聊 / 停 至少各一次（改动碰运行时/UI 时） | 防「合了但不能用」 |
| 禁 edu-cloud 写仓；禁 PROXY=1 进应用；禁 Plan B 换核 | 真源红线 |
| 禁宣称「已接入 Kimi Agent」除非有生产账本+授权证据 | 防假完成 |

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
| **窗2/3** | 一个主题一个分支/PR，CI 绿求合 | 不拆五张调查 |
| **合权/总管** | 绿档快合；黄扫关键路径 | 不叠第二审批戏 |
| **窗1** | `prod-update` tip；remote-health | 不装浏览器验聊 |
| **窗4** | 登录+聊+停；三行报告 | 不改码不部署 |
| **业主** | 目标与授权（KA canary / 切流 / 清库） | 少被技术假流程打扰 |

### 窗编号（钉死）

| 窗 | 职责 |
|----|------|
| **1** | 部署 |
| **2/3** | 写入（可并行） |
| **4** | 验证（已登录+视觉+操控网页） |

---

## 命令（部署 · 窗1）

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

## 编排（Kimi Agent）加速而不降安全

```text
仓内：能并的缺口并成少数大 PR（门禁/审计/safety 已并进 main 的继续用）
生产：tip 可勤装，flag 保持 0 + 名单空
放量：仅业主书面授权 canary（总闸+名单）后，窗4 出 runtime=kimi-agent 证据
默认切流：#170，另授权，禁止偷做
```

---

## 权威顺序

业主授权 > TRUTH-FREEZE 目标/禁项 > **本页节奏** > STATE-NOW 快照 > 聊天  
与本页冲突的「多卡仪式 / 总管八股」以本页为准废止。

---

## 单关键路径极速模式（BINDING · 2026-08-01 业主确认）

**主线只做 Kimi 真接。** 日常默认即本模式。

| 规则 | |
|------|--|
| 一目标一 PR | 代码+测试+必要观测一次收完 |
| 绿档 | CI 绿即合 |
| 黄档 | 仅一次 exact-SHA 审查 |
| 部署 | 窗1 **一次** |
| 验收 | 窗4 **一次** |
| 失败 | 关闸 + **一个**修复 PR |
| 禁止 | 流程文档轮转、准备性 Issue、3A/3B 微切片、重复草稿 PR |

### Kimi canary（须业主书面授权）

```text
1) 窗1：prod-update tip（flag 仍可先 OFF 装码）
2) 窗1：仅当已授权 → RUNTIME=1 + CANARY_MEMBERSHIP_IDS=单会员
3) recreate pico-api；health 核 SHA + runtime_enabled + canary_configured
4) 窗4：一次验完真 provider / runtime / 账本 / deny / cap / cancel
5) 失败：RUNTIME=0、名单空、recreate，基线 chat/stop
6) 通过后再议扩名单或 #170 默认切流；此前不宣称接入完成
```

**五条底线：** 单会员白名单 · 危险工具关 · 只经 AllowlistGateway · 限额/取消/审计 · exact SHA 可回滚。


