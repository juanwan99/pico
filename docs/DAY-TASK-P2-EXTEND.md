# 标准任务卡 · T-P2-EXTEND

```
DOC: docs/DAY-TASK-P2-EXTEND.md
TYPE: STANDARD-TASK-CARD
ID: T-P2-EXTEND
STATUS: OPEN · 正式派发体例
DATE: 2026-08-07
PRIOR: T-P0-PI-CUTOVER #310 · T-P1-WB-SURFACE #311 · tip 0963b9d…
FORMAT: docs/TASK-CARD-STANDARD.md
PLAN: docs/HANDOFF-WB-PI.md §5 P2
```

> **以专用 Issue 正文为准**（创建后回填编号）。本文与 Issue 同步。

---

```text
════════════════════════════════════
标准任务卡 · T-P2-EXTEND
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP（MEMORY-RESET 有效；P0/P1 工程门已关）
角色：执行窗端到端 · 总管仅黄/红合与阶段核真源
RISK: 黄（接入现成组件；不改默认 runtime=Pi 语义）
FAST: YES（一主题一闭环；禁拆五张卡）
仓：https://github.com/juanwan99/pico
载体回写：（Issue 创建后填）
BASE：  cd4139ea29b433526d54d384cca06ee0f8eeb9df
PRODUCT：0963b9d9767c7e7d6cd62f1236abe639052a7c36
关联：HANDOFF-WB-PI §5 P2 · #310 · #311 · TRUTH-FREEZE v1.1
      docs/TEST-TASK-P2-EXTEND.md

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
唯一执行窗 SOLO：改码→CI→合→装 tip→登录点验→回写本 Issue。

【真源】
HANDOFF-WB-PI → MEMORY-RESET → TRUTH-FREEZE v1.1 → STATE-NOW
→ 本卡正文 → GitHub 证据。聊天不覆盖正文。

【目标】
在 P0/P1 已可演示的六条表面上，做 **P2 加深**：
1) **知识库（KB）**：接入现成检索/RAG 组件（不自研向量内核）；用户可对已挂载材料提问并得到有依据的答复或诚实「未命中」
2) **MCP 白名单**：接入 **1～2** 个现成 MCP（或等价工具桥），经 Pico allowlist；用户路径可触发且可审计
3) **手感**：流式/等待/错误文案接近「日常能用来办事」（非像素 1:1）；不破坏 pi-agent 默认
人话：不只闲聊——能挂一点自己的材料问、能多接一两个外部工具、用起来不糊。
**默认不签** CLAIM-WB-DEGREE-WEB（除非本卡末另开取证且六条+证据齐——本卡 OUT 仍默认 NO）。

【IN】（只做这些）
A 知识库试点（现成组件）
  - 控制面：挂载/选择材料（文件或已有 Artifact）进入可检索范围（最小可用即可）
  - 问答路径：开放域问「根据这份材料…」→ 有引用/摘录或诚实未命中
  - 不自研向量 DB 内核；可用现成库/API（密钥仅服务端）
  - 失败诚实；不装「已全库 RAG 完成」
B MCP 白名单 1～2
  - 仅 allowlist；危险 host/shell 类默认关
  - 用户可感知入口或 Skill/工具列表中可见
  - 账本有 tool.call / tool.result（runtime 仍 pi-agent）
  - 禁止默认打开任意 MCP 市场
C 手感打磨（最小集合）
  - 长跑：心跳/「仍在处理」可见（若已有则回归加固）
  - 失败：user_message 中文可读
  - 短聊与交件路径均不崩；取消仍可用（P0 回归）
D 合装验
  - 少 PR（优先 1）· CI 绿 · exact tip 部署
  - ## MERGED · ## DEPLOYED · ## TEST REPORT
  - health：default_runtime=pi-agent · scope=all 不回退

【OUT】（本卡严禁）
- 自研 MCP 协议栈 / 自研向量数据库内核
- 自动化大盘 / 企业 Admin 全套（P3）
- Dify 升门脸终局 · aivia 场景卷当验收
- 双核并列 · 默认回 Kimi · 复活 run_agent_loop
- 写 edu-cloud · Agent 写教务库 · 密钥进仓/Issue
- 像素 1:1 · 桌面 workDir · 拆闭源 WorkBuddy
- 多窗碎卡 · 假 KB/MCP 按钮无后端
- 本卡默认 **禁止** 自签 CLAIM-WB-DEGREE-WEB=YES（取证另卡）

【验收】
1. tip 对齐 · 仍 pi-agent / scope=all
2. KB：至少 1 条「挂材料→提问→有依据答复或诚实未命中」公网证据（run_id / 摘录，勿贴密钥）
3. MCP：1～2 个白名单工具可触发；ledger 有记录
4. 手感：长任务可见进行中；失败中文；cancel 回归 PASS
5. P1 表面不回退（产物下载 / ≥3 Skill / 同会话改 抽 1 条）
6. ## TEST REPORT；CLAIM-WB-DEGREE-WEB: NO

【禁止】
仅 juanwan99/pico · 禁 PROXY=1 · 禁裸露 18765/27017 · 禁打印 key
CI 红不合 · 假绿禁止 · 执行窗不自 PASS 产品终局

【CLAIM】
CLAIM T-P2-EXTEND（SOLO）
BASE cd4139ea29b433526d54d384cca06ee0f8eeb9df
PRODUCT 0963b9d9767c7e7d6cd62f1236abe639052a7c36
P2 KB试点+MCP白名单1～2+手感打磨（不签六条CLAIM）

【回写模板】
## MERGED
SHA: / PR:

## DEPLOYED
SHA:
default_runtime: pi-agent
pi_agent_scope: all
PRODUCT:

## TEST REPORT
（见 docs/TEST-TASK-P2-EXTEND.md）
verdict: PASS|FAIL
CLAIM-WB-DEGREE-WEB: NO

## BLOCKED
原因:（一行）

HANDOFF-WB-PI 执行回写
DATE: / TIP_SHA: / MODE: SOLO
KB: yes/no · MCP: n= · handfeel: yes/no
六条: 1__ 2__ 3__ 4__ 5__ 6__
CLAIM-WB-DEGREE-WEB: NO
下一刀: CLAIM 取证卡 或 P3

【合入】
黄档：CI 绿 + 验收在 PR；总管可快合
红：鉴权/runtime 默认语义/任意外连扩大 → 总管审
执行窗 VERDICT_AUTHORITY: NONE
════════════════════════════════════
```
