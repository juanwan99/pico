# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。** 产品定义：[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)。编排唯一路径=开源 Kimi Agent 真接入；现状=过渡自研环（经 `run_agent_runtime` 默认进 `run_agent_loop`）；禁假称已接入；禁预埋 Plan B/其它运行时。**


```
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot · 覆盖聊天里冲突的进度/角色/SHA 口述
UPDATED: 2026-08-01
TRUTH_ORDER: 本页 SHA/门禁 < 更新的 GitHub PR 评论（DEPLOYED/TEST REPORT） < 代码 main tip
```

> **用途：** 执行窗上下文过长、记忆污染时，**先读本页 + AGENTS.md**，再读任务提示词。  
> **不要**用旧交接长文、旧 E1/E2/E3 自动心跳叙事、或总管过时百分比接管。

---

## 0. 产品一句话（正确）

Pico = **独立 AI 工作台底座**（对话 + Agent + 产物 + **唯一 AI 账本** + 模型 HTTPS）。  
壳 = **`apps/librechat`** → Pico API。  
**不是**网盘/教务 SaaS；**禁止**写 `edu-cloud`；计划法 MVP **v1.2 FIXED**（无授权不升 v1.3）。

终局分工：Pico = AI 过程真源；edu = 业务真源（对接后置）。

**目标校正（冻结）：**

| 层 | 选择 |
|----|------|
| 壳 | LibreChat（MIT） |
| 控制面 + AI 账本 | 仅 Pico |
| 编排 | **唯一目标 = 开源 Kimi Agent**；现状默认 = 过渡 `run_agent_loop` |
| 模型 | Kimi / Moonshot HTTPS 优先锁定 |
| 教师沙箱 | **不做**默认执行沙箱；学校隔离 = 数据/租户 |
| Plan B | **禁止**预埋 Pi/OpenCode/「可替换 harness 多运行时」 |

---

## 1. SHA（证据绑定）

| 面 | 完整 SHA | 含义 |
|----|----------|------|
| **main tip（写本页时）** | `868fbf4fa7d231a42ff97f4f49d89a95a8376590` | Merge #147 STATE-NOW 证据刷新；其父含 Merge #145 KA-2 |
| **生产应用** | `ddf269b704c7e4a13e9d02718c3dbab1db4d0b42` | #142 `## TEST REPORT` 报告并经总管采信（#128 重跑代理） |
| 差异 | tip − 生产 | main **ahead** 生产；含正本清源 docs + KA-0/1/2 **应用码**（flag 默认 OFF） |

**差异不是换核证据：** 生产仍跑 `ddf269b…`；`PICO_KIMI_AGENT_RUNTIME` 默认 `0`；默认执行核仍是
`run_agent_loop`（经 `run_agent_runtime`）。合 #145 **≠** 部署 **≠** 开 flag **≠** 已接入完成。

#142 是产品主路径 **FAIL** 证据（不是 PASS）：login PASS；chat FAIL（`400 status code (no body)`）；
retry 入口 PASS（未再次长跑）；stop FAIL（`cancel_requested` 后仍 `running`）；pico-dev 401 PASS。

**禁止再写：**「main = 生产」「#145 已部署/已换核」「KA-2 合并 = 已接入」
「当前 tip 仍是 `ff1dc7c…` / 生产仍是 `768d0bd…`（过期）」。

---

## 2. 角色与派发（现行）

| 角色 | 职责 |
|------|------|
| **总管（Grok）** | 规划、派可执行项、核 SHA/CI/部署/验证证据、审合黄档、不盲信自报 |
| **窗口 1 / 2 / 3** | 执行；**无可靠自动触发**；标准任务卡 + GitHub 回写 |
| 业主 | 产品目标；少问技术细节 |

**规则：**

1. 槽位名：**窗口 1、2、3**（旧 E1/E2/E3 自动心跳 **作废**；`## CLAIM E1` 仅历史噪音）。  
2. `docs/EXECUTION-QUEUE.md` 历史队列 ≠ 现行自动派工权威（见该文件顶栏 SUPERSEDED 说明）。  
3. 上下文默认 **KEEP**；仅任务写明 `CLEAR` 才清。  
4. 依赖未审完 → 不派下一步；能并行则并行（验证 ∥ 写入常可）。  
5. 写入窗 **不自判产品 PASS**；`DEPLOYED` ≠ 产品 PASS；`CI 绿` ≠ 产品 PASS。  
6. 结果必须写 GitHub；聊天「做完了」不算。  
7. HARD：只 `juanwan99/pico`；禁 PROXY=1；禁密钥；禁 edu-cloud。

---

## 3. 历史收口（新回归证据优先）

| 主题 | 证据锚点 | 勿做 |
|------|----------|------|
| 停止 → cancelled | 历史 VQ-008；**#142 新回归** | 看 #144；禁止旧 PASS 盖新 FAIL |
| 失败重跑入口 | #127/#128 + #142 retry 入口 PASS | 未再长跑 ≠ 全站重跑 PASS |
| Skill 目录 ADR | `ADR-SKILL-CATALOG` ACCEPTED A | 禁止第二套技能商店 |
| 3 日底座冲刺 | SPRINT-3DAY-PUSH COMPLETED | 勿当现行日任务 |

Skill 正确表述：产品目录 = **LibreChat Skills**；Pico = 策略 + 工具 fail-closed + Run 快照。

---

## 3.5 正本清源 / KA 进度

| 项 | 状态 |
|----|------|
| TRUTH-FREEZE v1.0 | 已合 |
| 污染清理 POLLUTION-SWEEP | 进行中（活动文档名实；#121 拒合） |
| KIMI-AGENT-GAP | 活动差距清单；**默认未归位**；KA-0/1/2 状态见表 |
| KA-0 | **#137 合** · 可装 pin + 入口探测 · 无真模型 hello |
| KA-1 | **#140 合** · 纯 mapper + 单测 · 当时未接线生产 |
| KA-2 | **#145 合** · flag-only Session · **默认 OFF** · 未部署换核 |
| STATE-NOW 证据刷新 | **#147 合**（#146） |
| Kimi Agent **生产真接** | **未完成** · 禁止宣称已接入 |
| #121 harness 可替换边界 | **拒合 / 关闭** · 与 O4 冲突 |

---

## 4. 未完成门禁（当前）

| 优先级 | 项 | 状态 |
|--------|-----|------|
| **P0 总门** | **#142 生产主路径烟测** | ACCEPT **FAIL**；保持 OPEN |
| **P0 · chat** | **#143 PROD-CHAT-400-DIAG** | OPEN；须 `## DIAG REPORT` |
| **P0 · stop** | **#144 PROD-STOP-STUCK-DIAG** | OPEN；须 `## DIAG REPORT` |
| 后置 | KA-3 默认切核 | **未授权**；不得因 #145 提前 |
| 后置 | 限时公网分享 / edu 真联 / 像素 | 方向或债；不插队 |

禁止用 CI、DEPLOYED、KA-2 合并覆盖 #142 两个生产失败。

---

## 5. 过时记忆黑名单（见到即丢弃）

- Live Preview 6014 / trycloudflare 为业主主路径  
- Mongo 误 pin 27017 当产品成功  
- 默认壳 = apps/web / nextchat / workbench  
- 「自动队列轮询即可触发三窗」/ E1E2E3 心跳即派工  
- 「独立 AI 主路径约 90%」类百分比  
- #123 = 生产部署实现（实际是队列文档）  
- main tip 与生产应用 SHA 混为一谈  
- **Harness #121 已合 / 可替换多运行时已冻结**  
- 总管沙箱 = 用户预览机 / 可直连生产改代码  
- KA-2 已合 = 生产已启用 Kimi Agent / 已接入完成  
- `PICO_KIMI_AGENT_RUNTIME` 默认为 1  
- #142 抽检完成 = 产品主路径 PASS  
- STATE-NOW 仍写 tip=`ff1dc7c…` 或生产=`768d0bd…` 为「当前」  

---

## 6. 读文档顺序（现行）

1. `docs/TRUTH-FREEZE.md`  
2. `docs/WHAT-IS-PICO.md`  
3. 本页 `docs/STATE-NOW.md`  
4. `docs/KIMI-AGENT-GAP.md` · `docs/POLLUTION-SWEEP.md`  
5. 根 `AGENTS.md` · `docs/ONEFLOW.md`  
6. 任务指定的 PR/Issue  
7. **不要**把 `docs/archive/**`、旧 HANDOFF、过期 DAY-TASK、**#121** 当现行权威  

---

## 7. 下一动作（总管）

1. 窗口 1 · #143 chat 400 · `## DIAG REPORT`  
2. 窗口 3 · #144 stop 卡住 · `## DIAG REPORT`  
3. 日用 FIX 仅在有诊断证据后派；KA-3 / 生产开 flag **另授权**  

生产基线：`ddf269b704c7e4a13e9d02718c3dbab1db4d0b42`。  
main 勿冒充生产。
