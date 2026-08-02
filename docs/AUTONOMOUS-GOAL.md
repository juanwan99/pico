# 总目标自治模式（BINDING）

```
DOC: docs/AUTONOMOUS-GOAL.md
STATUS: BINDING — 业主 2026-08-02 起用：agent 自跑自测，业主只管终局验收
REPO: juanwan99/pico ONLY
PROD: https://pico.aivia.asia
SEE: docs/FAST-PATH.md · docs/CORRECTED-GOALS.md · docs/AGENT-SELFTEST.md
```

## 0. 和「旧模式」差在哪

| | 旧（人驱） | **本模式（总目标自治）** |
|--|------------|--------------------------|
| 节奏 | 业主每步「继续/派发/审查」 | Agent 按总目标 loop，少问业主 |
| 业主 | 司令 | **阅卷人**：只看 `## OWNER ACCEPTANCE` |
| 窗1/4 | 多等业主点名 | **章程内可自治**装 tip / 跑清单（必须 GitHub 回执） |
| #170 / 扩 canary | 业主授权 | **同左 · 硬闸 · 禁止自作主张** |
| 完成 | 「这张卡做完」 | **同一 tip 上 §1 清单过线 → 交验收包** |

红线、真源、不自 PASS：**不变**。

---

## 1. 总目标（唯一成功定义）

学校向 **独立 AI 工作台** 底座：

```text
登录 → 下任务 → 看见过程 → 拿到产物 → 能停 → 失败能再试 → 能找回 → 状态诚实
（改业务：S7 人确认闭环）
```

- 模型：Kimi / Moonshot HTTPS；**受控真接**（canary → 验过再谈扩/默认）。
- 账本 Task/Run/Event/Artifact/Change = 过程真源。
- 教师默认不要执行沙箱；隔离 = 数据/租户，不是每校一台 shell 机。
- **禁止**宣称「Kimi Agent 接入完成 / product PASS」直到业主在验收包上书面通过。

### 1.1 交业主验收前必须同时满足（同一 production git_sha）

| ID | 门禁 | 证据 |
|----|------|------|
| A | 生产 `ok` 且 `git_sha` == 声明 tip | `## DEPLOYED` + health |
| B | 单会员 canary 下 pico-agent 可观测 runtime（或诚实「未触发」） | 窗4 + 账本事件 |
| C | 过程可见（步骤/工具/任务栏或结果区） | 窗4 |
| D | **能停**：终态诚实，不为假「已完成」 | 窗4 + 账本 |
| E | **失败能再试**：重跑产生新 Run | 窗4 + 账本 |
| F | 产物可打开/下载（有产物时） | 窗4 |
| G | S7：propose 落库 + 确认/拒绝至少一条路径 | 窗4 + DB/API |
| H | 危险工具关；AllowlistGateway；无密钥进仓 | 配置/代码审查 |
| I | 报告写 `product PASS: NOT CLAIMED` 直至业主通过 | 回执纪律 |

---

## 2. 角色与窗口

| 角色 | 职责 | 禁止 |
|------|------|------|
| **业主** | 授权闸门；回复验收包「通过/打回」 | 被当人肉 CI |
| **总管** | 完善目标、派标准卡、合 PR、收口、出验收包 | 自判 product PASS；乱派碎卡 |
| **窗2/3** | 中/大写入；一个目标一个 PR | 拆 3A/3B；动 #170 |
| **窗1** | exact tip 部署；`## DEPLOYED` | 无 SHA 装；循环 BLOCKED |
| **窗4** | 登录+视觉；`## TEST REPORT` | 改配置/部署；假 PASS |

单 agent 可串行扮演 2→合→1→4，回执标题仍必须分开。

---

## 3. 自治循环（默认不停）

```text
1. 读 main SHA、生产 health.git_sha、最近 TEST REPORT
2. 生产落后且 main 含已合修复/功能 → 窗1 一张卡装 tip
3. 窗4 按 §4 测 → ## TEST REPORT
4. FAIL → 一个修复大包 → CI 绿 → 合 main → 回 2
5. 同一 tip 上 overall PASS 且 §1 A–I 齐 → §5 OWNER ACCEPTANCE → 停等业主
6. 遇 #170 / 扩 canary / 换核 / 清 zombie DB → STOP 只写待授权
```

- 部署与验收：**每个 tip 各一次**，不来回刷。
- 写码：可连续合 main；**装 tip 批量一次**。
- 绿档 CI 绿即合；黄档总管一次 exact-SHA 审即可合。

---

## 4. 窗4 清单（生产 · 硬刷新）

门槛：`git_sha` == 本轮 tip，否则 `## BLOCKED` **一条**即停。

1. 登录  
2. canary 会员 pico-agent 真聊  
3. 过程可见 + runtime 记录  
4. 运行中停止 → 账本/UI  
5. 失败重跑 → 新 Run  
6. 产物打开/下载  
7. S7 闭环或「本轮未触发」+ 路径说明  
8. 侧栏/任务历史能进入会话  

`overall: PASS|FAIL|PARTIAL`；`product PASS: NOT CLAIMED`。

---

## 5. 业主验收包（业主只看这个）

标题前缀：**`OWNER-ACCEPT:`**

```text
## OWNER ACCEPTANCE
- tip / production git_sha:（必须一致）
- canary: 单会员 / 未扩
- A–I 表：每条 PASS + 一句话证据
- 链接：DEPLOYED issue、TEST REPORT issue、关键 PR
- 残留风险：≤5
- product PASS: NOT CLAIMED（待业主）
- 请业主回复：验收通过 | 打回（注明条目）
```

业主「验收通过」后总管可标「业主已验收该 tip」——**仍不等于授权 #170**。

---

## 6. 标准任务卡（缺一不可）

```text
【Pico 标准任务卡】
task_id / window: 1|2|3|4 / type / context / size
【总进度】【问题】【步骤/交付】【结果写入】【禁止】
```

一窗一卡；中大任务；结果必须 GitHub 回写。

### Issue 标题纪律（业主监控用）

| 前缀 | 用途 |
|------|------|
| `MAIN:` / `FIX:` | 写入 |
| `SPEED: deploy` | 部署 |
| `VERIFY:` | 窗4 |
| `OWNER-ACCEPT:` | **仅业主验收** |

业主收藏：

- Open issues  
- 搜 `OWNER-ACCEPT`  
- 搜 `## DEPLOYED` / `## TEST REPORT`  

---

## 7. 红线（永远）

- 唯一写仓 pico；禁 edu-cloud 写；禁 PROXY=1；禁密钥进仓  
- 禁 Plan B 换核；走不通 Kimi 受控路径 → STOP 交业主  
- 禁假接入、自 PASS  
- 工具只经 AllowlistGateway；危险工具默认关  
- 生产默认 Runtime 策略：canary 单会员直至业主改口；**#170 默认切流须书面**  

---

## 8. 与 FAST-PATH / 自测关系

- **FAST-PATH**：日常节奏（改→合→装→点→回执）仍 BINDING。  
- **AGENT-SELFTEST**：沙箱本地门禁；**不能替代**生产窗4。  
- **本页**：何时可打扰业主、何为总完成、如何自治 loop。

冲突时：**红线与业主书面闸门 > 本页 > FAST-PATH 提速技巧**。

---

## 9. 当前起跑钉（每次 loop 先 gh 校准）

```bash
gh api repos/juanwan99/pico/commits/main --jq .sha
# 生产 health.git_sha（窗1 remote-health / 部署回执）
```

已知快照（会过期）：P0 修在 main 后，生产若仍落后 → **先 SPEED deploy 再 VERIFY**，禁止未装就宣称修好。
