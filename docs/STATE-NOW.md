# Pico 当前真源快照（总管 · 正本清源）

> **真源冻结：[TRUTH-FREEZE.md](./TRUTH-FREEZE.md) v1.0。** 产品定义：[WHAT-IS-PICO.md](./WHAT-IS-PICO.md)。编排**唯一目标**=开源 Kimi Agent；**生产/默认现状**=过渡 `run_agent_loop`；main 另有 **默认关闭** 的 KA-2 候选路径（互斥、无 dual-run/Plan B）；禁假称已接入。


```
DOC: docs/STATE-NOW.md
STATUS: BINDING snapshot · 覆盖聊天里冲突的进度/角色/SHA 口述
UPDATED: 2026-08-01
TRUTH_ORDER: 本页 SHA/门禁 < 更新的 GitHub PR 评论（DEPLOYED/TEST REPORT / DIAG） < 代码 main tip
```

> **用途：** 执行窗上下文过长、记忆污染时，**先读本页 + AGENTS.md**，再读任务提示词。  
> **不要**用旧交接长文、旧 E1/E2/E3 自动心跳叙事、或总管过时百分比接管。

---

## 0. 产品一句话（正确）

Pico = **独立 AI 工作台底座**（对话 + Agent + 产物 + **唯一 AI 账本** + 模型 HTTPS）。  
壳 = **`apps/librechat`** → Pico API。  
**不是**网盘/教务 SaaS；**禁止**写 `edu-cloud`；计划法 MVP **v1.2 FIXED**（无授权不升 v1.3）。

终局分工：Pico = AI 过程真源；edu = 业务真源（对接后置）。

**目标校正（冻结）：**

| 层 | 选择 |
|----|------|
| 壳 | LibreChat（MIT） |
| 控制面 + AI 账本 | 仅 Pico |
| 编排目标 | **唯一 = 开源 Kimi Agent**（无 Plan B） |
| 编排现状 | **默认** = 过渡 `run_agent_loop`（经 `run_agent_runtime`，flag OFF） |
| main 候选 | KA-2 Kimi Session 路径 **仅** `PICO_KIMI_AGENT_RUNTIME=1`；与旧环**互斥**；**不是**第二替代目标 / dual-run |
| 模型 | Kimi / Moonshot HTTPS 优先锁定；壳广告模型必须 ⊆ API allowlist |
| 教师沙箱 | **不做**默认执行沙箱；学校隔离 = 数据/租户 |

---

## 1. SHA（证据绑定）

| 面 | 完整 SHA | 含义 |
|----|----------|------|
| **main tip（写本页时）** | `b5db109db4f0bfcdbdbf4f2c3320ac5625d382f2` | Merge #148 污染第四轮；含 #145 KA-2 与文档对齐 |
| **生产应用** | `ddf269b704c7e4a13e9d02718c3dbab1db4d0b42` | #142 / #143 / #144 采信；**早于 KA-2**，生产未跑 flag 路径 |
| 差异 | tip − 生产 | main ahead；含 docs + KA 骨架应用码；**≠ 生产换核** |

**禁止：** main=生产；#145 已部署；KA-2=已接入；tip 仍写 `868fbf4…`/`ff1dc7c…`；生产仍写 `768d0bd…` 为「当前」。

---

## 2. 角色与派发（现行）

| 角色 | 职责 |
|------|------|
| **总管（Grok）** | 规划、派可执行项、核证据、审合黄档、不盲信自报 |
| **窗口 1 / 2 / 3** | 执行；无可靠自动触发；标准任务卡 + GitHub 回写 |
| 业主 | 产品目标 |

规则：窗口名 1/2/3；EXECUTION-QUEUE 已 SUPERSEDED；KEEP 默认；不自 PASS；只 pico；禁 PROXY=1/密钥/edu-cloud。

---

## 3. 历史收口（新回归证据优先）

| 主题 | 证据 | 勿做 |
|------|------|------|
| 停止 | 历史 VQ-008；**#142 FAIL + #144 DIAG 僵尸** | 旧 PASS 盖新 FAIL |
| 真聊 400 | #142 FAIL + **#143 DIAG 模型合同** | 当「未诊断」 |
| 失败重跑入口 | #128 + #142 入口 PASS | 未长跑当全站 PASS |
| #121 harness | **已拒合关闭** | 当已冻结架构 |

---

## 3.5 正本清源 / KA 进度

| 项 | 状态 |
|----|------|
| TRUTH-FREEZE / WHAT-IS / 禁 Plan B | 已合 |
| 污染第四轮 #148 | **已合 main**；清单项 11 已勾；**项 7 业主签字仍待** → 阶段未整表 DONE |
| KA-0 / KA-1 / KA-2 | 已合 #137 / #140 / #145；默认 OFF；生产未开 |
| 生产真接 / KA-3 | **未完成 / 未授权** |

**口径：** main 里同时有「旧过渡环 + 默认关闭的 Kimi 候选」= **互斥实现**，**不是**引入第二替代目标 runtime。

---

## 4. 未完成门禁（当前）

| 优先级 | 项 | 状态 |
|--------|-----|------|
| **P0 总门** | **#142 生产主路径烟测** | ACCEPT **FAIL**；**待 FIX 部署后重跑** |
| **P0 · chat** | **#143** | **DIAG COMPLETE**（总管 ACCEPT）→ 待 **FIX 模型合同** |
| **P0 · stop** | **#144** | **DIAG COMPLETE**（总管 ACCEPT）→ 待 **FIX durable cancel / orphan 对账** |
| 后置 | KA-3 / 生产开 flag | **未授权** |
| 后置 | 限时公网 / edu / 像素 | 不插队 |

### #143 根因（采信 DIAG）

- LibreChat 广告/默认含 **`moonshot-v1-8k`**
- 生产 `PICO_ALLOWED_MODELS=kimi-k2.6,pico-agent`
- API `_assert_model_allowed` → **400** `model is not allowed`（LibreChat 表面「no body」）
- **未**创建 Task/Run；**未**调用上游 Kimi
- FIX：壳可见模型/默认 ⊆ API allowlist（优先默认 `kimi-k2.6` 或 `pico-agent`）

### #144 根因（采信 DIAG）

- cancel 对 running 只写 `cancel_requested`；执行在 API 进程内 `asyncio` task
- **进程重启后 worker 丢失** → 无人 `is_cancelled` → 永久 `running`（orphan/zombie）
- #142 样例 run 早于当前 API 容器 ~19h；生产另有同类 4 条
- 次要：provider 在途请求取消窗口
- FIX：durable cancel 终态 + 启动 reconciliation + 回归测；僵尸一次性收口另授权

禁止用 CI / DEPLOYED / KA-2 合并覆盖上述产品失败。

---

## 5. 过时记忆黑名单

- main tip = 生产 SHA；`868fbf4…`/`768d0bd…` 当「当前」  
- #143/#144 仍「等待 DIAG」  
- KA-2 合 main = 已接入 / 第二 Plan B 运行时  
- `PICO_KIMI_AGENT_RUNTIME` 默认 1 / dual-run 自动 fallback  
- Harness #121 已合  
- E1 自动心跳派工  
- #142 抽检完成 = 产品 PASS  
- 污染清单项 7 未签就宣称阶段整表 DONE  

---

## 6. 读文档顺序

TRUTH-FREEZE → WHAT-IS-PICO → **本页** → KIMI-AGENT-GAP → POLLUTION-SWEEP → AGENTS → 任务 Issue/PR。  
archive / #121 / 过期 DAY-TASK **非权威**。

---

## 7. 下一动作（总管）

```text
P0 = chat 模型合同 FIX + durable cancel/zombie FIX
     → 部署生产 → 重跑 #142
KA-3 = 未授权
product PASS = NOT CLAIMED
```

1. **窗口 1** · `PROD-CHAT-MODEL-CONTRACT-FIX`（见派发卡 / 新 Issue）  
2. **窗口 3** · `PROD-STOP-DURABLE-CANCEL-FIX`（黄档）  
3. **窗口 2** · 可选：绿档 bookkeeping 已随本 PR；或待命部署/重跑  

生产基线仍：`ddf269b704c7e4a13e9d02718c3dbab1db4d0b42`。
