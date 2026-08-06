# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.1。**  
> **产品目标权威：[HANDOFF-WB-PI.md](./HANDOFF-WB-PI.md)。**  
> **编排默认 = Pi；模型默认 = DeepSeek。**  
> **Kimi Agent = 遗产回滚路径，非产品唯一目标。**  
> **`run_agent_loop` = 已物理删除（KA-4 HARD）；从未是目标。**

```text
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-06 (PI-KERNEL-REPLACE · HANDOFF-WB-PI)
TRUTH_ORDER: GitHub 证据 > 本页 > 聊天
```

---

## 0. 产品与目标

| 层 | 内容 |
|----|------|
| 产品 | 任务型 AI 工作台（Web）· WorkBuddy 程度六条 |
| 编排目标 | **默认唯一：Pi Agent harness** |
| 模型 | **DeepSeek HTTPS 为主** |
| 实现 | `run_agent_runtime` → `run_pi_agent`；账本 Event 映射；allowlist gateway 工具 |
| 遗产 | `PICO_LEGACY_KIMI_AGENT_RUNTIME` → `run_kimi_agent`（可选回滚） |
| 禁 | 双核并列真源；Dify 门脸终局；场景考卷对标；自研 loop 回流；edu-cloud |

**用户成功：** 登录 → 开放派活 → 过程可见 → 产物 → 能停/找回/再试 → 状态诚实。

---

## 1. 切换说明（本包）

| 项 | 值 |
|----|-----|
| 默认 runtime | `pi-agent` |
| env | `PICO_PI_AGENT_RUNTIME=1`（默认 True） |
| 模型 env | `DEEPSEEK_API_KEY` + `PICO_MODEL_PROVIDER=deepseek` |
| health 字段 | `default_runtime` / `pi_agent_runtime_enabled` / `pi_agent_scope` |
| 旧 health | `kimi_agent_*` 仍暴露（legacy 可观测） |
| 旧 loop | `legacy_loop_unavailable=true` 不变 |

---

## 2. 上一 tip 考古（Kimi 时代 · 勿覆盖产品目标）

| 面 | SHA | 含义 |
|----|-----|------|
| 历史 GLOBAL PASS tip | `38067b824c2e5fd5e445d7f33a20089c8f13360d` | #298 签于 Kimi 路径 ENGINEERING complete |
| 本包 | 待合入 tip | Pi 默认核替换；**不得**用旧 GLOBAL PASS 冒充 WB 六条完成 |

---

## 3. 推进

```text
当前：Pi 内核替换落地（代码）· 文档 TRUTH-FREEZE v1.1
P0 余量：公网门脸稳 + DeepSeek 实钥接通 + 开放域当场题跑通 + 取消可用
P1：产物露出 · ≥3 Skill 前台 · 同会话改 · 完成态
CLAIM-WB-DEGREE-WEB：P0/P1 未满六条 → NO
禁：假绿 · 密钥进仓 · 双核并列 · Dify 门脸叙事
```

product PASS (WB 六条): **NOT CLAIMED** · orchestration default: **pi-agent**
