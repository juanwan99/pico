# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。** 产品定义：[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)。编排唯一路径=开源 Kimi Agent 真接入；现状=过渡自研环；禁假称已接入；禁预埋 Plan B/其它运行时。**


```
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot · 覆盖聊天里冲突的进度/角色/SHA 口述
UPDATED: 2026-08-01
TRUTH_ORDER: 本页 SHA/门禁 < 更新的 GitHub PR 评论（DEPLOYED/TEST REPORT） < 代码
```

> **用途：** 执行窗上下文过长、记忆污染时，**先读本页 + AGENTS.md**，再读任务提示词。  
> **不要**用旧交接长文、旧 E1/E2/E3 自动心跳叙事、或总管过时百分比接管。

---

## 0. 产品一句话（正确）

Pico = **独立 AI 工作台底座**（对话 + Agent + 产物 + **唯一 AI 账本** + 模型 HTTPS）。  
壳 = **`apps/librechat`** → Pico API。  
**不是**网盘/教务 SaaS；**禁止**写 `edu-cloud`；计划法 MVP **v1.2 FIXED**（无授权不升 v1.3）。

终局分工：Pico = AI 过程真源；edu = 业务真源（对接后置）。

---

## 1. SHA（业主确认 · 绑定）

| 面 | 完整 SHA | 含义 |
|----|----------|------|
| **main tip** | `fd66ce23991c963090d7be07faa594a3737942ed` | Merge #145；含 KA-0 / KA-1 / KA-2 |
| **生产应用** | `ddf269b704c7e4a13e9d02718c3dbab1db4d0b42` | #142 `## TEST REPORT` 报告并经总管采信的生产应用 SHA |
| 差异 | tip − 生产 | main **ahead 20 commits**；含正本清源 docs、KA-0/1 骨架及 KA-2 默认关闭的应用代码 |

上述差异**不是**生产换核证据：#145 没有部署，生产仍运行 `ddf269b…`；KA-2 的
`PICO_KIMI_AGENT_RUNTIME` 在代码与生产示例中都默认 `0`，现行默认执行核仍是
`pico_orchestrator.runner.run_agent_loop`。

#142 是产品主路径 **FAIL** 证据，而不是部署/产品 PASS：login PASS；chat FAIL
（`400 status code (no body)`）；retry 入口 PASS（未再次长跑）；stop FAIL
（已记 `run.cancel_requested`，15 秒后仍 `running`）；pico-dev 401 PASS。

**禁止再写：**「main 与生产相同」「#145 已部署/已换核」「KA-2 合并 = Kimi Agent 已接入完成」
或继续引用 `768d0bd…` / `ff1dc7c…` 作为当前 tip。

---

## 2. 角色与派发（现行 · 覆盖自动派工）

| 角色 | 职责 |
|------|------|
| **总管（Grok）** | 规划、只派**当前可执行一项**、核 SHA/CI/部署/验证证据、不轻信自报 |
| **窗口 1 / 2 / 3** | 执行；**无自动触发**；须总管发标准提示词并确认 active |
| 业主 | **功能需求**；少问技术细节 |

**规则：**

1. 执行槽名：**窗口 1、窗口 2、窗口 3**（旧 E1/E2/E3 心跳叙事 **作废**）。  
2. `docs/EXECUTION-QUEUE.md` = 持久真源，**≠** 任务已触发。  
3. 上下文默认 **KEEP**；仅总管任务写明 `CLEAR` 时才清。  
4. 一项未完整收口（GitHub 证据齐）→ **不开下一项**。  
5. 写入窗 **不自判产品 PASS**；`## DEPLOYED` **≠** 产品验收 PASS。  
6. 结果必须写 GitHub PR/Issue；聊天口头完成不算。  
7. HARD：只 `juanwan99/pico`；禁 PROXY=1；禁打印密钥；禁 edu-cloud。

---

## 3. 历史收口（新回归证据优先）

| 主题 | 证据锚点 | 勿做 |
|------|----------|------|
| 停止 → cancelled | 历史 VQ-008 PASS · #117；**已被 #142 新回归覆盖** | 当前看 #144；禁止拿旧 PASS 覆盖 stop FAIL |
| Skill 目录 ADR | `docs/ADR-SKILL-CATALOG.md` **ACCEPTED A** | 禁止第二套技能商店 |
| 3 日底座冲刺 | `docs/SPRINT-3DAY-PUSH.md` COMPLETED | 勿当现行日任务 |
| P0 安全 / 多条 N 轨 | 见 VALIDATION-QUEUE 已 DONE 项 | 勿用旧 DAY-TASK 根路径当现行 |

Skill 正确表述：

- 产品目录 = **LibreChat Skills**（唯一）  
- Pico = 策略约束 + 工具 fail-closed + 执行选择 + **Run 受控快照**  
- 不是「Pico 只写快照」一句了之。

---

## 3.5 正本清源阶段（文档/污染）

| 项 | 状态 |
|----|------|
| TRUTH-FREEZE v1.0 | 已合 |
| 污染标注 POLLUTION-SWEEP | 已合 |
| KIMI-AGENT-GAP 只读 | 已合 main（#133 起；后续修订见 git log） |
| KA-0 可安装性/入口 | **已合 #137**；pin 可从公网 PyPI 安装，真实模型 hello 未验 |
| KA-1 Wire→账本契约 | **已合 #140**；mapper + 无密钥单测，不是生产接线 |
| KA-2 flag-only Session 路径 | **已合 #145**；默认 OFF、未部署、无真实 provider 证据 |
| Kimi Agent 生产真接 | **未完成**；默认仍 `run_agent_loop`，禁止宣称已接入 |

KA-2 的准确含义：main 中存在可选 Kimi Session 路径；仅显式设置
`PICO_KIMI_AGENT_RUNTIME=1` 才会选择它。**合 main ≠ 生产开 flag ≠ 生产换核 ≠ 产品 PASS。**

## 4. 未完成门禁（当前）

| 优先级 | 项 | 状态 |
|--------|-----|------|
| **P0 总门** | **#142 生产主路径烟测** | `## TEST REPORT` 已被总管采信为 **FAIL**；issue 保持 OPEN |
| **P0 · chat** | **#143 PROD-CHAT-400-DIAG** | OPEN；调查中，尚无 `## DIAG REPORT` |
| **P0 · stop** | **#144 PROD-STOP-STUCK-DIAG** | OPEN；调查中，尚无 `## DIAG REPORT` |
| 后置 | KA-3 生产默认切核 | **不得因 KA-2 已合而提前**；须另卡、真实证据与门禁 |
| 后置 | 项目—资产—产物版本厚度、自动化诚实、像素终局 | 债/后置 |

**#142 正确说法：** 抽检已完成且 verdict=FAIL；它暴露 chat 400 与 stop 不到诚实终态。
#143 / #144 是定位根因的调查卡，不是已修复证据。禁止用 CI、DEPLOYED 或 KA-2 合并覆盖
这两个生产失败。

---

## 5. 过时记忆黑名单（见到即丢弃）

- Live Preview 6014 / trycloudflare 为业主主路径  
- Mongo 误 pin 27017 当产品成功；babash 笔误当现行  
- 默认壳 = apps/web / nextchat / workbench  
- 「自动队列轮询即可触发三窗」  
- 「独立 AI 主路径约 90%」类百分比结论文  
- #123 = 生产部署实现（实际是 **队列文档**）  
- main tip 与生产应用 SHA 混为一谈  
- Harness #121 已合已冻结  
- 总管沙箱 = 用户预览机 / 可直连生产改代码  
- KA-2 已合 main = 生产已经启用 Kimi Agent
- `PICO_KIMI_AGENT_RUNTIME` 默认值为 1
- #142 已完成所以产品主路径 PASS

---

## 6. 读文档顺序（现行）

1. 本页 `docs/STATE-NOW.md`  
2. 根 `AGENTS.md`  
3. `docs/ONEFLOW.md` · `docs/CONTEXT-POLICY.md`  
4. 任务指定的 PR + `docs/EXECUTION-QUEUE.md` / `docs/VALIDATION-QUEUE.md`（若相关）  
5. **不要**把 `docs/archive/**`、旧 HANDOFF、过期 DAY-TASK 当现行派工  

计划法：`docs/MVP-3DAY.md` v1.2 FIXED · 快模式见 `docs/SPRINT-FAST.md`（到期规则以文件为准）。

---

## 7. 下一动作（总管）

当前 P0 调查并行：

1. 窗口 1 · #143 `PROD-CHAT-400-DIAG` → 写 `## DIAG REPORT`，交叉 #142。
2. 窗口 3 · #144 `PROD-STOP-STUCK-DIAG` → 写 `## DIAG REPORT`，交叉 #142。

两卡当前都仍 OPEN 且无诊断报告。生产基线按 #142 采信
`ddf269b704c7e4a13e9d02718c3dbab1db4d0b42`；不要拿 main
`fd66ce23991c963090d7be07faa594a3737942ed` 冒充生产运行版本。

诊断收口后由总管派修复/验证；KA-3 与任何生产 flag 切换必须另行授权和验收。
