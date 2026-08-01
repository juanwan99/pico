# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。**  
> **编排目标（唯一）= 开源 Kimi Agent。**  
> **`run_agent_loop` = 实现债，从未是目标。** 禁止把过渡实现写成第二目标。

```text
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
| **编排实现债** | 默认路径仍可能经 `run_agent_loop`；它要归位清掉，**不是目标**，也不是双轨架构 |
| 当前授权 | **KA-3 未授权**；不得开 flag、切运行时或声称已接入 |
| 禁 | Plan B 运行时；教师默认沙箱；edu-cloud；假接入；把实现债说成目标 |

## 窗口地图（BINDING）

| 窗口 | 角色 |
|------|------|
| **1** | 部署（ssh / prod-update） |
| **2** | 写入 |
| **3** | 写入/调查（并行） |
| **4** | **独立验证**：已登录 + 视觉 + 操控网页 |

**用户成功：** 登录 → 下任务 → 过程可见 → 产物 → 能停/找回/再试 → 状态诚实。

---

## 1. SHA 与生产证据

| 面 | SHA | 含义 |
|----|-----|------|
| main tip（写页时） | `d5148cb462477d06013eea9818176aa522d1625c` | Merge #164；相对生产仅增加取码 runbook 文档 |
| **生产应用** | `c1a97a700ae418810d88d99eeb5c697e4da130f0` | #161 `## DEPLOYED` + CONTROLLER ACCEPT；标准 `git fetch` + `prod-update.sh`，HEAD / `origin/main` / `health.git_sha` 三一致 |
| 历史主路径 PASS | `674707dd1125289b57fbcfde069b06b8e45fd009` | #142 CONTROLLER ACCEPT：login / chat / stop / retry 入口 / pico-dev 401；**仅该历史 SHA 的主路径烟测** |

生产证据以 #161 的 `c1a97a7…` 为准：公网 login 200，UI readiness 在第 10/30 次成功，KA flag OFF。

`d5148cb…` main tip 的新增内容仅为 #164 文档；**main ≠ 生产**，#142 的历史 PASS 也不能自动外推为新 tip 烟测 PASS。

---

## 2. 日用门禁（状态诚实）

| 项 | 当前状态 | 可宣称范围 |
|----|----------|------------|
| #142 历史全项烟测 | **CLOSED · ACCEPT PASS** @ `674707dd…` | 仅该 SHA 的主路径；不是全站或编排完成 |
| #161 标准路径部署 | **CLOSED · ACCEPT DEPLOYED** @ `c1a97a7…` | 部署成立；product PASS 未宣称 |
| #162 tip 轻烟测 | **OPEN · BLOCKED，待有效重跑** | 前次抢跑时仍见 `674707dd…`；后次执行窗无法访问生产 loopback。均未执行 login/chat/stop，不能写 PASS |
| #165 浏览器/视觉验证 | **OPEN · NOT EXECUTED** | 尚无 `## VISION REPORT`；不能把 DISPATCH 当完成 |

当前能说：生产已经按标准路径运行 `c1a97a7…`。

当前不能说：`c1a97a7…` 的 tip 烟测已 PASS、视觉验证已完成、全站 PASS、Kimi Agent 已接入。

---

## 3. 运维收口

| 项 | 状态 | 证据/意义 |
|----|------|-----------|
| #157 生产取码通道 | **CLOSED · ACCEPT DONE** | read-only deploy key；生产 `git fetch origin main` 成功，不再依赖 bundle 特批 |
| #160 UI readiness 重试 | **MERGED** @ `c1a97a7…` | 生产 #161 实测 `attempt=1..9 status=000`、第 10 次 ready；假部署失败债已收口 |
| #164 main refspec runbook | **MERGED** @ `d5148cb…` | 文档钉死 `+refs/heads/main:refs/remotes/origin/main`，防 preview refspec 回归；文档卡无需部署 |

#161 中出现的旧 preview refspec 与 Docker socket 权限均已当场修正，最终标准部署成功；不粉饰过程，也不再把已收口项列为当前 P0。

---

## 4. HOLD 与授权边界

- **#159 = OPEN · HOLD_AUTH。** 历史 orphan/zombie run 的生产账本清理涉及 DB 写入；业主未授权，禁止执行或假收口。
- **KA-3 = 未授权。** 不开 `PICO_KIMI_AGENT_RUNTIME`，不切核，不以 KA-0/1/2、SDK pin 或 CI 绿冒充 Kimi Agent 真接入。
- `run_agent_loop` 只是待归位实现债；目标始终且仅为开源 Kimi Agent。

---

## 5. 进度方式（已切换轻量 · 见 FAST-PATH）

**默认不再拆多张验证卡。** 见 [FAST-PATH.md](./FAST-PATH.md)：

```text
改 → 合 main → prod-update tip → remote-health + 聊/停自测 → 三行报告
```

工具已就绪：`scripts/prod-update.sh`（含 fetch 预检）· `scripts/remote-health.sh`。

| 仍 OPEN 的旧验证债 | 处理 |
|--------------------|------|
| #162 / #165 | **收口方式**：部署窗按 FAST-PATH 做一次自测三行即可关；不必再开新体系 |
| #159 zombie | HOLD 待授权 |
| #170 KA-3 | HOLD 待业主书面授权 |

product PASS: **NOT CLAIMED（仅 #142 历史主路径 PASS）** · 编排目标未宣称完成 · `run_agent_loop` 不是目标
