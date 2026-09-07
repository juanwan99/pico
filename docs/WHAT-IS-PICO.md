# Pico 到底是什么（2026-08-01 正本清源）

```
DOC: docs/WHAT-IS-PICO.md
STATUS: BINDING · 覆盖一切冲突的产品口述与旧文档金句
FREEZE: docs/TRUTH-FREEZE.md v1.8 · LAW §0-supreme · AGENTS 文首工作法 · HANDOFF-WB-PI（产品六条）· DIRECTION-NOW §0-star v1.4
OWNER: 业主目标 + 总管落盘
TRUTH: 本页「是/不是/现状/目标」；代码与 DEPLOYED/TEST REPORT 可更新「现状」；不可偷偷改「目标」
```

---

## 0. 一句话

**Pico 的用法 = Grok 的用法。** 通用 LLM。老师的话是 user；系统纪律是 system，不得冒充人话。工具 / 材料 / Skill 是挂载，模型看老师的话决定用不用。问「这是什么」就解释；说「做成 Word」才交文件。

产品主线是办公（Word / Excel / HTML / PPT）。写代码只够服务办公，不是编程产品。能力并列，禁止焊死唯一路径。专用办公动词是捷径，不是天花板。天花板 = 隔离面上真跑成熟办公库。工作环境交给成熟上游隔离执行面；本阶段接的是办公计算机，不是通用 bash。Pico 只薄适配账本、授权、门脸。Skill 只能收窄。

工作台（LibreChat + Pico 账本）是壳和控制面，**不是**读正文猜任务的定向工作流。

**最高禁止：** 自己搞一套体系、做重体系、厚桥、第二能力核。只允许薄适配。

**禁止：** force_agent 自动挂交付 Skill、把「本轮必须交 N 个文件」焊进 user prompt、用课件/通知/模块词表定向、把专用动词当能力上限。

详见 [`DIRECTION-NOW.md` §0-star](./DIRECTION-NOW.md)。

---

## 1. 是什么（产品）

| 维度 | 定义 |
|------|------|
| **品类** | **通用 LLM**（用法对齐 Grok）+ 任务型工作台壳（对话 + 可挂载工具办事 + 产物账本）；办事优先 = 办公文件（Word/Excel/HTML/PPT）；办事程度对标 WorkBuddy 六条；**不是**编程产品 |
| **用户** | 教师/管理者等（学校场景），先独立可试用 |
| **壳** | **`apps/librechat`（MIT）** 中文工作台；禁止回潮 web/nextchat/workbench；禁止拆闭源 WorkBuddy |
| **智能** | **统一 New API**（现网聊天 = `openai-responses`，出图 = 同一网关 Gemini 渠道；见 EXPERIENCE §34；槽位名仍 `DEEPSEEK_*` / `PICO_IMAGE_GATEWAY_*`）。对外身份只叫 Pico。禁止厂牌直连再造核 |
| **编排** | **默认真 Pi RPC**（`health.default_runtime=pi-true`）；hosted `pi_runtime` / Kimi Agent = 遗产回滚 |
| **过程真源** | **Pico 唯一 AI 账本**：Task / Run / Event / Artifact / Change(S7)… |
| **计量** | New API 管渠道/密钥/统计；Pico 记 `usage_events` 并派生积分；**不做钱** |
| **控制面** | 租户/membership、工具白名单、停止、重试、技能策略、限流与安全门 |
| **与 edu** | **Pico = AI 过程真源**；**edu = 业务数据真源**（钱/钱包/学籍）。edu 钱包只拉 Pico export，禁止另接模型第二账。真联调后置；**禁止写 edu-cloud / edu-core** |

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
| 公开发布通道 | **否**。发布是 Edu 专用申请、校管批准。Pico 不挂 `/p/{id}` 当产品 |
| 编程 Agent / 代码 IDE | **否**。写代码只为做出/改好办公文件。不要 bash，不要对标 Codex/Cursor |

---

## 3. 结构（四层）

```text
1. 壳     LibreChat 工作台 UI
2. 控制面  Pico API：身份、Run 生命周期、产物、S7、安全
3. 编排核  默认真 Pi（目标 vs 现状见 §4）
4. 模型    云端 HTTPS API（现网 New API · EXPERIENCE §34）
```

---

## 4. 编排 · 目标 vs 现状（彻底诚实）

### 4.1 目标（BINDING · TRUTH-FREEZE v1.8）

```text
编排 = 上游真 Pi RPC（默认唯一 multi-step）
     + Pico 账本 / 白名单 / S7 / 停止·重试控制面
模型 = New API（聊天 openai-responses · 出图同一网关；槽位 DEEPSEEK_*）
计量 = New API 管渠道；Pico 记用量；edu 只认 export（本仓不写 edu）
办公天花板 = 隔离面真跑 python-docx / openpyxl / python-pptx
generate_* / spec = 快路，不是天花板
hosted pi_runtime / Kimi Agent = 遗产回滚，非产品默认
禁止：自研 Agent OS 当产品主叙事或终局
禁止：双核并列真源（真 Pi + hosted + Kimi 同时「官方唯一」）
```

### 4.2 实现事实（2026-09-08 · **不是目标** · 以生产 tip 核）

> **真源：** TRUTH-FREEZE **v1.8** + DIRECTION-NOW §0-star v1.4。  
> 旧 v1.0「唯一核 = Kimi Agent / 禁 Pi」**已作废**。  
> 旧「默认 = hosted `pi_runtime` / DeepSeek 聊天核」**不是现网**。  
> `run_agent_loop` **从未**是产品目标；已移除，**禁止**复活为终局叙事。

```text
编排默认：真 Pi（health.default_runtime=pi-true）   ✅ 现网（须以生产 tip 核）
模型默认：New API openai-responses（§34）          ✅ 现网脑；对外只叫 Pico
出图：同一 New API Gemini 渠道                      ✅ 现网
Meili embedder                                    ⚠️ 现网智谱 · 待统一进 New API
计量：Pico usage_events → 积分；edu 认 export       ✅ 合同；本仓不写 edu
Kimi Agent / hosted pi_runtime                    ⚠️ 遗产回滚 · 非默认
隔离办公库 sandbox_office_lib                     ✅ 执行层已接线（#936/#942 调用面）
generate_* 仍常驻 CORE                            ⚠️ 快路未退役 · 不是天花板
老师聊天是否走沙箱                                ❌ 未证 · #919 仍 OPEN
「目标/长期是自研环」                              ❌ 污染 · 禁止
「唯一目标仍是 Kimi Agent」                        ❌ 过期 v1.0 · 禁止再写
「hosted pi_runtime 是产品默认」                   ❌ 过期 · 禁止再写
「DeepSeek 是现网聊天核」                          ❌ 过期叙事 · 禁止再写
「Pico/edu 再直连厂牌做第二套计费」                ❌ 违法 · LAW §2.14 / P0f
```

历史偏航：约 2026-07-29 自研多步环进仓 → 后清债；2026-08-06 业主纠偏为 **Pi + 云端 API**（当时口令 DeepSeek）；其后现网脑切 New API，核切真 Pi。  
实现是否已在公网 tip 对齐，以 GitHub + `curl tip` 为准，**不得**用本节冒充 DEPLOYED。

### 4.3 即日起纪律

1. **默认唯一 multi-step = 真 Pi**；事件入 Pico 账本。对外身份 = Pico，不以厂牌为叙事。  
2. **禁止**再写「编排唯一 = 开源 Kimi Agent」或「禁预埋 Pi」——那是 v1.0。  
3. **禁止**再写「默认核 = hosted `pi_runtime`」——那是切真 Pi 之前的实现句。  
4. **禁止**复活 `run_agent_loop` / 自研 Agent OS 当产品主叙事。  
5. hosted loop / Kimi Agent 仅作 **遗产回滚**（显式 flag）；不得与真 Pi 并列「官方唯一」。  
6. 刷新/历史/停止/重试属控制面与壳通路，不得单独证明 O1 已完成。  
7. 若 Pi 路径证伪走不通：停止擅自换核，**书面交业主**；不得静默切到第二「唯一」核。  
8. 本阶段 **不做** 连接器 / MCP / Skill 摊子上架；禁定向题词 if。  
9. 办公：隔离库是天花板。加专用动词而 `generate_*` 照旧 = 不算进步。禁止把调用面 PASS 说成老师聊天已走沙箱。  
10. **模型/计量只走 New API。** 禁止厂牌直连再造核。Pico 不做钱。edu 只认 export。本仓不写 edu。

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
2. **目标默认：真 Pi 编排 + 云端 API 脑**（TRUTH-FREEZE v1.8）；hosted / Kimi 是遗产回滚。办公天花板 = 隔离库，不是 `generate_*`。  
3. **最高：禁止自搞一套体系、禁止做重体系。** 自研工具环与双核并列真源均禁止；实现现状以 GitHub + tip 为准，禁止假称完成。
