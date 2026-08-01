# Pico 整体技术架构方案（含定价）

```
DOC: docs/OVERALL-ARCHITECTURE.md
SUPERSEDED_IN_PART_BY: docs/TRUTH-FREEZE.md v1.0 + docs/WHAT-IS-PICO.md（产品/编排/沙箱边界以冻结真源为准；文中「底层 Agent」若指现网 = 过渡 tool-loop，非已接 Kimi Agent）
STATUS: DRAFT v0.2 — 不确定项已由架构默认建议填齐（待业主一键 ACK 后升 FIXED v1.0）
SCALE: 起步 10 校 × ~100 教师 ≈ 1000 席位
RELATED:
  - docs/SCOPE.md
  - docs/ARCHITECTURE.md（层简述）
  - docs/archive/DEPLOY-AND-PRICING.md（部署/收费讨论底稿）
  - docs/archive/UNDERLYING-AGENT.md
  - docs/PHASE2-CONTRACTS.md / PHASE3-INTEGRATION.md
DATE: 2026-07-29
```

---

## 0. 一页结论（含默认拍板建议）

| 维度 | 决策 |
|------|------|
| 产品 | **Claude/Codex 式 AI 工作台** + 模型 HTTPS API；编排**目标**开源 Kimi Agent（现状见 TRUTH-FREEZE）；**非网盘、非自研 Agent OS 终局** |
| 边界 | **edu** = 人/班/考务/成绩真源；**Pico** = 唯一 AI 账本 + Agent + 工作台 |
| 租户 | `school_id` 校级；`membership_id` 校内用户。教师是租户成员，**不是**一人一机 |
| 部署 | **混合：默认 Standard（共享）；Dedicated 一校一单元为加价 SKU** |
| 首期 10 校 | **全部 Standard**；有书面隔离要求再开 Dedicated |
| 大文件/考试卷 | **校本地 / 校侧对象为主**；Pico 只存 **引用 + AI 过程** |
| 模型 | 默认 **Kimi API**；Standard 平台代付计量；Dedicated 可选 BYOK |
| 定价 | **基础包（含点）+ 模块加购（可再赠点）+ 阅卷独立 + 个人充值补充** |
| 点包周期 | **月度点包，月末清零（不累积）**；付费加购包可设 12 个月有效 |
| 阅卷 vs 聊天点 | **默认隔离、不可互挪** |
| 个人充值 | **允许**；校池优先，个人补；校管理员可关；单价 ≥ 校级加购点 |
| 超额默认 | **硬限阻断 + 通知校管理员**（可改降级，但不默认静默超支） |
| 计量 | 对内 token，对外「点」；bucket：日常 / 模块 / 阅卷 / 个人 |

---

## 1. 产品与系统边界

```text
                    ┌──────────────────────────────┐
                    │  教师浏览器（工作台 UI）        │
                    │  LibreChat 产品壳              │
                    └─────────────┬────────────────┘
                                  │ HTTPS
                    ┌─────────────▼────────────────┐
                    │  Pico 控制面                   │
                    │  · 鉴权（JWT principal）        │
                    │  · Task / Run / Event / 产物   │
                    │  · 配额与计费科目               │
                    │  · Agent 多步工具环             │
                    │  · OpenAI 兼容入口              │
                    └──────┬──────────────┬────────┘
                           │              │
              模型 API     │              │ 引用/只读工具
                           ▼              ▼
                    ┌────────────┐  ┌─────────────────────┐
                    │ Kimi 等    │  │ edu 业务 API         │
                    │ HTTPS API  │  │ + 校侧考试对象存储    │
                    └────────────┘  └─────────────────────┘
```

| 在 Pico | 不在 Pico |
|---------|-----------|
| AI 对话与工作台 | 学籍、排课、成绩主库 |
| 唯一 AI 账本（Task/Run/Event） | 10T 级考试原件二进制 |
| 白名单工具网关 | 默认 Shell/全域网盘 |
| 模型密钥（平台或校 BYOK） | 与 edu 双跑第二套 AI 账本 |
| 配额/点/账单聚合 | 教务审批流最终落库（edu 确认后） |

---

## 2. 逻辑架构（分层）

### 2.1 层说明

| 层 | 职责 | 当前实现要点 |
|----|------|----------------|
| **L1 体验层** | 会话、Markdown、工具展示、设置 | `apps/librechat`（中文默认） |
| **L2 API 控制面** | 鉴权、任务、流式/兼容协议、变更确认 | `services/api` FastAPI |
| **L3 编排层** | 多步 tool-calling、事件发射、超时/token 帽 | `pico_orchestrator.run_agent_loop` |
| **L4 工具网关** | 白名单、校隔离、跨校 fail-closed | `AllowlistGateway` |
| **L5 模型提供商** | Kimi / 可扩展 DeepSeek 等 | `provider.resolve_provider` |
| **L6 账本存储** | Task/Run/Event/Artifact/Change | SQL（可演进 Postgres） |
| **L7 计量计费** | 点池、科目、超额 | **方案层已定，工程分阶段** |
| **L8 集成** | edu 凭证、只读适配、回写提案 | Phase 2 合同 / Phase 3 对接 |

### 2.2 核心领域对象

```text
Principal (school_id, membership_id, scopes)
    │
    ├─ Task          用户意图容器
    │     └─ Run     一次执行
    │           └─ Event[]   有序：step / tool / message / deny
    │           └─ Artifact[]  产物（正文或 URI 引用）
    └─ ChangeProposal → 人工确认 →（edu 回写，非 Pico 静默写业务库）

BillingAccount (school)
    ├─ Wallet school 池 / module 池 / grading 池
    └─ Wallet personal (membership)
```

### 2.3 请求主路径

```text
UI 发送
  → POST /v1/chat/completions（或 /v1/tasks）
  → 校验 JWT / 代理密钥 → Principal
  → 配额预检（科目 bucket）
  → 创建 Task + Run
  → run_agent_loop（模型 + 白名单工具）
  → 写 Event；汇总 token → 扣点
  → 返回流式/完整助手消息
```

---

## 3. 部署架构

### 3.1 推荐策略：混合（成本 / 可靠 / 复杂度平衡）

| 档 | 形态 | 适用 |
|----|------|------|
| **Standard** | 共享集群 + 行级 `school_id` | 默认、大多数校 |
| **Dedicated** | **一校一 VM/主机单元**（同镜像） | 强隔离、采购要求 |
| 禁止 | 一教师一虚拟机 | 成本与复杂度不可接受 |

**校内：** 多教师共享该环境，身份为租户成员。  
**校间：** Standard 逻辑隔离；Dedicated 机/库级隔离。

### 3.2 Standard 拓扑

```text
                    LB
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     API×N        API×N        （可选异步 worker）
        │            │
        └────────────┼────────────┐
                     ▼            ▼
                 Postgres      Redis（限流/会话可选）
                     │
                     ▼
              对象存储（小附件/导出；非考试主存）
```

### 3.3 Dedicated 拓扑（一校一单元）

```text
[ 校单元 VM ]
  Pico API + Web + 本校 AI DB
  出站：Kimi API
  入站：仅校网/专线 + 平台升级通道
  挂载或旁路：校本地考试存储网关
```

### 3.4 与「考试数据本地」的部署关系

| 模式 | Pico 在哪 | 考试原件在哪 |
|------|-----------|--------------|
| 云 Standard + 校 NAS | 云 | 校本地，网关按需授权读取 |
| 校侧 Dedicated | 校机房/一体机 | 同校 NAS/盘 |
| 混合冷热 | 云或校 | 热本地、冷归档 |

**原则：TB 级原件不进 Pico 主库。**

---

## 4. 数据架构

### 4.1 三类存储

| 存储 | 内容 | 容量特征 | 责任方 |
|------|------|----------|--------|
| **AI 账本库** | Task/Run/Event/计费流水 | GB 级/校/年 | Pico |
| **业务库** | 人、班、考试元数据、成绩 | 视 edu | edu |
| **对象/文件** | 卷面、音视频、扫描件 | **TB 级（如 10T/年）** | **校本地优先** 或校侧桶 |

### 4.2 考试数据流（推荐）

```text
扫描/上传 → 校本地对象存储
           → edu 记元数据（exam_id, uri, 权限）
教师发起「阅卷/分析」
           → Pico Run + context_refs(exam_id, uri…)
           → 工具经网关拉取「本页/本题」子集
           → 结果进 Artifact + Event
           → 若改成绩：ChangeProposal → 人审 → edu 写入
```

### 4.3 引用模型（Pico 内）

```json
{
  "type": "external_object",
  "school_id": "school-a",
  "uri": "school-nas://exams/2026/mid/paper-001/page-03.png",
  "checksum": "sha256:…",
  "access": "signed_url_or_gateway",
  "ttl_seconds": 600
}
```

---

## 5. 安全与多租户

| 控制 | 要求 |
|------|------|
| 身份 | 短时 JWT；claims 含 school/membership/scopes |
| 工具 | 仅白名单；`school_scoped` 工具强制本校 |
| 跨校 | fail-closed + `auth.deny` 事件 |
| 危险能力 | Shell/File/Web/MCP **默认关**（`agents/pico.yaml`） |
| 密钥 | 模型 Key 仅服务端；BYOK 入保险柜 |
| 审计 | 唯一 AI 账本可追 Run/工具/确认 |
| 双跑 | **禁止** edu 旧 AI 与 Pico 并行记账 |

---

## 6. Agent 与模型

```text
底层 Agent ≠ 另一颗更强模型
          = 钉版本能力边界 + Kimi HTTPS API + 服务端多步工具环 + 白名单
```

| 项 | 现状/目标 |
|----|-----------|
| 钉版本 | `kimi-agent-sdk 0.0.5` / `kimi-cli 1.12.0`（pin） |
| 默认模型 | `moonshot-v1-8k`（可配置） |
| 工具示例 | `pico_echo` / `fake_edu_list_classes` / `pico_propose_change` |
| UI 接入 | OpenAI 兼容 `/v1/chat/completions` |
| 质量边界 | 同 API 则推理≈Kimi；通用 Agent 能力弱于官方全家桶；学校可控与账本更强 |

---

## 7. 集成 edu（合同级）

| 阶段 | 内容 |
|------|------|
| Phase 1 | Pico 独立；FakeEdu；不联调 |
| Phase 2 | 冻结 OpenAPI/事件/提案形状 |
| Phase 3 | 真凭证、只读适配、确认回写协调；**Pico 独占 AI 账本** |

edu → Pico：签发或换票、启动 Run、带 `context_refs`。  
Pico → edu：只读查询工具；变更仅提案，业务写在 edu 审后。

---

## 8. 定价与计量架构（纳入技术设计）

### 8.1 商业包装（对外）

```text
① 平台基础包（每校）
   · 基础功能使用权
   · 赠送校级「AI 点」月包（或年包月释放）

② 功能模块加购
   · 模块年费/月费
   · 可再赠点（入校池或模块专属池）

③ 考试阅卷（独立产品线）
   · 场次 / 卷 / 页 等
   · 阅卷专用点包（与日常对话分桶）

④ 教师个人充值（补充）
   · 个人点钱包
   · 校管理员可关或设上限
```

### 8.2 点与 token

| 对外 | 对内 |
|------|------|
| AI 点 | token（或 1 点 = N token，附件可调） |
| 剩余点、消耗明细 | Run 级 `usage` 汇总 |

### 8.3 计费科目（bucket）— 技术必建

| bucket | 用途 |
|--------|------|
| `chat_school` | 日常对话/基础工具 |
| `module_<id>` | 模块专属（可选） |
| `grading` | 阅卷 |
| `personal_<membership_id>` | 教师个人 |

### 8.4 扣费顺序（默认）

```text
1. 模块专属池（若该次 Run 归属模块）
2. 校级通用池 chat_school
3. 教师个人池
4. 仍不足 → 策略：block | notify | 引导加购
```

**阅卷默认不与 chat 混用**（可配置例外）。

### 8.5 配额对象（配置/表）

```text
SchoolPlan
  plan: standard | dedicated
  seat_limit
  modules[]
  wallets[]: { bucket, period, granted, used, hard_limit_action }
  byok_enabled
  grading_sku
```

### 8.6 与成本的关系（一校数量级，示意）

| 科目 | 数量级提示 |
|------|------------|
| 控制面 Standard 分摊 | 每月几十～几百元/校 |
| Dedicated 单元 | 每月约数百～两千元级/校 |
| 模型 token | 随活跃变化，常为敏感项 → **包量+超额** |
| 考试 10T/年存储 | **独立**对象/本地成本，不进「点」糊弄 |

### 8.7 计费在请求路径中的位置

```text
鉴权通过
  → resolve_bucket(run_kind)
  → check_wallet(school, membership, bucket, estimate)
  → 执行 Agent
  → commit_usage(actual_tokens)
  → 异步账单聚合（日/月）
```

**预检 + 实扣**，防止只记不卡。

---

## 9. 容量与可靠性（10×100）

| 项 | 目标 |
|----|------|
| 席位 | ~1000 教师；DAU 远低于峰值设计 |
| API | 无状态水平扩展；多副本 |
| DB | 先单主 + 备份；账本按校归档策略 |
| 限流 | 校级 QPS + 点余额双限 |
| 发布 | 不可变镜像；Standard 金丝雀；Dedicated 舰队滚动 |
| 备份 | 账本日备；考试原件按校本地 SLA |
| 观测 | 延迟、错误率、token 突刺、跨校 deny、钱包耗尽 |

---

## 10. 技术选型冻结（与现网一致）

| 组件 | 选型 |
|------|------|
| 控制面 | Python 3.11+ / FastAPI |
| 编排 | 服务端多步 tool loop + pin Kimi 相关版本 |
| UI | LibreChat（MIT 产品壳）+ 中文 |
| 协议 | REST + SSE；OpenAI 兼容聊天 |
| DB | SQLite（开发）→ Postgres（生产建议） |
| 部署 | Docker/单二进制镜像；Standard/Dedicated 同镜像 |

---

## 11. 分阶段落地（架构视角）

| 阶段 | 技术 | 定价相关 |
|------|------|----------|
| **P1 已做** | 独立 Pico、账本、工具环、LibreChat、兼容 API | 不阻塞；内部可记 usage |
| **P1.5** | 校级钱包表、bucket、预检扣减、管理员用量视图 | 基础包+点可试运营 |
| **P2** | edu 合同字段、context_refs | 合同与科目对齐 |
| **P3** | 真只读/确认回写 | 阅卷链路联调 |
| **P4** | Dedicated IaC、校存储网关、个人充值支付 | 模块/阅卷/个人 SKU 上线 |

---

## 12. 风险与非目标

| 非目标 | 原因 |
|--------|------|
| Pico 变网盘 | 10T 与产品边界冲突 |
| 一人一虚拟机 | 成本/运维爆炸 |
| 双 AI 账本 | 对账与责任混乱 |
| 无包量无限模型 | 成本不可控 |
| 默认开 Shell | 安全与验收风险 |

---

## 13. 原不确定项 — 架构默认建议（已选定）

> 业主若无异议，直接 **ACK** 后将本文升 `FIXED v1.0`。若要改某一条，只改该条即可。

| # | 问题 | **默认建议** | 理由（成本 / 可靠 / 复杂度） |
|---|------|--------------|------------------------------|
| 1 | 部署默认 | **混合：Standard 默认 + Dedicated 可选** | 10 校成本可控；专属只卖给愿加价/强合规的校 |
| 2 | 定价结构 | **基础包+点 / 模块 / 阅卷独立 / 个人充值补充** | 预算清晰；阅卷突刺不打穿日常包；个人补位不反客为主 |
| 3 | 点包周期 | **月度发放、月末清零** | 财务可预测、防囤积；实现简单。付费加购包可 12 个月有效作例外 |
| 4 | 阅卷 vs 聊天 | **默认隔离、不可互挪** | 账目与毛利清晰；大考不拖垮备课；合同好写 |
| 5 | 考试原件 | **校本地 / 校侧对象为主** | 10T 级成本与合规；Pico 保持引用模型 |
| 6 | 首期 10 校 | **全 Standard** | 先把配额/审计/产品跑顺，再开专属舰队 |
| 7 | 模型付费 | **平台代付+计量；Dedicated 可 BYOK** | 开户简单；敏感校有出口 |
| 8 | 超额策略 | **阻断 + 通知管理员** | 比静默超支更可控；比仅告警更少账单事故 |
| 9 | 扣费顺序 | **模块池 → 校池 → 个人** | 模块成本可归因；校统一采购优先 |
| 10 | 个人充值 | **开，但可被校关闭** | 满足积极教师；避免变成唯一收款模型 |

### 点包细则（默认）

| 包类型 | 周期 | 是否累积 | 备注 |
|--------|------|----------|------|
| 基础包赠送点 | 自然月 | **否（清零）** | 与月费对齐 |
| 模块赠送点 | 随模块订购周期 | 并入校池则随月清零；模块专属池可订购期内有效 | 吃量模块建议专属池 |
| 阅卷点包 | 场次或订购期 | 不并入聊天包 | 独立 bucket=`grading` |
| 个人充值点 | 自充值起 **12 个月** | 个人有效期内可用 | 过期作废、不退现（合同写明） |

### 对外「点」汇率（默认起点，可调价附件）

```text
1 点 = 1,000 token（输入+输出合计，或按官方权重折算后入账）
高级模型可设倍率：如 2 点 / 1k token
```

汇率放**价目附件**，代码只读配置，避免改代码调价。

### ACK 方式

业主回复：`架构默认建议 ACK` 或指出要改的编号。  
ACK 后执行：`STATUS → FIXED v1.0`，HANDOFF 标注生效。

---

## 14. 文档索引

| 文档 | 内容 |
|------|------|
| 本文 | **整体架构 + 定价总览** |
| `DEPLOY-AND-PRICING.md` | 部署形态与收费讨论细节 |
| `UNDERLYING-AGENT.md` | 底层 Agent 定义 |
| `PHASE2-CONTRACTS.md` | 与 edu 合同 |
| `SCOPE.md` | 与 edu 职责切分 |
| `MVP-3DAY.md` | Phase1 成功标准（计划变更另走升版） |
