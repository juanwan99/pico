# 日间任务书 · P0 Pi+DeepSeek 落地（单窗 SOLO）

```
TYPE: DAY
CARD: DAY-TASK-P0-PI-CUTOVER
TRACK: P0-PI-CUTOVER
STATUS: OPEN · 2026-08-06
MODE: SOLO · 单窗端到端（非多窗派工）
TOTAL: Grok（总管 · 阶段核真源）
EXEC: 唯一执行窗（写+装+验串行）
RISK: 黄/红（生产默认 runtime 切流 + env）
PLAN: docs/HANDOFF-WB-PI.md · docs/TRUTH-FREEZE.md v1.1
ORG: docs/STAGE-PACKAGE-MODE.md · docs/MEMORY-RESET.md
CODE: PR #309
TEST: docs/TEST-TASK-P0-PI-CUTOVER.md
ISSUE: #310
context_reset: false
```

## 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：回 Pico 整车 + 默认编排核 Pi + DeepSeek
不做：Dify 门脸终局、场景考卷当对标、双核并列真源
执行：单窗 SOLO · 改→合→装→验
```

## 指针

| 项 | 值 |
|----|-----|
| 产品真源 | [HANDOFF-WB-PI.md](./HANDOFF-WB-PI.md) |
| 清源 | [MEMORY-RESET.md](./MEMORY-RESET.md) |
| 冻结 | [TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.1 |
| 快照 | [STATE-NOW.md](./STATE-NOW.md) |
| 组织 | [STAGE-PACKAGE-MODE.md](./STAGE-PACKAGE-MODE.md) |
| 技术步骤 | [FAST-PATH.md](./FAST-PATH.md)（步骤参考；**不**拆多窗） |
| 代码 | [#309](https://github.com/juanwan99/pico/pull/309) |
| Issue | [#310](https://github.com/juanwan99/pico/issues/310) |

## 目标（单一）

**合 #309 → 生产 tip 默认 Pi + DeepSeek → 开放域当场题（过程/回复/停）→ health 自证。**  
**不宣称** `CLAIM-WB-DEGREE-WEB`。

## 非目标

六条全绿 · ≥3 Skill 前台 · KB/MCP · 像素 · workDir · loop 回流 · Dify 门脸 · 写 edu · 多窗碎卡。

## HARD

- 仅 `juanwan99/pico`
- 禁 PROXY=1 · 禁公网裸露 18765/27017 · 禁打印/Issue 贴 key
- CI 红 ⇒ 不合；默认 runtime 切流：审后合
- exact SHA 部署 + `health.git_sha` 对齐
- 禁假绿（场景卷 / 旧 #298 PASS 冒充六条）
- **禁把本卡再拆成窗1/2/4 三张等待卡**

## LEASES（SOLO 可写）

- `services/orchestrator/**` · 相关 api/health · 本卡 docs
- 生产 env（密码器，不进仓）
- Issue #310 回写
- 禁：edu-cloud · aivia 主刀 · P1 Skill 大战

---

## 【给：唯一执行窗 SOLO】（复制即开）

```text
# MEMORY RESET 先读
docs/MEMORY-RESET.md · docs/HANDOFF-WB-PI.md · docs/DAY-TASK-P0-PI-CUTOVER.md

# 单窗串行，不要等别的窗
MODE=SOLO

## A 合码
1) 读 PR #309（Pi 默认 + TRUTH-FREEZE v1.1 + MEMORY-RESET）
2) CI 绿 → merge main（若无合权：贴 CANDIDATE 等总管，仍不拆窗）
3) TIP=$(git rev-parse origin/main)  # full 40-char
4) 贴 #310: ## MERGED · SHA=…

## B 装 tip
5) 密码器（勿贴 Issue）:
   DEEPSEEK_API_KEY=…
   PICO_MODEL_PROVIDER=deepseek
   PICO_PI_AGENT_RUNTIME=1
   PICO_LEGACY_KIMI_AGENT_RUNTIME=0
   PICO_KIMI_AGENT_RUNTIME=0
6) PICO_DEPLOY_SHA=$TIP bash scripts/prod-update.sh
7) health: git_sha==TIP · default_runtime=pi-agent · pi_agent_scope=all
8) 贴 #310:
## DEPLOYED
SHA: <40字>
default_runtime: pi-agent
pi_agent_scope: all

## C 点验（同一窗 · 已登录）
9) 读 docs/TEST-TASK-P0-PI-CUTOVER.md
10) 登录公网 → 开放域当场题（禁背 aivia 卷）→ 过程/回复 → 停
11) 贴 #310: ## TEST REPORT（表格式）
12) 禁止 CLAIM-WB-DEGREE-WEB=YES

卡住: ## BLOCKED + 一行原因。做完即停。
```

---

## 生产 env（密码器 · 勿贴值）

```bash
DEEPSEEK_API_KEY=<密码器>
PICO_MODEL_PROVIDER=deepseek
PICO_PI_AGENT_RUNTIME=1
PICO_LEGACY_KIMI_AGENT_RUNTIME=0
PICO_KIMI_AGENT_RUNTIME=0
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

## 验收

| 门 | 证据（同一 Issue #310） |
|----|-------------------------|
| 合码 | ## MERGED + tip SHA |
| 部署 | ## DEPLOYED + health 字段 |
| 点验 | ## TEST REPORT |
| 禁宣 | 不写 CLAIM-WB-DEGREE-WEB=YES |

无 GitHub 回写 = 未交付。

## 结束回写

```text
HANDOFF-WB-PI 执行回写
DATE:
TIP_SHA:
MODE: SOLO
PI_DEFAULT: yes/no
DEEPSEEK: yes/no
六条: 1__ 2__ 3__ 4__ 5__ 6__
证据: #310
CLAIM-WB-DEGREE-WEB: NO
下一刀: P1 产物+Skill 前台+同会话改
```
