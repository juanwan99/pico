# Pico 当前真源快照（总管 · 正本清源）

> **产品定义：[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)。编排目标=开源 Kimi Agent；现状=过渡自研环，禁假称已接入。**


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
| **main tip** | `ff1dc7c0f95414dbbc3e4d7cd1b5444bb0e0b43d` | 含 #124 队列关闭文档 |
| **生产应用** | `768d0bd56858acacf859cf9a8cd357f68dc2f1ba` | 运行中的应用码；EQ-031 `## DEPLOYED` + Controller **ACCEPTED** |
| 差异 | tip − 生产 | **仅 docs 队列**，无应用代码漂移 |

生产已验（部署门，**不是**产品功能 PASS）：login 200、端口 loopback、pico-dev 401、HEAD=health=`768d0bd…`。

**禁止再写：**「main ≈ 768d0bd」「生产还在 567ab9e」「要先派窗重复 health」。

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

## 3. 已收口（勿重开，无回归证据时）

| 主题 | 证据锚点 | 勿做 |
|------|----------|------|
| 停止 → cancelled | VQ-008 PASS · #117 · 生产曾 `567ab9e…` 起 | **禁止**无新回归时重复 VQ-008 |
| Skill 目录 ADR | `docs/ADR-SKILL-CATALOG.md` **ACCEPTED A** | 禁止第二套技能商店 |
| 3 日底座冲刺 | `docs/SPRINT-3DAY-PUSH.md` COMPLETED | 勿当现行日任务 |
| P0 安全 / 多条 N 轨 | 见 VALIDATION-QUEUE 已 DONE 项 | 勿用旧 DAY-TASK 根路径当现行 |

Skill 正确表述：

- 产品目录 = **LibreChat Skills**（唯一）  
- Pico = 策略约束 + 工具 fail-closed + 执行选择 + **Run 受控快照**  
- 不是「Pico 只写快照」一句了之。

---

## 4. 未完成门禁（当前）

| 优先级 | 项 | 状态 |
|--------|-----|------|
| **P0 当前唯一** | **#119 + #120 独立生产产品验证** | 代码已在 `768d0bd…`；**尚无 `## TEST REPORT`** |
| P1 | #121 Harness 边界文档 | **Draft + CONFLICTING**；未冻结 |
| P1 | 部署脚本 UI readiness / 假 BLOCKED | 债；有报告 |
| P1 | 用户级 failed Run 重跑闭环 | 缺 |
| 后置 | 项目—资产—产物版本厚度、自动化诚实、M5 edu、像素终局 | 债/后置 |

**#119/#120 正确说法：** 已实现、已上线（在生产应用 SHA 内）；**等待独立生产验证**。  
**禁止**因 DEPLOYED 写成产品 PASS。

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

**仅一项：** 窗口 1 · 验证 · #119/#120 生产行为 · 结果 `## TEST REPORT` @ #119。  
生产 SHA 门槛 = **`768d0bd…`**（业主已确认，**不必**再派窗只查 health）。

收口后由总管核证据再派下一项或请业主给下一功能需求。
