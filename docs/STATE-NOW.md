# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。**  
> **编排目标（唯一）= 开源 Kimi Agent。**  
> **`run_agent_loop` = 实现债，从未是目标。** 禁止「长期是自研环」污染话术。


```
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot
UPDATED: 2026-08-01
TRUTH_ORDER: GitHub 证据（PR/DIAG/DEPLOYED/TEST）> 本页 SHA 句 > 聊天
```

---

## 0. 产品与目标（冻结 · 不讨论）

| 层 | 内容 |
|----|------|
| 产品 | 学校向 **独立 AI 工作台**底座（LibreChat 壳 + Pico 账本/控制面 + 模型 HTTPS） |
| **编排目标** | **只此一个：开源 Kimi Agent 真接入**（+ 账本/白名单/S7） |
| **编排实现债** | 代码默认路径仍可能经 `run_agent_loop` → **要归位清掉**，**不是**第二目标 |
| 模型 | Kimi/Moonshot HTTPS 优先 |
| 禁 | Plan B 运行时；教师默认沙箱；edu-cloud；假接入；把债说成目标 |

**用户成功：** 登录 → 下任务 → 过程可见 → 产物 → 能停/找回/再试 → 状态诚实。

---

## 1. SHA

| 面 | SHA | 含义 |
|----|-----|------|
| main tip（写页时） | `a1a06e54c4680ee12778033594dc48ca9d528456` | 含 #152 模型合同、#153 durable cancel 等 |
| 生产硬证（最新烟测/诊断锚） | `ddf269b704c7e4a13e9d02718c3dbab1db4d0b42` | #142/#143/#144；**部署若未跟上 tip，生产仍旧** |

main ≠ 生产。#152/#153 合 main **≠** 已 DEPLOYED **≠** #142 PASS。

---

## 2. 编排认知消毒（业主重申）

| 错误（污染） | 正确 |
|--------------|------|
| 「长期目标/现状战略是自研 run_agent_loop」 | **目标从未是自研环**；环 = 进仓后的**实现债** |
| 「我们选了自研环当架构」 | **未选**；要归位到 Kimi Agent |
| 「有环 + KA-2 = 双目标」 | 目标唯一；KA-2 = flag-off **归位候选实现**；环 = 待移除占用 |
| pin/sdk 绿 = 已接入 | **否** |

---

## 3. 日用门禁（产品速度主路径）

| 项 | 状态 |
|----|------|
| #142 烟测 | OPEN · FAIL 锚旧生产；**待部署 tip 后重跑** |
| #143 chat 400 | DIAG ACCEPT；**#152 已合 main**；部署曾 BLOCKED（pico-prod DNS） |
| #144 stop zombie | DIAG ACCEPT；**#153 已合 main**；待部署/重验 |
| #151 | 实现已进 #153；issue 可收口到部署/验证 |

**P0 不是再讨论编排哲学，是：部署 → 重验 → 过 #142。**

---

## 4. 速度阻碍 · 深度清理清单（VELO）

| ID | 阻碍 | 处置 |
|----|------|------|
| V1 | 把实现债讲成目标史 | **本 PR 消毒**；聊天/总管再犯当场纠 |
| V2 | 自动 E1 队列当派工权威 | EXECUTION-QUEUE 已 SUPERSEDED |
| V3 | 旧 PLAN/POLISH/PREVIEW issue 占注意力 | **关闭** #1/#21/#28 为 SUPERSEDED（见评论） |
| V4 | 文档轮转代替部署 | STATE-NOW 写明：无 DEPLOYED 不算前进 |
| V5 | 部署跳板 `pico-prod` 不可解析 | **速度 P0 基建**；修好前一切 FIX 合 main 仍不产生用户价值 |
| V6 | 等「完美 KA-3」再日用上线 | **禁止**；日用与归位可分轨，归位须授权但不挡部署已合 FIX |
| V7 | 控制器/多文流程税 | 现行权威 = 任务卡+Issue；CONTROLLER-* 机制说明，**非**第二真源 |
| V8 | 污染阶段无限加戏 | 清单项 7 业主签可选；**不**用新长文挡部署 |
| V9 | Plan B / harness 讨论回流 | #121 已拒；再开直接关 |
| V10 | 无证据 PASS | 保留；**这是质量门不是拖速门**——拖速的是假完成返工 |

**保留的「慢」：** exact SHA、TEST REPORT、不自 PASS、禁 edu-cloud——换可信，不砍。

**砍的「慢」：** 假目标叙事、自动假派工、过期 issue、未部署的合入狂欢、用编排辩论挡部署。

详见 [VELOCITY-CLEAN.md](./VELOCITY-CLEAN.md)。

---

## 5. 角色

总管：对齐目标、清污染、审证据、少流程多闭环。  
窗口：任务卡执行 + GitHub 回写。  
业主：目标与授权；少被技术假目标干扰。

---

## 6. 下一刀（不派工时也适用）

```text
1) 恢复生产部署通道（跳板/DNS/SSH）
2) 部署含 #152+#153 的 main → ## DEPLOYED
3) 重跑 #142 → chat/stop 证据
4) 编排归位 KA-3 另授权，不与 1–3 抢叙事
```

product PASS: **NOT CLAIMED** · 编排目标未宣称完成
