# 记忆复位 · 错误记忆黑名单（pico）

```
DOC: docs/MEMORY-RESET.md
STATUS: BINDING · 新窗开场必读
DATE: 2026-08-06
OWNER: 单窗执行 · 正本清源
TRUTH: docs/HANDOFF-WB-PI.md > docs/TRUTH-FREEZE.md v1.1 > 本页 > 聊天
```

> **凡与本页冲突的旧聊天、旧 STATE、旧任务卡分窗句、archive 金句 → 作废。**  
> **宏观目标错了 = 整窗作废。**

---

## 0. 现行一句（钉死）

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：回 Pico 整车 + 默认编排核 Pi + DeepSeek
不做：Dify 门脸终局、场景考卷当对标、双核并列真源
执行：单窗 SOLO（改→合→装→验 同一窗串行）
组织：docs/STAGE-PACKAGE-MODE.md
```

---

## 1. 作废记忆（禁止再当真源）

### 1.1 产品 / 编排

| 错误记忆 | 现行 |
|----------|------|
| 唯一编排目标 = 开源 **Kimi Agent** | 默认唯一 = **Pi**；Kimi = 遗产回滚 |
| 禁 Pi / Plan B / 不得预埋 DeepSeek | **作废**；Pi + DeepSeek 为默认 |
| keep-kimi · 主叙事仍是 Kimi | **作废**；产品故事 = Pi + DeepSeek |
| 旧 GLOBAL product PASS @ `38067b82…` = 六条完成 | **否**；仅 Kimi 时代 ENGINEERING；**≠** `CLAIM-WB-DEGREE-WEB` |
| `run_agent_loop` 可回 / 双核并列真源 | **禁**；loop 已删；默认只钉 Pi |
| Dify Chat/Console = 产品门脸终局 | **禁**；门脸 = Pico LibreChat 壳 |
| aivia G/C/U 场景卷 = 对标 WorkBuddy 完成 | **禁**；水管回归 ≠ WB 程度 |
| 教育专家站主线 / Agent 写教务库 | **禁** |
| aivia CLAIM S1–S4 / GENERAL-WB 完成 = 产品终局 | **禁**；本仓降级 |

### 1.2 窗口 / 派工（本次重点）

| 错误记忆 | 现行 |
|----------|------|
| **必须**同时开窗1部署 / 窗2·3写入 / 窗4验证 | **单窗 SOLO** · 一人串行端到端 |
| 总管每刀拆多窗派卡 | **禁**；一张阶段/日卡 · 单执行窗 |
| FAST-PATH「窗编号钉死」= 日常必多窗 | **技术步骤仍在**（改→合→装→验），**组织 = 单窗**完成 |
| 无登录硬跑 chat 的「窗1 当验收」 | 仍禁假验；但验收由 **同一 SOLO 窗** 登录后做 |
| EXECUTION-QUEUE 自动 E1 派工 | **SUPERSEDED** |
| 多卡仪式：调查+写入+部署+烟测+视觉 | **禁**；能一卡并则一卡 |

**历史窗号仅作职责别名（非并行编制）：**

| 旧号 | 含义 | 单窗怎么做 |
|------|------|------------|
| 窗2/3 | 写码 | SOLO 写 PR |
| 总管 | 合门禁 | 绿档可按授权合；黄/红仍审 |
| 窗1 | 装 tip | SOLO 跑 prod-update |
| 窗4 | 点验 | SOLO 登录聊停 + TEST REPORT |

### 1.3 流程 / 证据

| 错误记忆 | 现行 |
|----------|------|
| 聊天口述进度 = 真源 | GitHub Issue/PR/SHA/CI/`## DEPLOYED`/`## TEST REPORT` |
| 自 PASS 产品终局 | **禁**；`VERDICT_AUTHORITY: NONE` |
| 密钥/JWT 进 Issue 当证据 | **禁**；密码器 SSOT |
| PROXY=1 / 公网裸露 18765·27017 | **禁** |
| 写 edu-cloud | **禁** |

---

## 2. 现行指针（开场只读这些）

```text
1) docs/HANDOFF-WB-PI.md     ← 产品真源
2) docs/TRUTH-FREEZE.md      ← v1.1 冻结
3) docs/MEMORY-RESET.md      ← 本文（清错）
4) docs/STATE-NOW.md         ← tip/健康快照
5) docs/STAGE-PACKAGE-MODE.md← 单窗阶段包
6) docs/TASK-CARD-STANDARD.md  ← 任务卡格式
7) docs/DAY-TASK-P0-PI-CUTOVER.md ← 现行刀 T-P0-PI-CUTOVER
```

aivia-workbench：只读其 HANDOFF/CANON/MEMORY-RESET 知「已降级」，**不**在本仓派 GENERAL-WB 主刀。

---

## 3. 单窗 SOLO 动作（默认）

```text
CLAIM 日卡/阶段卡
  → 写码（若未合）→ CI → 合 main（权限内）
  → prod-update exact tip + env
  → health 自证
  → 登录开放域当场题 + 停
  → ## DEPLOYED + ## TEST REPORT 贴同一 Issue
  → 阶段成果包（若阶段末）
停：DoD 满或 ## BLOCKED 一行原因
```

不并行抢同一仓；不拆五张等待卡。

---

## 4. 复位声明（可贴 Issue）

```text
## MEMORY RESET
DATE: 2026-08-06
MODE: SOLO single-window
DEFAULT: Pi + DeepSeek
KILL: multi-window daily dispatch · Kimi-as-only-goal · Dify-as-product · scene-exam-as-WB
CARD: DAY-TASK-P0-PI-CUTOVER · #310
CLAIM-WB-DEGREE-WEB: NO (until six bars + evidence)
```
