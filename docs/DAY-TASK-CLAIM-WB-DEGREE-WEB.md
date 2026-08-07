# 标准任务卡 · T-CLAIM-WB-DEGREE-WEB

```
DOC: docs/DAY-TASK-CLAIM-WB-DEGREE-WEB.md
TYPE: STANDARD-TASK-CARD
ID: T-CLAIM-WB-DEGREE-WEB
STATUS: OPEN · 正式派发体例
DATE: 2026-08-07
PRIOR: P0 #310 · P1 #311 · P2 #313 工程门 CLOSED · tip 14615ba…
FORMAT: docs/TASK-CARD-STANDARD.md
PLAN: docs/HANDOFF-WB-PI.md §1 六条 · §6 CLAIM-WB-DEGREE-WEB
```

> **以专用 Issue 正文为准**（创建后回填编号）。

---

```text
════════════════════════════════════
标准任务卡 · T-CLAIM-WB-DEGREE-WEB
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP（MEMORY-RESET 有效；P0–P2 工程门已关）
角色：执行窗取证+回写 · 总管深审 · **仅业主**可签 YES
RISK: 红（产品终局出口名；假绿代价高）
FAST: YES（一主题一闭环：取证包；默认不改 runtime 语义）
仓：https://github.com/juanwan99/pico
载体回写：（Issue 创建后填）
BASE：  a823d3e39e2deeb1a79d3b1fcc1abba66da693ba
PRODUCT：14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
关联：HANDOFF-WB-PI §1/§6 · PRODUCT-PASS-CONTRACT · #310 #311 #313
      docs/TEST-TASK-CLAIM-WB-DEGREE-WEB.md

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
唯一执行窗 SOLO：在**当前生产 tip**上做开放域取证 → 装/对 tip 若漂移 →
写证据包到本 Issue → 总管审 → **业主**书面签 YES/NO。
执行窗 **VERDICT_AUTHORITY: NONE** · **禁止**自签 CLAIM-WB-DEGREE-WEB=YES。

【真源】
HANDOFF-WB-PI §1 六条 + §6 验收 → MEMORY-RESET → TRUTH-FREEZE v1.1
→ STATE-NOW → 本卡正文 → GitHub 证据。

【目标】
在 tip 对齐的公网工作台上，用**开放域当场题**（禁 aivia 固定卷冒充）证明六条，
产出可审计证据包，供业主决定是否书面：
  CLAIM-WB-DEGREE-WEB: YES @ <full tip SHA>
默认出口仍可为 **NO + 缺口清单**（诚实优先）。
人话：不是再开发；是「做成了吗」的取证与签章流程。

【IN】（只做这些）
A tip 对齐
  - loopback health.git_sha = 生产 tip（PRODUCT 校准）
  - default_runtime=pi-agent · scope=all · kimi off · legacy_loop_unavailable=true
  - 漂移则 exact 装 tip 后再验（## DEPLOYED）
B 六条证据（每条至少 1 条公网证据；开放域题干自拟可贴摘要）
  1 开放派活：自然语言开干，非场景卡菜单
  2 能力架：≥3 Skill 可见可选 + 点选绑定（或等价入口）
  3 多步：runtime=pi-agent · tool/step 事件
  4 真产物：可下/可开 · hash/文件名 · 禁空成功；短答不硬塞文件
  5 任务资产：历史/run 可点回 · 同会话改一版有差异
  6 完成态：过程/时间线/结果区可见 · 终态诚实 · 取消可用
C 方案自证
  - 门脸=Pico · 核=Pi · 模型=DeepSeek（health / resolve / 事件字段）
  - 诚实限制：Web≠桌面 workDir · 非像素 · MCP=桥非协议栈 · KB=全文试点
D 证据包回写本 Issue
  - ## EVIDENCE PACK（六条表 + run_id / 截图路径说明 / tip）
  - ## TEST REPORT（对表 TEST-TASK）
  - ## RECOMMENDATION: YES 候选 | NO + 缺口（执行窗建议，非签章）
E 总管 ## REVIEW · 业主 ## OWNER DECISION
  - 仅业主可写：CLAIM-WB-DEGREE-WEB: YES @ <sha>
  - 或：NO / REVISE + 原因

【OUT】（严禁）
- 执行窗自签 CLAIM-WB-DEGREE-WEB=YES
- 用 aivia G/C/U 固定卷 / 旧 GLOBAL @ 38067b82 冒充六条
- 宣称桌面 workDir / 像素 1:1 / 真 MCP 协议栈 / 向量 KB 完备
- Dify 门脸终局 · 双核真源 · 回 Kimi 默认 · 复活 loop
- 大功能开发（P3 自动化 / 真 MCP wire）——另卡
- 密钥进仓/Issue · 写 edu-cloud · 多窗碎卡

【验收】
1. PRODUCT tip 与 health 对齐 · pi-agent
2. 六条每条有 GitHub 可点证据（run_id 或 UI 路径说明，禁密钥）
3. ## EVIDENCE PACK + ## TEST REPORT 完整
4. ## REVIEW 完成（总管）
5. ## OWNER DECISION：YES @ sha 或 NO/REVISE
6. 若 YES：STATE-NOW / HANDOFF 回写 CLAIM=YES + tip；若 NO：缺口进下一刀卡

【禁止】
仅 pico · 禁 PROXY=1 · 禁裸露 18765/27017 · 禁打印 key · 假绿禁止

【CLAIM】
CLAIM T-CLAIM-WB-DEGREE-WEB（SOLO）
BASE a823d3e39e2deeb1a79d3b1fcc1abba66da693ba
PRODUCT 14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
开放域取证六条 · 证据包 · 业主签 YES/NO（执行窗不自签）

【回写模板】
## DEPLOYED（若重装）
SHA: / default_runtime: pi-agent

## EVIDENCE PACK
TIP:
六条表: 1__ 2__ 3__ 4__ 5__ 6__（证据链接/run_id）
方案: Pico+Pi+DeepSeek
限制: Web≠workDir · MCP桥 · KB全文试点

## TEST REPORT
（见 TEST-TASK-CLAIM-WB-DEGREE-WEB）
verdict: PASS|FAIL（取证过程）
CLAIM-WB-DEGREE-WEB: PENDING|NO（执行窗不得写 YES）

## RECOMMENDATION
建议: YES候选 | NO
缺口:

## REVIEW（总管）
ENGINEERING_EVIDENCE: PASS|FAIL
PRODUCT_CLAIM: PENDING

## OWNER DECISION（仅业主）
CLAIM-WB-DEGREE-WEB: YES @ <sha> | NO | REVISE

【合入】
本卡以**证据与签章**为主；无强制功能 PR。
文档/STATE 仅在业主 YES 后由执行窗或总管小 PR 回写。
执行窗 VERDICT_AUTHORITY: NONE
════════════════════════════════════
```
