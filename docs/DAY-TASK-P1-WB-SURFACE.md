# 标准任务卡 · T-P1-WB-SURFACE

```
DOC: docs/DAY-TASK-P1-WB-SURFACE.md
TYPE: STANDARD-TASK-CARD
ID: T-P1-WB-SURFACE
STATUS: OPEN · 正式派发体例
DATE: 2026-08-07
PRIOR: T-P0-PI-CUTOVER · #310 · tip 1a53637 · Pi+DeepSeek 已落地
FORMAT: docs/TASK-CARD-STANDARD.md
```

> **以专用 Issue 正文为准**（创建后回填编号）。本文与 Issue 同步。

---

```text
════════════════════════════════════
标准任务卡 · T-P1-WB-SURFACE
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP（MEMORY-RESET 有效；P0 已闭环）
角色：执行窗端到端 · 总管仅黄/红合与阶段核真源
RISK: 黄（UI + 账本露出；不改默认 runtime 语义）
FAST: YES（一主题一闭环；禁拆五张卡）
仓：https://github.com/juanwan99/pico
载体回写：（Issue 创建后填）
BASE：  1a53637516fbb5803c2c4afb487ccdb9fc6ff834
PRODUCT：1a53637516fbb5803c2c4afb487ccdb9fc6ff834
关联：HANDOFF-WB-PI §5 P1 · #310 P0 PASS · TRUTH-FREEZE v1.1
      docs/ADR-SKILL-CATALOG.md · docs/TEST-TASK-P1-WB-SURFACE.md

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
唯一执行窗 SOLO：改码→CI→合（权限内）→装 tip→登录点验→回写本 Issue。

【真源】
HANDOFF-WB-PI → MEMORY-RESET → TRUTH-FREEZE v1.1 → STATE-NOW
→ 本卡正文 → GitHub 证据。聊天不覆盖正文。

【目标】
在 **已落地的 Pi+DeepSeek** 上，把六条中用户可感知的 **能力架 + 真产物 + 同会话改 + 完成态** 做到可演示：
1) 产物可下/可开（禁空成功）
2) 前台 ≥3 Skill（或等价能力入口）可见可选
3) 同会话续聊能改一版
4) 过程/完成态（时间线或固定露出区）基本可见
人话：派活 → 能选能力 → 跑完有东西可点 → 再说「改短一点」能接着改 → 状态诚实。
不宣称 CLAIM-WB-DEGREE-WEB，除非六条全满且证据在 GitHub（本卡默认仍 NO）。

【IN】（只做这些）
A 产物露出
  - Run 成功后 Artifact 在 UI 固定区可见（列表/卡片/右栏之一）
  - 至少一条路径：下载 或 打开预览可用
  - 短答任务不硬塞假文件；交件任务禁「成功但无文件」
B ≥3 Skill 前台
  - 用户侧可见可选 ≥3 项（Skill 名/说明；点选后进入会话或绑定 run）
  - 数据源优先已有 catalog / ADR-SKILL-CATALOG；不自研第二套商店
  - 未选 Skill 时仍可开放派活（不破坏六条#1）
C 同会话改
  - 同一 conversation 内第二轮指令能基于上文改产物或改回复
  - 有可指 run/消息证据（非新开空白会话才「像改了」）
D 完成态 / 时间线
  - 过程或摘要可见（沿用 ledger events / 既有 timeline）
  - 终态 succeeded/failed/cancelled 诚实；失败 user_message 可读
E 合装验
  - 一主题少 PR（优先 1 个）· CI 绿 · exact tip 部署
  - ## MERGED · ## DEPLOYED · ## TEST REPORT（对表 TEST-TASK-P1）

【OUT】（本卡严禁）
- CLAIM-WB-DEGREE-WEB=YES（除非书面六条全满+证据；默认禁止本卡自签）
- KB 内核 / MCP 协议栈 / 自动化大盘（P2/P3）
- 像素 1:1 · 桌面 workDir · 拆闭源 WorkBuddy
- 复活 run_agent_loop · 双核并列真源 · 默认改回 Kimi
- Dify 门脸 · aivia 场景卷当验收
- 写 edu-cloud · 密钥进仓/Issue
- 拆窗1+2+4 三张等待卡 · 调查卡+写入卡+部署卡分离磨洋工
- 为「≥3」做假按钮无绑定 run

【验收】
1. 公网 tip = ## DEPLOYED SHA；default_runtime 仍为 pi-agent（不回退）
2. 当场交件题：有 Artifact 可下或可开（hash/文件名可贴，禁贴密钥）
3. UI 截图或 DOM 证据：≥3 Skill/能力入口可见；点选一条后 run 带 skill 或等价绑定
4. 同会话第二轮「改一版」有差异化输出或新产物版本
5. 时间线/过程至少一类可见；取消仍可用（回归 P0）
6. ## TEST REPORT 表全填；verdict PASS|FAIL；CLAIM-WB-DEGREE-WEB: NO

【禁止】
仅 juanwan99/pico · 禁 PROXY=1 · 禁裸露 18765/27017 · 禁打印 key
CI 红不合 · 假绿禁止 · 执行窗不自 PASS 产品终局

【CLAIM】
CLAIM T-P1-WB-SURFACE（SOLO）
BASE 1a53637516fbb5803c2c4afb487ccdb9fc6ff834
PRODUCT 1a53637516fbb5803c2c4afb487ccdb9fc6ff834
P1 产物露出+≥3 Skill 前台+同会话改+完成态可演示

【回写模板】
## MERGED
SHA: / PR:

## DEPLOYED
SHA:
default_runtime: pi-agent
pi_agent_scope: all
PRODUCT:

## TEST REPORT
（见 docs/TEST-TASK-P1-WB-SURFACE.md）
verdict: PASS|FAIL
CLAIM-WB-DEGREE-WEB: NO

## BLOCKED
原因:（一行）

HANDOFF-WB-PI 执行回写
DATE: / TIP_SHA: / MODE: SOLO
六条: 1__ 2__ 3__ 4__ 5__ 6__
CLAIM-WB-DEGREE-WEB: NO
下一刀: P2 或补洞

【合入】
黄档：CI 绿 + 验收在 PR；总管可快合
红：仅当碰鉴权/runtime 默认语义时升级
执行窗 VERDICT_AUTHORITY: NONE
════════════════════════════════════
```
