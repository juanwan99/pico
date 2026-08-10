# P5 · 超 WB 终验材料包 · pack-p5-final

```text
BINDING: T-PACK-P5-FINAL-CLAIM-MATERIALS (#426) · 公网 tip 实查为准
日期: 2026-08-10
tip（取证/初测）: 6fd55ab80aa1575bdf49b68e6f3984a4e65f0dd4
tip（F5 复测）: 27954b2a59a5dcf8f5c57c1d51b176d205ff9e50（含 #427 修复）
CLAIM-WB: NO · 本目录不蕴含产品 Ready · 仅业主可签
```

## 目录

| 文件/目录 | 说明 |
|-----------|------|
| [COMPARE.md](./COMPARE.md) | 对比表：不弱 + 更强 A/B/C（每格证据指针） |
| [RETEST.md](./RETEST.md) | 复测包 F1–F6（当前 tip · 新表述 · 三层） |
| [EVIDENCE-PACK.md](./EVIDENCE-PACK.md) | 六条表 + C-T1–C-T10 + run_id |
| [s1-open-multifile](./s1-open-multifile/) | 六条#1/#3/#4/#6：开放域单文件落盘 |
| [s2-open-office-multi](./s2-open-office-multi/) | F1：开放域多文件办公包（4 文件） |
| [s3-open-revise](./s3-open-revise/) | 六条#5：同会话修订 v1→v2 |
| [s4-open-chat](./s4-open-chat/) | 六条#4 短答 + F4：无假文件 |
| [f2-open-html-page](./f2-open-html-page/) | F2/F3/F6：单 HTML 人页 + 恢复链 + 徽章 |
| [f5-open-w5-chain](./f5-open-w5-chain/) | F5：W5 脏活链（初测 P0 → 修复 #427 → 复测 PASS） |
| [f5-open-w5-chain-r2](./f5-open-w5-chain-r2/) | F5 复测（tip 27954b2a · 5 真文件 · PASS） |
| [skills-shelf](./skills-shelf/) | 六条#2：能力架 UI 帧 |

## 取证纪律

- 全部场景为**开放域当场新题**（非 P1–P4 固定卷）。
- 帧：visual-gate（BINDING #384 V0–V3）或等价帧；账本：`/api/pico/v1/*`（run/events/delivery.summary）。
- 主气泡无工具参数墙 / ID 墙（monologue_clean）。
- **禁止假绿**：F5 P0 如实记录并修复（PR #427）。
- `PACKAGE READY · P5 ≠ CLAIM-WB-DEGREE-WEB: YES`（后者仅业主 `## OWNER DECISION`）。

## 六条映射（摘要）

| # | 条 | 证据 |
|---|-----|------|
| 1 | 开放派活 | s1-open-multifile V0/V2 · 当场新题 |
| 2 | 能力架 | skills/catalog ≥5 skill · skill.snapshot 绑定 · 侧栏入口 |
| 3 | 多步 | run 事件流：agent.step · tool.call/result · run.durable |
| 4 | 真产物 | s1 1 文件 · s2 4 文件 · f2 HTML 人页 · s4 短答无文件 |
| 5 | 任务资产 | s3-open-revise：同会话 v1→v2 · revision=true · 历史可回 |
| 6 | 完成态 | 时间线/结果区帧 + run.status/delivery.summary · 终态诚实 |

## 黄债 / 缺口（诚实）

1. ~~F5 裸「多文件交付」0 文件假绿~~ → **已修复 #427（tip 27954b2a）· 复测 PASS（5 真文件）**
2. 能力架「前台逐 skill 手动点选」完整市场 UI 未在本 build 验证（目录可见 + 自动绑定有据）。
3. 欠交付（高负载 token cap 类）live 难稳定触发 —— 承 P4 黄债，未复现为 P0。
4. 桌面 workDir / 像素 1:1 / 真 MCP 协议栈 / 连接器市场：**明确不做**（诚实限制）。
