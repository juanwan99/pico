# STATE-NOW · Pico（本窗真源）

```text
DATE: 2026-08-09
仓: juanwan99/pico ONLY
CLAIM-WB-DEGREE-WEB: NO
PRODUCT PASS: 未签
main tip（写卷）: 以 origin/main 实查为准
```

## 业主方向（最新 BINDING）

见 **[docs/DIRECTION-NOW.md](./DIRECTION-NOW.md)**

```text
1) 通用开放域 · 教育仅之一
2) Pi + DeepSeek
3) 通用能力 + 复杂问题（办公优先）
4) 对标 WorkBuddy · 本阶段只打牢 Agent + UI/UX
   不做：连接器 / MCP / Skill 摊子
```

## 锁定句

```text
目标：Web 上对标 WorkBuddy 的办事能力（体验向）
方案：Pico 整车 + Pi + DeepSeek
本阶段：基础能力（Agent 优化 + 交互体验）
不做：Dify 门脸 · 场景卷对标 · 双核 · MCP/Skill/连接器铺开
验收秤：阶段一底座全优 → 阶段二加压；基建是手段
```

## 主线

| 阶段 | 状态 |
|------|------|
| **一 ENABLE** | **当前** · T-PHASE1-FOUNDATION-AGENT-UX（#360）· Agent 稳 + 交付/人包/UI + 公网办公复杂题全优 |
| **二 加压** | 阶段一全优后 · W 题/重办公链可选 · 仍不默认开 MCP/Skill |

规划骨架：[PLAN-TWO-PHASE-WB.md](./PLAN-TWO-PHASE-WB.md)（范围以 DIRECTION-NOW 收窄为准）

## 工程快照

| 项 | 值 |
|----|-----|
| main | 以 `git rev-parse origin/main` 为准；部署后写完整 40 位 |
| #351 人包下载 | 已合 |
| #356/#361 交付基础 | 成功语义 + 人包主通道 + 公网 tip；须 CI 绿 → 合 → prod-update |
| F0 清源 | WHAT-IS §4.2–4.3/§7 = v1.1 Pi+DeepSeek；PRODUCT-PASS-CONTRACT 旧 CLAIMED@38067b82 **VOID** |
| 公网 tip | 部署前 `/api/pico/tip` 可能 401；部署后须 40 位 = main |
| CLAIM-WB | **NO** |

## 错误记忆

见 MEMORY-RESET：禁止 edu 串仓；禁止用 HTML 课件单测代替复杂能力；禁止引用过期 GLOBAL PASS@38067b82；本阶段不做 MCP/Skill/连接器。
