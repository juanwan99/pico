# Pico 到底是什么（2026-08-01 正本清源）

```
DOC: docs/WHAT-IS-PICO.md
STATUS: BINDING · 覆盖一切冲突的产品口述与旧文档金句
FREEZE: docs/TRUTH-FREEZE.md v1.1 · HANDOFF-WB-PI（默认 Pi + DeepSeek）
OWNER: 业主目标 + 总管落盘
TRUTH: 本页「是/不是/现状/目标」；代码与 DEPLOYED/TEST REPORT 可更新「现状」；不可偷偷改「目标」
```

---

## 0. 一句话

**Pico 的用法 = Grok 的用法。** 通用 LLM。老师的话是 user；系统纪律是 system，不得冒充人话。工具 / 材料 / Skill 是挂载，模型看老师的话决定用不用。问「这是什么」就解释；说「做成 Word」才交文件。

工作台（LibreChat + Pico 账本）是壳和控制面，**不是**读正文猜任务的定向工作流。

**禁止：** force_agent 自动挂交付 Skill、把「本轮必须交 N 个文件」焊进 user prompt、用课件/通知/模块词表定向。

详见 [`DIRECTION-NOW.md` §0-star](./DIRECTION-NOW.md)。

---

## 1. 是什么（产品）

| 维度 | 定义 |
|------|------|
| **品类** | **通用 LLM**（用法对齐 Grok）+ 任务型工作台壳（对话 + 可挂载工具办事 + 产物账本）；办事程度对标 WorkBuddy 六条 |
| **用户** | 教师/管理者等（学校场景），先独立可试用 |
| **壳** | **`apps/librechat`（MIT）** 中文工作台；禁止回潮 web/nextchat/workbench；禁止拆闭源 WorkBuddy |
| **智能** | **云端模型 HTTPS API**（**DeepSeek 为主**，Kimi 可选后备密钥） |
| **编排** | **默认 Pi Agent harness**（v1.1）；Kimi Agent = 遗产回滚 |
| **过程真源** | **Pico 唯一 AI 账本**：Task / Run / Event / Artifact / Change(S7)… |
| **控制面** | 租户/membership、工具白名单、停止、重试、技能策略、限流与安全门 |
| **与 edu** | **Pico = AI 过程真源**；**edu = 业务数据真源**；真联调后置；**禁止写 edu-cloud** |

**用户可感知的成功：**  
打开公网工作台 → 登录 → 下任务 → 看到过程 → 拿到产物 → 能停、能找回、失败能再试 → 状态不撒谎。

---

## 2. 不是什么

| 不是 | 说明 |
|------|------|
| 网盘 / 5GB 文件主产品 | 文件是产物与附件，不是产品中心 |
| 教务 SaaS / 成绩主库 | 学籍班课考在 edu |
| 自托管大模型训练集群 | 默认买 API |
| 自研「Agent OS」终局品牌 | **目标禁止**；代码里若有薄工具环 = **待归位债务** |
| 读正文猜任务的定向 Agent | **禁止**。特定任务只因老师挂了文件/Skill/工具。见 DIRECTION-NOW §0-star |
| Live Preview 沙箱端口故事 | 业主主路径是 **公网 HTTPS** |

---

## 3. 结构（四层）

```text
1. 壳     LibreChat 工作台 UI
2. 控制面  Pico API：身份、Run 生命周期、产物、S7、安全
3. 编排核  默认 Pi（目标 vs 现状见 §4）
4. 模型    DeepSeek 主 · Kimi 可选后备
```

---

## 4. 编排 · 目标 vs 现状（彻底诚实）

### 4.1 目标（BINDING · 2026-08-06 · HANDOFF-WB-PI）

```text
编排 = Pi Agent harness（默认唯一 multi-step）
     + Pico 账本 / 白名单 / S7 / 停止·重试控制面
模型 = DeepSeek HTTPS API（主）
Kimi Agent = 遗产/可选回滚，非产品唯一目标
禁止：自研 Agent OS 当产品主叙事或终局
禁止：双核并列真源（Pi + Reasonix + Kimi 同时「官方唯一」）
```

### 4.2 实现事实（2026-08-09 · **不是目标**）

> **真源：** TRUTH-FREEZE **v1.1** + HANDOFF-WB-PI。  
> 旧 v1.0「唯一核 = Kimi Agent / 禁 Pi」**已作废**。  
> `run_agent_loop` **从未**是产品目标；已移除，**禁止**复活为终局叙事。

```text
编排默认：Pi harness（PICO_PI_AGENT_RUNTIME）     ✅ 代码默认路径（须以生产 tip 核）
模型默认：DeepSeek HTTPS API                      ✅ 产品主模型
Kimi Agent 模块                                   ⚠️ 遗产 / flag 可选回滚 · 非默认目标
Kimi HTTPS 密钥                                   ⚠️ 可选后备 · 非产品主叙事
「目标/长期是自研环」                              ❌ 污染 · 禁止
「唯一目标仍是 Kimi Agent」                        ❌ 过期 v1.0 · 禁止再写
「Pi + Kimi + Reasonix 同时官方唯一」              ❌ 双核并列 · 禁止
```

历史偏航：约 2026-07-29 自研多步环进仓 → 后清债；2026-08-06 业主纠偏为 **Pi + DeepSeek**。  
实现是否已在公网 tip 对齐，以 `STATE-NOW` + 生产 tip 为准，**不得**用本节冒充 DEPLOYED。

### 4.3 即日起纪律

1. **默认唯一 multi-step = Pi**；事件入 Pico 账本。模型主叙事 = **DeepSeek**。  
2. **禁止**再写「编排唯一 = 开源 Kimi Agent」或「禁预埋 Pi」——那是 v1.0，已被 v1.1 取代。  
3. **禁止**复活 `run_agent_loop` / 自研 Agent OS 当产品主叙事。  
4. Kimi Agent 仅作 **遗产回滚**（显式 flag）；不得与 Pi 并列「官方唯一」。  
5. 刷新/历史/停止/重试属控制面与壳通路，不得单独证明 O1 已完成。  
6. 若 Pi 路径证伪走不通：停止擅自换核，**书面交业主**；不得静默切到第二「唯一」核。  
7. 本阶段（PLAN-TWO-PHASE 阶段一）**不做**连接器 / MCP / Skill 摊子上架；禁定向题词 if。

---

## 5. 阶段（摘要）

| 阶段 | 状态 |
|------|------|
| 公网可跑 / 主链可演示 | 大体具备 |
| 日用可靠 + 交付语义 | **阶段一主线**（PLAN-TWO-PHASE-WB） |
| WorkBuddy 程度（六条 · W1–W5） | 阶段二；阶段一全优前不开 |
| edu / 像素终局 | 后置 |

---

## 6. HARD

只写 `juanwan99/pico`；禁 edu-cloud；禁 PROXY=1；禁打印密钥；GitHub 为进度真源。

---

## 7. 三句记忆

1. Pico 是 AI 工作台底座（壳 + 账本 + 控制面 + 模型 API），不是网盘/教务。  
2. **目标默认：Pi 编排 + DeepSeek 模型**（TRUTH-FREEZE v1.1）；Kimi Agent 是遗产回滚，不是产品唯一目标。  
3. 自研工具环与双核并列真源均禁止；实现现状以 tip/STATE-NOW 为准，禁止假称完成。
