# 阶段二任务包 · STAGE2-WB-POLISH（完整计划）

```text
DOC: docs/PLAN-STAGE2-WB-POLISH.md
STATUS: BINDING · 阶段二唯一计划真源
DATE: 2026-08-07
CARD: T-STAGE2-WB-POLISH
ACCEPT: docs/ACCEPT-STAGE2-WB-POLISH.md
TEST: docs/TEST-TASK-STAGE2-WB-POLISH.md
PRIOR: STAGE1 #320 PASS · tip PRODUCT 14615ba…
ALIGN: HANDOFF-WB-PI · 六条已绿 → 打磨到愿天天用 + 业主签章
MODE: 单窗 SOLO · 无人值守 · 仅 EXCELLENT 晋级
```

---

## 0. 阶段目标（业主口径）

```text
阶段一：公网六条路径能办事（已 PASS）
阶段二：打磨到「愿当主入口用」+ 公网证据包 + 仅业主签 CLAIM-WB-DEGREE-WEB

≠ 再堆无关大功能
≠ 像素 1:1 / 桌面 workDir
≠ 执行窗自签 CLAIM=YES
```

**出口人话：** 你愿意日常用公网 Pico 办事；证据齐后你书面 YES 或 NO+缺口。

---

## 1. 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（测→修→装→验→自我验收 串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派
```

---

## 2. 组织法 · 无人值守

```text
WHILE 小任务 S2.x 未 EXCELLENT:
  公网测 → 未优秀则修→装→再测 → SELF-ACCEPT
  仅 EXCELLENT 进入 S2.(x+1)
S2.1–S2.10 全 EXCELLENT → ## STAGE2 VERDICT
→ 请业主 ## OWNER DECISION（CLAIM YES/NO）
→ 若 YES：S2.11 真源回写 EXCELLENT
```

| 律 | |
|----|---|
| 公网主路径 | 必须 |
| PASS_WEAK 禁止晋级 | 同阶段一 |
| 不自签 CLAIM-WB | 仅业主 |
| 不回退六条 | 回归抽检 S2.0 |

### BLOCKED 白名单

```text
- 无 edge/origin SSH
- 无演示账号
- 业主未做 OWNER DECISION（仅挡 S2.11 与关 CLAIM 卡）
- 上游 DeepSeek 全域故障
```

---

## 3. 小任务（S2.0 → S2.11）

| ID | 名称 | 焦点 |
|----|------|------|
| **S2.0** | 阶段一回归抽检 | 公网登录+交件+短答不回退 |
| **S2.1** | 差距清单 | 对照 WB 行为列阻断/体验/后置 |
| **S2.2** | 交件纪律默认硬 | 交件题默认走工具；禁裸 DSML 假成功（S1.5 黄） |
| **S2.3** | 长任务手感 | 进行中心跳/文案；不假死 |
| **S2.4** | 产物露出 | 固定结果区；下载主路径好找 |
| **S2.5** | 失败+重试 | 失败人话；可再跑 |
| **S2.6** | 难任务抽检 | 2～3 个当场新题（公文/表/分析）≥2/3 可交差 |
| **S2.7** | 材料再问（轻） | 有则据材料；无则诚实未命中 |
| **S2.8** | 移动端可用 | ~390 宽能办完一件事 |
| **S2.9** | 诚实边界 | 文档写清 Web≠workDir / MCP桥 / KB试点 |
| **S2.10** | 公网证据包 | 六条+难任务+tip+截图/run 齐备 Issue |
| **S2.11** | 真源回写 | 仅业主 YES 后：STATE-NOW/HANDOFF CLAIM=YES+tip |

**S2.11 依赖 OWNER DECISION=YES；** 业主 NO/REVISE 时写缺口清单，不假写 YES。

---

## 4. 与阶段一 / CLAIM 关系

| 项 | |
|----|---|
| #320 STAGE1 | 前置 PASS；本包不得削弱 |
| #316 CLAIM | 证据升级后由业主重决；执行窗建议写在 S2.10 |
| P3 自动化/真 MCP 栈 | **本包不插队** |

---

## 5. 阶段总出口

```text
STAGE2_WB_POLISH: PASS  = S2.0–S2.10 全 EXCELLENT
CLAIM-WB-DEGREE-WEB: 仅业主 ## OWNER DECISION
S2.11: 业主 YES 后 EXCELLENT；NO 则 SKIP+缺口
```

```
════════════════════════════════════════════════════════
BINDING · STAGE2-WB-POLISH
打磨+证据+业主签章 · 仅 EXCELLENT 晋级 · 无人值守
════════════════════════════════════════════════════════
```
