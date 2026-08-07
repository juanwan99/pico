# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.1。**  
> **产品目标权威：[HANDOFF-WB-PI.md](./HANDOFF-WB-PI.md)。**  
> **错误记忆黑名单：[MEMORY-RESET.md](./MEMORY-RESET.md)。**  
> **派卡体例：[TASK-CARD-STANDARD.md](./TASK-CARD-STANDARD.md)（CLAIM/BASE/PRODUCT）。**  
> **组织法：[STAGE-PACKAGE-MODE.md](./STAGE-PACKAGE-MODE.md) — 单窗 SOLO。**  
> **编排默认 = Pi；模型默认 = DeepSeek。**  
> **Kimi Agent = 遗产回滚，非产品唯一目标。**  
> **`run_agent_loop` = 已删；从未是目标。**

```text
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-07 (P1 closed · tip 0963b9d · CLAIM-WB still NO)
TRUTH_ORDER: GitHub 证据 > HANDOFF-WB-PI > TRUTH-FREEZE > MEMORY-RESET > 本页 > 聊天
```

---

## 0. 产品与目标

| 层 | 内容 |
|----|------|
| 产品 | 任务型 AI 工作台（Web）· WorkBuddy 程度六条 |
| 编排 | **默认唯一：Pi**（`run_pi_agent`） |
| 模型 | **DeepSeek HTTPS 为主** |
| 实现 | 账本 Event；allowlist gateway；`legacy_loop_unavailable=true` |
| 遗产 | `PICO_LEGACY_KIMI_*` 可选回滚 · 非主叙事 |
| 禁 | 双核真源 · Dify 门脸终局 · 场景卷对标 · loop 回流 · edu-cloud |

**用户成功：** 登录 → 开放派活 → 过程可见 → 产物 → 能停/找回/再试 → 状态诚实。

---

## 1. 执行编制（BINDING · 单窗）

| 角色 | 职责 |
|------|------|
| **执行窗 SOLO（唯一默认）** | 端到端：写码 → CI → 合（权限内）→ 装 tip → health → 登录点验 → 回写 Issue |
| **业主** | 方向 / 阶段成果包 ACCEPT·REVISE |
| **总管** | 阶段计划 · 禁区 · 阶段末核真源；**不**日常多窗碎派 |

**旧「窗1/2/3/4」= 职责别名，不是并行编制。** 详见 [MEMORY-RESET.md](./MEMORY-RESET.md) §1.2。  
技术步骤仍可记：改 → 合 → 装 → 验（[FAST-PATH.md](./FAST-PATH.md)），**由同一窗串行**。

---

## 2. 切换与 health（Pi 包）

| 项 | 值 |
|----|-----|
| 默认 runtime | `pi-agent` |
| env | `PICO_PI_AGENT_RUNTIME=1` · `PICO_MODEL_PROVIDER=deepseek` · `DEEPSEEK_*` |
| health | `default_runtime` / `pi_agent_*` / `legacy_loop_unavailable=true` |
| 旧字段 | `kimi_agent_*` 可观测，非默认 |

---

## 3. tip / 卡

| 面 | SHA / 链接 | 含义 |
|----|------------|------|
| **main / 生产 tip** | **`0963b9d9767c7e7d6cd62f1236abe639052a7c36`** | #312 + #311 DEPLOYED+TEST PASS |
| 历史 GLOBAL PASS tip | `38067b824c2e5fd5e445d7f33a20089c8f13360d` | Kimi 时代 · **不得**冒充六条 |
| P0 换核 | [#310](https://github.com/juanwan99/pico/issues/310) · T-P0-PI-CUTOVER · tip `1a53637…` | **工程闭环** · Pi+DeepSeek |
| P1 表面 | [#311](https://github.com/juanwan99/pico/issues/311) · T-P1-WB-SURFACE | **工程闭环** · 产物/Skill/同会话/完成态演示 |

---

## 4. 错误记忆速查（摘要 · 全文见 MEMORY-RESET）

```text
KILL:
  - 多窗日常派工（1部署+2写+4验 必须并行）
  - 唯一目标=Kimi · keep-kimi 主叙事
  - 禁 Pi/DeepSeek
  - Dify 门脸终局 · aivia 场景卷=WB 完成
  - 旧 GLOBAL PASS = CLAIM-WB-DEGREE-WEB
  - 自 PASS · 密钥进 Issue · 写 edu-cloud
KEEP:
  - 单窗 SOLO · Pi + DeepSeek · Pico 账本唯一
  - 开放域当场题 · exact-SHA 部署 · 诚实失败
```

---

## 5. 推进

```text
MODE: SOLO single-window
tip: 0963b9d9767c7e7d6cd62f1236abe639052a7c36
P0: CLOSED 工程门（#310）· Pi+DeepSeek
P1: CLOSED 工程门（#311）· 产物+≥3 Skill+同会话改+完成态 · 演示级六条可指
CLAIM-WB-DEGREE-WEB: NO  ← 未书面签产品终局；需专卡取证才可议 YES
下一刀: P2（KB/MCP/手感）或 CLAIM-WB-DEGREE-WEB 取证卡（另开）
```

product PASS (WB 六条): **NOT CLAIMED** · orchestration default: **pi-agent** · dispatch: **SOLO**
