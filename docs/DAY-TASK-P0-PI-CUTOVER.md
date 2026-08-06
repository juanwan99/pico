# 日间任务书 · P0 Pi+DeepSeek 落地（合码→装 tip→点验）

```
TYPE: DAY
CARD: DAY-TASK-P0-PI-CUTOVER
TRACK: P0-PI-CUTOVER
STATUS: OPEN · 2026-08-06
TOTAL: Grok（总管）
RISK: 黄/红（生产默认 runtime 切流 + env 语义）
PLAN: docs/HANDOFF-WB-PI.md · docs/TRUTH-FREEZE.md v1.1
CODE: PR #309 · feat/pi-kernel-replace-kimi @ 45d6dbf
TEST: docs/TEST-TASK-P0-PI-CUTOVER.md
ISSUE: #310
context_reset: false
```

## 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：回 Pico 整车 + 默认编排核 Pi + DeepSeek
不做：Dify 门脸终局、场景考卷当对标、双核并列真源
```

## 指针

| 项 | 值 |
|----|-----|
| 产品真源 | [docs/HANDOFF-WB-PI.md](./HANDOFF-WB-PI.md) |
| 冻结 | [docs/TRUTH-FREEZE.md](./TRUTH-FREEZE.md) **v1.1**（随 #309） |
| 快照 | [docs/STATE-NOW.md](./STATE-NOW.md) |
| 节奏 | [docs/FAST-PATH.md](./FAST-PATH.md) · 改→合→窗1装→窗4点 |
| 代码 | [#309](https://github.com/juanwan99/pico/pull/309) |
| 派工 Issue | [#310](https://github.com/juanwan99/pico/issues/310) |
| 考古 tip | `38067b82…`（Kimi 时代 GLOBAL PASS · **不得**冒充六条） |

## 目标（单一主目标）

**合 #309 → 生产 tip 默认 multi-step=Pi、模型=DeepSeek → 开放域当场题可跑（有过程/有回复/能停）→ health 自证。**

人话出口：登录 → 派活 → 见过程 → 有回复 → 能停；`health.default_runtime=pi-agent` 且 `pi_agent_scope=all`。

## 非目标

- `CLAIM-WB-DEGREE-WEB` / 六条全绿（P1）
- ≥3 Skill 前台 · KB · MCP · 像素 1:1 · 桌面 workDir
- 复活 `run_agent_loop` · 双核并列真源
- Dify 门脸 / aivia 场景卷验收
- 写 edu-cloud · AGENTS 长文轮转

## HARD

- 仅 `juanwan99/pico` · 禁 edu-cloud
- 禁 PROXY=1 · 禁公网裸露 18765/27017 · 禁打印/Issue 贴 key
- 密钥仅密码器/服务器 env
- CI 红 ⇒ 不合 main；#309 总管审后合（默认 runtime 切流）
- 部署 = **exact SHA** + `health.git_sha` 对齐
- 禁假绿：固定场景卷 / 旧 #298 PASS 冒充完成
- 失败回滚：上一 tip **或** 应急关 Pi（不写产品故事）

## LEASES

| 角色 | 可做 | 禁止 |
|------|------|------|
| 总管 | 审合 #309 | 无 CI 硬合 |
| 窗1 | prod-update · env · health · ## DEPLOYED | 浏览器当验收 |
| 窗4 | 登录/聊/停 · ## TEST REPORT | 改码/部署 |
| 窗2/3 | 仅 #309 红洞一个 follow-up PR | 插 P1 Skill 大战 |

---

## 【给：① 总管】

```text
读 docs/DAY-TASK-P0-PI-CUTOVER.md 与 PR #309。
核对：TRUTH-FREEZE v1.1 · 默认核 Pi · DeepSeek 优先 · 禁双核真源。
CI 绿 → merge main → 把 full 40-char tip SHA 贴 #310。
不合红 CI；不自签 CLAIM-WB-DEGREE-WEB。
```

---

## 【给：窗1 · 部署】

```text
读 docs/DAY-TASK-P0-PI-CUTOVER.md §生产 env。
1) git fetch origin main；TIP=$(git rev-parse origin/main)
2) 密码器写入（勿贴 Issue）：
   DEEPSEEK_API_KEY=…
   PICO_MODEL_PROVIDER=deepseek
   PICO_PI_AGENT_RUNTIME=1
   PICO_LEGACY_KIMI_AGENT_RUNTIME=0
   PICO_KIMI_AGENT_RUNTIME=0
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   DEEPSEEK_MODEL=deepseek-chat
3) PICO_DEPLOY_SHA=$TIP bash scripts/prod-update.sh
4) remote-health / loopback health：
   - git_sha == $TIP
   - default_runtime=pi-agent 或 pi_agent_runtime_enabled=true
   - pi_agent_scope=all
   - legacy_loop_unavailable=true
   - kimi_agent_runtime_enabled=false
5) 贴 #310：
## DEPLOYED
SHA: <40字>
pi_agent_scope: all
default_runtime: pi-agent
```

---

## 【给：窗4 · 验证】

```text
读 docs/TEST-TASK-P0-PI-CUTOVER.md 全文。
部署后一次做完：登录 → 开放域当场题 → 过程/回复 → 停止。
## TEST REPORT 贴 #310（表格式）。
不改码不部署。禁止 CLAIM-WB-DEGREE-WEB。
```

---

## 【给：窗2/3 · 仅修洞】

```text
仅当 #309 CI 红或部署后阻断主路径：一个 follow-up PR，最小 diff。
LEASES：services/orchestrator · services/api 相关；禁 edu · 禁 P1 Skill 扩容。
CANDIDATE + CI 绿后等总管合。
```

---

## 生产 env（密码器 SSOT · 勿贴值）

```bash
DEEPSEEK_API_KEY=<密码器>
PICO_MODEL_PROVIDER=deepseek
PICO_PI_AGENT_RUNTIME=1
PICO_LEGACY_KIMI_AGENT_RUNTIME=0
PICO_KIMI_AGENT_RUNTIME=0
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

业主授权：HANDOFF-WB-PI 已拍板默认 Pi 全量；空 canary = all。勿再走「Kimi canary 偷开」。

## 验收总表

| 门 | 条件 |
|----|------|
| 合码 | #309 MERGED · tip 含 Pi 默认 |
| 部署 | ## DEPLOYED · git_sha 对齐 · pi scope=all |
| 点验 | TEST-TASK 全表 PASS（或诚实 FAIL+一行原因） |
| 禁宣 | 不写 CLAIM-WB-DEGREE-WEB=YES |

## 结束回写（#310 评论）

```text
HANDOFF-WB-PI 执行回写
DATE:
TIP_SHA:
PI_DEFAULT: yes/no
DEEPSEEK: yes/no
六条: 1__ 2__ 3__ 4__ 5__ 6__
证据: #310 + DEPLOYED + TEST REPORT
CLAIM-WB-DEGREE-WEB: NO
限制: Web≠桌面 workDir · 非像素
下一刀: P1 产物露出 + ≥3 Skill 前台 + 同会话改
```

## 完成以 GitHub 为准

无 PR/无 ## DEPLOYED/无 ## TEST REPORT = 未交付。卡住必须 `## BLOCKED` + 原因一行。
