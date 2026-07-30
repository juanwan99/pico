# 夜卡策略（加厚 · 可承担风险）

```
DOC: docs/NIGHT-CARD-POLICY.md
STATUS: BINDING 操作策略
DATE: 2026-07-30
WHY: 原 6h 卡常 10–90min 收工；需提高吞吐，同时保留 HARD 红线
RACI: docs/RACI-GROK-CODEX.md（总控=Grok 规划审查 · 执行=Codex）
NIGHT_RULE: 夜间必须多任务/长任务打满约6h + 可控风险
AUTHORITY: 工时与包数量以 docs/RACI-GROK-CODEX.md §3 为准（废止「≥3h 先停」）
TRUTH: 进度与证据仍只在 GitHub PR（OneFlow）
```

## 1. 问题

| 现象 | 原因 |
|------|------|
| 「6h」十几分钟结束 | 卡目标过窄、证据型任务偏多、禁止项过严导致不敢深挖 |
| 并行轨吃不满 | 一夜一轨且范围迷你 |

## 2. 新默认

| 项 | 旧 | **新** |
|----|-----|--------|
| 目标体量 | 单轨最小闭环 | **主目标 + ≥3 强制加厚包 + 储备包**；与 RACI §3 一致 |
| 工时 | 无 | **设计打满约 6h**；强制包完成后继续储备包；禁止最小闭环交卷 |
| 风险 | 几乎零风险 | **允许可控风险**（见 §3），须在 PR 写 `RISK:` |
| 部署 | 常免 | **默认夜末部署**（除非纯文档） |
| 轨 | 一夜一轨 | **一夜一主轨 + 明确副包**（副包不可踩 HARD） |

## 3. 允许的风险（可控）

| 允许 | 条件 |
|------|------|
| 大面积 LibreChat UI 改主路径/二三级 | 矩阵更新 + 截图；不宣称像素 100% |
| 扩 Skill 预设到 8–12、加深 LC 接线 | 仍唯一目录 A；工具求交；S7 写风险 |
| Playwright 主路径进 CI 或加固 selftest | 不 flake 红合 |
| Pico 侧 live edu **客户端**硬化（mock 测） | **默认 fake**；真 URL 仅 env；**永不写 edu-cloud** |
| 重构 api 模块边界（skill/run） | 测全绿；行为不变或有说明 |
| 性能/打包/镜像瘦身 | 可回滚；记录 before/after |

## 4. 仍禁止（HARD）

- 写 **edu-cloud** 仓任何内容  
- `PROXY=1`、公网暴露 18765/27017/8080、打印 key  
- 自 PASS 终局、升 v1.3 无授权  
- 第二套 Skill 商店 UI  
- 未授权生产默认真连 edu  
- 无 PR 的 MD 交接当真源  

## 5. 夜卡结构模板

```text
使命（主）
强制加厚包 A/B/C/D（须尝试；完成或诚实 BLOCKED）
风险声明 RISK:
约 6h 负载；强制包 + 储备包
H0–H6 粗时间盒（可并行包）
结束：多 PR 可，但须合 main + DEPLOYED
```

## 6. 与 PARALLEL 计划关系

PARALLEL-SPRINT-PLAN 的 N3/N4/N5 **语义保留**，但执行以 **加厚夜卡** 为准；本策略覆盖「迷你卡早停」。
