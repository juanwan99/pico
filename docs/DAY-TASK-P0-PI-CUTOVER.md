# 标准任务卡 · T-P0-PI-CUTOVER

```
DOC: docs/DAY-TASK-P0-PI-CUTOVER.md
TYPE: STANDARD-TASK-CARD
ID: T-P0-PI-CUTOVER
ISSUE: #310
CODE: #309
STATUS: OPEN · 正式派发体例
DATE: 2026-08-06
```

> **以 Issue [#310](https://github.com/juanwan99/pico/issues/310) 正文为准。** 本文与 Issue 同步。

---

```text
════════════════════════════════════
标准任务卡 · T-P0-PI-CUTOVER
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP（已 MEMORY-RESET；勿 /new 清掉真源）
角色：执行窗端到端 · 总管仅黄/红合与阶段核真源
RISK: 黄/红（生产默认 runtime 切流 + env 语义）
FAST: YES（一主题一闭环；禁拆五张卡）
仓：https://github.com/juanwan99/pico
载体回写：https://github.com/juanwan99/pico/issues/310
BASE：  1e06440dcabee4c643454483094541cdfc601182
PRODUCT：UNKNOWN（开跑前 loopback /api health.git_sha 校准；考古参考 38067b824c2e5fd5e445d7f33a20089c8f13360d）
关联：PR #309 @ bc09c54f19eabf00bf838904ee5509541f7520ae
      docs/HANDOFF-WB-PI.md · docs/MEMORY-RESET.md · docs/TRUTH-FREEZE.md v1.1
      docs/TEST-TASK-P0-PI-CUTOVER.md · docs/TASK-CARD-STANDARD.md

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
唯一执行窗 SOLO：写/合（权限内）/装 tip/登录点验/回写 #310。
不是「只等窗4」的半窗；不是并行三窗编制。

【真源】
1) HANDOFF-WB-PI  2) MEMORY-RESET  3) TRUTH-FREEZE v1.1
4) STATE-NOW  5) 本卡 Issue 正文  6) GitHub SHA/CI/DEPLOYED
聊天摘要不覆盖正文。

【目标】
合 #309 → 生产 tip 默认 multi-step=Pi、模型=DeepSeek →
开放域当场题可跑（有过程/有回复/能停）→ health 自证 pi-agent。
人话：登录→派活→见过程→有回复→能停。
不宣称 CLAIM-WB-DEGREE-WEB。

【IN】（只做这些）
A 合码
  - #309 CI 绿 → merge main
  - tip = origin/main full 40-char
  - ## MERGED 贴 #310
B 装 tip
  - 密码器：DEEPSEEK_API_KEY、PICO_MODEL_PROVIDER=deepseek、
    PICO_PI_AGENT_RUNTIME=1、LEGACY_KIMI=0、KIMI_RUNTIME=0
  - PICO_DEPLOY_SHA=$TIP bash scripts/prod-update.sh
  - health：git_sha==TIP · default_runtime=pi-agent · pi_agent_scope=all
    · legacy_loop_unavailable=true · kimi_agent_runtime_enabled=false
  - ## DEPLOYED 贴 #310（更新 PRODUCT=线上 sha）
C 点验（同一窗 · 已登录）
  - 按 docs/TEST-TASK-P0-PI-CUTOVER.md（PI-T1…T12）
  - 开放域当场题（禁 aivia 固定卷）
  - ## TEST REPORT 贴 #310
D 可选修洞
  - 仅阻断主路径时一个 follow-up PR，不扩 P1

【OUT】（本卡严禁）
- CLAIM-WB-DEGREE-WEB=YES / 六条全绿自签
- ≥3 Skill 前台、KB、MCP、像素、桌面 workDir（P1/P2）
- 复活 run_agent_loop · 双核并列真源
- Dify 门脸终局 · aivia 场景卷当验收
- 写 edu-cloud · 密钥进 Git/Issue
- 拆成窗1部署卡+窗2写卡+窗4验卡 三张等待
- 用旧 GLOBAL PASS @ 38067b82 冒充本卡完成

【验收】
1. main tip 含 Pi 默认核 + TRUTH-FREEZE v1.1（#309 MERGED）
2. ## DEPLOYED：health.git_sha = tip；default_runtime=pi-agent；scope=all
3. ## TEST REPORT：PI-T1…T12 表；三行 chat/stop；verdict PASS|FAIL
4. 开放域当场题非空回复；过程或 run 状态诚实；停止可用或 N/A+说明
5. 作者不自签 CLAIM-WB-DEGREE-WEB；不自签产品终局 PASS

【禁止】
HARD：仅 juanwan99/pico · 禁 PROXY=1 · 禁公网裸露 18765/27017 · 禁打印 key
CI 红不合；假绿（场景卷/旧 PASS）禁止；失败 ## BLOCKED 一行原因

【CLAIM】（复制即认领）
CLAIM T-P0-PI-CUTOVER（SOLO）
BASE 1e06440dcabee4c643454483094541cdfc601182
PRODUCT UNKNOWN
合 #309 装 tip 默认 Pi+DeepSeek 并当场题验收

【回写模板】
## MERGED
SHA: <40>
PR: #309

## DEPLOYED
SHA: <health.git_sha>
default_runtime: pi-agent
pi_agent_scope: all
PRODUCT: <同 SHA · 校准后改 CLAIM 块>

## TEST REPORT
（见 TEST-TASK-P0-PI-CUTOVER 表）
verdict: PASS|FAIL
CLAIM-WB-DEGREE-WEB: NO

## MEMORY RESET（若新会话）
MODE: SOLO · DEFAULT: Pi+DeepSeek · KILL: multi-window/Kimi-goal/Dify/scene-exam

HANDOFF-WB-PI 执行回写
DATE: / TIP_SHA: / MODE: SOLO
PI_DEFAULT: / DEEPSEEK: / 六条: 1__…6__
CLAIM-WB-DEGREE-WEB: NO
下一刀: P1 产物+Skill 前台+同会话改

【合入】
- 默认：总管审后合 #309（runtime 切流 · 黄/红）
- 绿档文档-only follow-up 可按 FAST 代合
- 执行窗 VERDICT_AUTHORITY: NONE · 不自 PASS 产品
════════════════════════════════════
```

## 开跑前校准（执行窗 · 2 分钟）

```bash
# BASE
git fetch origin main && git rev-parse origin/main
# PRODUCT（线上 · 密码器机 / 跳板）
# curl -sS http://127.0.0.1:18765/health | jq -r .git_sha
# 将校准后的 PRODUCT 写回 #310 CLAIM 块后再大干
```

## 测试对表

见 [TEST-TASK-P0-PI-CUTOVER.md](./TEST-TASK-P0-PI-CUTOVER.md)。
