# Pico 真源冻结（TRUTH-FREEZE）

```
DOC: docs/TRUTH-FREEZE.md
STATUS: BINDING FREEZE v1.8
FROZEN_AT: 2026-09-08
PURPOSE: 固定产品/架构真源，防止聊天与旧文档再次冲掉校准结论
AUTHORITY: 业主书面确认 + HANDOFF-WB-PI + 本文件 + WHAT-IS-PICO + DIRECTION-NOW §0-star + LAW §0-supreme + AGENTS 文首工作法
SUPERSEDES: v1.7；v1.6；v1.5；v1.4；v1.3；v1.2；v1.1；v1.0「唯一编排 = Kimi Agent / 禁 Pi」；主管/执行者编制；多窗日常碎派；一切未列入本冻结集的冲突口述、过时 README 金句、archive 旧文
OWNER_ORDER_2026-09-02: 最高要求：禁止自搞一套体系 / 禁止做重体系。厚桥四层绝对禁止。工作法：人合一 · GitHub 唯一真源 · 工位分开。
OWNER_ORDER_2026-09-05: 北极星 v1.3 — 能力并列 · 禁焊死路径 · 专用动词是捷径 · 工作环境交成熟上游（#744 · #919）
OWNER_ORDER_2026-09-06: 北极星 v1.4 — 产品主线是办公（Word/Excel/HTML/PPT）；写代码是仆人；不要 bash；本阶段接办公计算机，不是通用编程沙箱
OWNER_ORDER_2026-09-08: 名实 — 默认核 = 真 Pi（`pi-true`），hosted `pi_runtime` 只回滚；聊天脑 = New API `openai-responses`（现网模型见 EXPERIENCE §34），不是「DeepSeek 聊天核」；隔离办公库是天花板，`generate_*` 是未退役快路，不是第二套办公核。Pico 与 edu 的模型调用 / 统计 / 渠道管理终局统一走 New API；Pico 不做钱；edu 钱包只认 Pico export，禁止另接一套模型账。本仓仍禁止写 edu-cloud / edu-core。
RELATED: docs/HANDOFF-WB-PI.md → docs/DIRECTION-NOW.md（北极星）→ docs/MEMORY-RESET.md
```

---

## 0. 怎么用（防丢失）

1. **新窗 / 总管 / 执行窗（默认单窗 SOLO）** 必读顺序：  
   `HANDOFF-WB-PI` → `TRUTH-FREEZE` → `WHAT-IS-PICO` → `STATE-NOW` → `AGENTS.md` → 任务卡  
2. **改目标类句子**（产品是什么、编排唯一路径、禁项）= **升冻结小版本**（v1.2…）并走 PR，禁止只在聊天改口。  
3. **改实现现状**（生产 SHA、某门是否 PASS）= 更新 `STATE-NOW` + GitHub 证据；**不要**改写本文件的「目标」段。  
4. `docs/archive/**` = **历史**，默认 **非真源**。  
5. 进度真源永远是：**GitHub PR / exact SHA / CI / `## DEPLOYED` / `## TEST REPORT`**。

---

## 1. 冻结决策集 v1.8（目标 · 不可被本窗改写）

### 1.1 产品是什么

| # | 冻结句 |
|---|--------|
| S0 | **最高要求**：绝对禁止自己搞一套体系。绝对禁止做重体系 / 厚桥 / 第二能力核。只允许薄适配。桥变厚=违法。本条压过本表其余行与一切任务卡。真源：LAW §0-supreme |
| P0 | **用法 = Grok**：通用 LLM；老师的话是 user；系统纪律是 system，不得冒充人话；工具/材料/Skill 是挂载，模型自己决定调不调。没点名不交件。禁止读正文猜任务、force_agent 自动挂交付、把「必须交 N 个文件」焊进 user prompt。真源：DIRECTION-NOW §0-star |
| P0b | **厚桥四层绝对禁止**（业主 2026-09-02）：①本地 PDF 阅读器 ②办公投影器 ③交件监工 ④硬帽截窗。Pico 不是第二套能力核。进模型前禁止抽文/OCR/渲页冒充已读。禁止用 Pico 自定 reserve/步数把上游窗截短。 |
| P0c | **能力并列 · 禁焊死路径**（#744）：多项能力同时可被模型选用。禁止把「必须真图 / 必须某厂 / 必须某工具」写成唯一主路。先扎实能力，再优化编排。以后多源自动编排仍用上游 Pi，禁止自研第二编排核。 |
| P0d | **专用动词是捷径，工作环境交成熟上游**（#919）：`generate_*` / inspect / 按地址薄改是快路，不是天花板。Skill 只能收窄，不得当权限裁剪器藏已承诺能力。文件、程序执行、依赖、进程生命周期交给成熟隔离环境薄接入。Pico 保留身份授权、唯一账本、产品对象、交互与交付门闩。新能力先问哪段成熟方案接走职责。加一个万能 exec 而旧定向协议照旧 = 不算进步。未完成复用验证前，不采购/认定某一家执行厂商。 |
| P0e | **产品主线是办公**（业主 2026-09-06）：Word / Excel / HTML / PPT 是产品。写代码只够服务办公（短脚本驱动成熟办公库），不是编程产品，不是对标 Codex/Cursor。天花板 = 隔离面上真跑 python-docx / openpyxl / python-pptx + 文档 skill 工艺，不是再加专用动词。本阶段接走的是办公计算机。宿主 Pi 永 `--no-builtin-tools`。不要 bash。不要自制通用 jail。不要 Pi 市场办公包、不要社区 .NET/ONLYOFFICE 扩展。 |
| P0f | **模型与计量上游 = New API**（业主 2026-09-08）：聊天、出图、以及后续要统计/计费的模型调用只打 New API（现网 `127.0.0.1:3000`，槽位名可仍是 `DEEPSEEK_*` / `PICO_IMAGE_GATEWAY_*`）。渠道、密钥、轮询、账号管理在 New API。Pico 只记 `usage_events` 并派生积分。钱在 edu-core，只拉 Pico export 的 `points`，禁止再乘，禁止 edu 另接厂牌直连当第二账。禁止为 DeepSeek/Kimi/Claude/Grok 再造直连核。对外身份只叫 Pico。Meili embedder 现网仍智谱 = **待统一缺口**，不是新开第三条直连的许可证。本仓不写 edu。 |
| P1 | Pico = **任务型 AI 工作台（Web）** 底座（对话 + 办事 + 产物 + 唯一 AI 账本 + 控制面）；办事程度类 WorkBuddy（六条）。P1 不得压过 P0。办事优先 = 办公文件，不是写代码。 |
| P2 | **不是** 网盘 / 教务 SaaS / 成绩主库 / 自托管大模型默认 / Dify 门脸终局 / 场景考卷对标 / 定向猜任务的办公机器人 / 编程 Agent |
| P3 | 用户成功 = 公网登录 → 开放派活 → 多步过程可见 → 真产物 → 能停、能找回、同会话可改 → 状态诚实 |
| P4 | 壳 = **`apps/librechat`（MIT）**；禁止回潮 web/nextchat/workbench；禁止拆闭源 WorkBuddy |
| P5 | 与 edu：Pico = **AI 过程真源**；edu-core = **业务事实真源**（钱/钱包/学籍）；对接后置；**禁止写 edu-cloud / edu-core**；**禁止 Agent 写成绩/教务库**。计量合同见 P0f / C11 / `USAGE-LEDGER.md` |

### 1.2 架构四层

| # | 层 | 冻结选择 |
|---|-----|----------|
| A1 | 壳 | LibreChat |
| A2 | 控制面+账本 | 仅 Pico（Task/Run/Event/Artifact/Change…） |
| A3 | 编排运行时 | **默认唯一：真 Pi RPC**（`health.default_runtime=pi-true` · `run_true_pi_agent`）。hosted `pico_orchestrator.pi_runtime` = 事故回滚（`PICO_HOSTED_LOOP=1`），不是产品默认 |
| A4 | 模型 | **统一走 New API**。现网聊天脑 = New API `openai-responses`（模型名见 EXPERIENCE §34）。出图走同一 New API 的 Gemini 渠道。槽位名可仍是 `DEEPSEEK_*`。对外身份只叫 Pico。Kimi 密钥 = 可选后备，非叙事。禁止「DeepSeek 聊天核」当现网。禁止再为厂牌直连再造核 |

### 1.3 编排名实（关键）

| # | 冻结句 |
|---|--------|
| O1 | **目标（默认唯一编排核）** = **上游真 Pi** 驱动多步工具环；事件进入 Pico 账本。hosted loop / Kimi Agent 只回滚。能力并列，不把某一工具/厂商焊成唯一办事路径。以后多源自动编排仍用 Pi，禁止自研第二编排核。 |
| O2 | **模型** = New API（现网 `openai-responses`；槽位 `DEEPSEEK_*`）。产品对外不以厂牌为叙事。Kimi 不是产品脑。统计/渠道管理在 New API，不在 Pico 自研计费 OS。 |
| O3 | `run_agent_loop` = **已移除**（KA-4 HARD）；**禁止**复活为产品目标。 |
| O4 | **Kimi Agent** = **遗产/可选回滚**（`PICO_LEGACY_KIMI_AGENT_RUNTIME`），**不再**产品唯一目标。 |
| O5 | **禁止双核并列真源**（Pi + Reasonix + Kimi 同时「官方唯一」）。默认只钉 Pi。 |
| O6 | Reasonix 等实验须 flag，不得写「唯一目标」。 |
| O7 | 刷新/历史/停止/重试 = **控制面与壳通路**，不得单独用来证明 O1 已完成。 |

### 1.4 能力边界

| # | 做 | 不做（冻结期内默认） |
|---|----|----------------------|
| C1 | 日用可靠（刷新/历史/停止/重试通路）；成熟上游隔离执行面接办公计算机（验证能减少 Pico 自建才留） | 业务机开放 host bash；Pi 内建 bash；自研沙箱核 / 自制 jail；未验证就采购/认定某一家 |
| C2 | 租户/membership 数据隔离 | 把数据隔离叫「每校执行沙箱」并当主线；一人一机云桌面 |
| C3 | 公网 HTTPS 工作台 | 以 Live Preview 为业主主路径 |
| C4 | Skill 前台可见可选（分期） | 自研 MCP 协议栈 / 自研向量库内核 |
| C5 | MCP / KB = 接入现成组件（分期） | 默认开放 Host Shell/任意脚本；编程沙箱当产品卖点 |
| C6 | S7：业务变更需确认 | AI 直接改正式成绩 |
| C7 | WorkBuddy **Web 六条** | 桌面 exe / 像素 1:1 / 固定场景考卷冒充完成 |
| C8 | 原件挂账本；模型自己调工具 | 本地 PDF 阅读器 / 办公投影器 / 交件监工 / 硬帽截窗 |
| C9 | 专用办公动词作捷径；Skill 只收窄；天花板 = 隔离办公库 | 把专用动词当能力上限；用 Skill 藏已承诺能力；加厚 spec 当天花板 |
| C10 | 办公主线：真 Word/Excel/HTML/PPT；短脚本只服务办公 | 编程产品；host/Pi bash 当办公能力；把 generate_* 当上限 |
| C11 | 模型调用与计量统一 New API；Pico `usage_events` → 积分；edu 钱包只消费 export | Pico 做钱/点池；edu 另接模型直连第二账；为厂牌再造直连核；把智谱 embedder 缺口扩成第三条产品脑 |

### 1.5 协作与仓

| # | 冻结句 |
|---|--------|
| W0 | **工作法**：本窗合一。GitHub Issue/PR/SHA/CI + 公网 tip = 唯一真源。写码树 `/home/ops/pico` ≠ 生产树 `/opt/pico`（只 prod-update）。卫生=对账。禁止主管/执行者日常编制、mailbox、ECS 第二账本。真源：AGENTS 文首 |
| W1 | 只写 `juanwan99/pico`（产品主仓） |
| W2 | 禁 PROXY=1；禁打印密钥 |
| W3 | 本窗端到端（STAGE-PACKAGE）；旧窗1/2/4 与主管/执行者仅历史别名；无自动 E1 派工 |
| W4 | CLAIM-WB / 全球产品 PASS 不代签；DEPLOYED ≠ 产品 PASS；禁假绿 CLAIM。绿档本窗对账后关卡 |
| W5 | aivia-workbench = 非产品主仓；Dify/场景卷 ≠ WB 程度完成 |

### 1.6 多仓（只读认知 · 不写 edu）

```text
Pico     → 产品主仓 · AI 执行与账本 · 门脸
aivia    → 过渡参考/水管（已降级）
edu-core → 教育业务事实（后置）
edu-cloud→ 现网服役/对账（非本仓工作区）
```

---

## 2. 冻结文档集（防丢失 · 权威序）

| 序 | 路径 | 角色 |
|----|------|------|
| **T0** | **HANDOFF-WB-PI.md** | 产品目标与六条（2026-08-06 业主拍板） |
| **T1** | **TRUTH-FREEZE.md**（本页） | 目标冻结清单 |
| **T2** | **WHAT-IS-PICO.md** | 产品定义 |
| **T3** | **STATE-NOW.md** | 开窗索引（对不上以 GitHub + tip 为准） |
| **T4** | **AGENTS.md** | 执行 HARD · 文首工作法 |

---

## 3. 相对 v1.0 的变更（本版）

| 旧 v1.0 | 新 v1.1 |
|---------|---------|
| 唯一编排 = 开源 Kimi Agent | **默认 = Pi** |
| 禁止预埋 Pi | **作废**；Pi 升为默认核 |
| 模型 Kimi 优先 | **DeepSeek 主模型** |
| 编排 ENGINEERING = Kimi 故事 | **产品故事 = Pi + DeepSeek**；Kimi = 回滚 |

---

## 4. 实现现状指针（非目标）

> 细节以 `STATE-NOW` + GitHub 为准。

| 项 | 摘要 |
|----|------|
| 编排默认 | 真 Pi（`health.default_runtime=pi-true` · `PICO_TRUE_PI_DEFAULT=1`）。核以生产 tip 为准 |
| 模型默认 | New API `openai-responses`（EXPERIENCE §34）。槽位名仍 `DEEPSEEK_*`。出图同一 New API。embedder 现网智谱 = 待统一 |
| 计量 | Pico `usage_events` + 派生积分；edu 拉 export。渠道管理在 New API。Pico 不做钱 |
| 办公写路径 | 天花板 = 隔离 `sandbox_office_lib`（python-docx / openpyxl / python-pptx）。`generate_*` / spec = 快路，仍常驻，**减法未做**。老师聊天是否走沙箱 = #919，未证 |
| 遗产 | hosted `pi_runtime`、Kimi Agent 模块仍在仓内，flag 开启才走 |
| 自研环 | 仍删除；不得回流 |

---

## 5. 版本

| 版本 | 日期 | 变更 |
|------|------|------|
| **v1.0** | 2026-08-01 | 首次冻结：Kimi Agent 唯一 / 禁 Pi |
| **v1.1** | 2026-08-06 | 对齐 HANDOFF-WB-PI：默认 Pi + DeepSeek；Kimi 遗产回滚；禁双核真源；**单窗 SOLO**（废多窗日常派） |
| **v1.2** | 2026-08-11 | LAW：禁止自研 · 只做薄适配 |
| **v1.5** | 2026-09-02 | 最高句 + 厚桥四层 + 工作法 |
| **v1.6** | 2026-09-05 | 北极星 v1.3：能力并列 · 捷径/天花板 · 工作环境交成熟上游（P0c/P0d/C9） |
| **v1.7** | 2026-09-06 | 北极星 v1.4：办公主线（Word/Excel/HTML/PPT）· 写代码是仆人 · 本阶段接办公计算机 · 不要 bash（P0e/C10） |
| **v1.8** | 2026-09-08 | 名实：A3/O1 默认核 = 真 Pi（hosted 只回滚）；A4/O2/P0f 现网脑与计量上游 = New API（Pico+edu 统一，Pico 不做钱，本仓不写 edu）；办公天花板 = 隔离库，`generate_*` 是未退役快路；#942 只证调用面 |

升版规则：任何 P0–W5 / A1–A4 / O1–O7 / C1–C10 的修改 → **v1.x** 新 PR，标题含 `TRUTH-FREEZE`。

### v1.2 · 2026-08-11

- **项目法律：** [`docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md) — **禁止自研 · 只做薄适配**
- 真核 = 上游 Pi harness + 薄桥；禁止桥膨胀；禁止自研 MCP/向量内核

### v1.6 · 2026-09-05

- 对齐 DIRECTION-NOW §0-star v1.3（#744 · #919）
- 新增 P0c（能力并列 · 禁焊死路径 · 多源仍用 Pi）
- 新增 P0d / C9（专用动词是捷径；工作环境交成熟上游；Skill 只收窄）
- C1 改为允许成熟隔离执行面薄接入；仍禁 host bash / 自研沙箱核 / 未验证采购

### v1.7 · 2026-09-06

- 对齐 DIRECTION-NOW §0-star v1.4（业主：办公是产品，写代码不是核心追求）
- 新增 P0e / C10（办公主线；写代码是仆人；本阶段接办公计算机；不要 bash）
- C1 / C5 / C9 收窄：禁 Pi 内建 bash、自制 jail、编程沙箱当卖点、加厚 spec 当天花板
- 终局「工作环境交成熟上游」仍有效；阶段车辆不再是 B1 bash / overlay 编程环境

### v1.8 · 2026-09-08

- A3 / O1：默认唯一核 = 真 Pi RPC（`pi-true`）。`pi_runtime` 只保留为 `PICO_HOSTED_LOOP` 回滚，禁止再写成产品默认
- A4 / O2 / P0f / C11：现网聊天脑与出图 = New API。`DEEPSEEK_*` 是槽位名。Pico 与 edu 的统计/计费/渠道管理终局统一走 New API。Pico 只记用量；钱在 edu 只认 export。本仓不写 edu。禁止厂牌直连再造核
- 办公：隔离库已接线（#936 / #938 / #942 **调用面**）。`generate_*` 未从 CORE 退役。禁止把「库在」说成「老师聊天已走这条路」
- embedder 现网智谱 = 待统一缺口，不是新开第三条直连的许可证
