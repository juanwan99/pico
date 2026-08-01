# Pico — 3-Day MVP Plan **v1.2（已固定）**

```
STATUS: FIXED / BINDING
VERSION: v1.2
REPO: juanwan99/pico
SUPERSEDES: v1 @ d8fee789 · v1.1 @ 5b2140b
FIXED_AT_MAIN: (see git commit of this file)
AUTHOR: Grok-Global-Control
OWNER_DIRECTION: Pico 独立开发；参考 edu；对接后置；做完再协调 edu
CODEX_INPUT: REVISE 六条 → 安全/唯一账本/CI 吸收；真连 edu 时点后移到 Integration
```

---

## 0. 前因后果（固定叙事）

### 0.1 母体

**edu-cloud**：多校教育 SaaS（成员、考试、成绩、OneFlow）。架构冻结：学校业务真源在数据库；AI 不得另立业务真源。

### 0.2 产品纠正

| 错误旧理解 | 固定正确理解 |
|------------|----------------|
| 「教师空间」= 网盘 / 5GB 文件主线 | **AI 空间** = ChatGPT / Grok / Kimi **类产品**（体验 + Agent 编排 + 产物） |
| 自研交互与 Agent 框架 | **深度对齐成熟 AI 产品 IA**；**编排目标 = 开源 Kimi Agent**（薄改；**现状见 TRUTH-FREEZE**，禁假完成） |
| 最底层自托管大模型 | **最底层 = 模型 HTTPS API**（Kimi 和/或 DeepSeek） |
| 在 AI 仓重做教务 | **业务在 edu-cloud**；Pico 提供 AI 底座，**日后对接** |
| AI 与教务同一仓抢节奏 | **Pico 独立仓、独立节奏** |

### 0.3 为何存在 pico

- AI 迭代不应被 edu 大 CI、Alembic、业务模块拖死。  
- **Pico = 唯一 AI 产品与 AI 事实账本**（Task/Run/Event/Artifact 及后续 Change/Review/Commit）。  
- edu 内旧 AI 运行时/工作台/API/worker：**对接阶段原子退役**，禁止长期双跑。  
- **开发阶段（本 MVP）不修改、不联调 edu 仓库为日常依赖。**

### 0.4 三阶段总策略（业主拍板 · 已固定）

```text
Phase 1  MVP-3D   Pico 独立交付（本文）
Phase 2  Contract  冻结对接合同（可与 D3 并行写短文）
Phase 3  Integrate 与 edu 联调 + edu 旧 AI 退役
```

| 阶段 | 管 edu 吗？ | 目标 |
|------|-------------|------|
| **Phase 1** | **不管**（只读参考） | 真 Agent + 真模型 API + 真 UI + Pico 账本 + CI |
| **Phase 2** | 只写合同 | 身份/工具/变更回写接口形状 |
| **Phase 3** | 协调 edu | 真签发、真业务工具、退役 edu AI |

---

## 1. 所有权（固定）

| 事实 | Owner |
|------|--------|
| AI Task / Run / Event / Artifact /（后续）Change·Review·Commit | **仅 Pico** |
| 学校业务（学生、考试、成绩、成员…） | **仅 edu-cloud** |
| 模型 Provider 密钥与调用 | **Pico**（API） |
| 成员身份权威 | **edu-cloud**（Phase 3 签发；Phase 1 用 **同形测试签发**） |

禁止：Pico 与 edu 各记一套 Run 账本并行服役。

---

## 2. Phase 1 成功标准（Day 3 结束 · S1–S8）

**全部满足才算 MVP PASS。**

| ID | 标准 |
|----|------|
| **S1** | **真实**模型 API 端到端（Kimi **或** DeepSeek 先通一条）；流式到 UI；密钥仅服务端。**Mock 不能代替 S1。** |
| **S2** | **已钉版本**的 Kimi Agent 在服务端跑多步工具环（非前端假进度）。 |
| **S3** | Pico DB 持久化 Task + Run + 有序 Event（+ 产物元数据）；取消/失败/成功正确；**唯一 AI 账本。** |
| **S4** | 请求身份来自 **Pico 校验的短时凭证**（claim 形状与未来 edu 签发 **一致**：iss/aud/exp/school_id/membership_id/scopes）。Phase 1 由 **Pico 测试签发器** 签发；body/prompt **不得**扩权。 |
| **S5** | 三区 UI 真接通：历史/任务、输入+流式+工具时间线、≥1 类产物；错误态诚实。 |
| **S6** | ≥2 个 **allowlist 工具**；其中 ≥1 个实现 **「未来 edu 只读工具」接口形状**，Phase 1 用 **FakeEdu 适配器 + 合成学校数据**。跨校拒绝在 **网关按 token.school_id** 执行并记 Event。（**不要求** Day 3 打通 edu 真服务。） |
| **S7** | 最小待确认：提案 → 人确认 → 审计；禁止静默当业务已写入。 |
| **S8** | **强制 CI**：CANDIDATE PR → exact-SHA CI 绿 → 独立审查 → **有人值守**合并。 |

### Phase 1 明确不做

- 依赖 edu 仓库日常联调 / Preview 必达  
- 网盘产品全文、像素抄品牌  
- 自研 Agent 框架  
- 默认自托管 GPU 推理  
- 在 edu 合并 AI 代码（除 Phase 3）  
- 无人值守合并 main  

### Phase 3 才做的（不进 S1–S8）

- edu **真**签发 Pico 凭证  
- FakeEdu → **真** edu 只读 API  
- 变更回写学校库  
- edu 旧 AI **原子退役**与工作台跳转/嵌入 Pico  

---

## 3. Agent 安全（固定 · 吸收 Codex #4）

非测试 Agent 运行前必须：

| 能力 | 状态 |
|------|------|
| Shell / 主机 File / Web / MCP / 任意工具 | **关闭** |
| 仅 Pico allowlist 工具 | **开启** |

- 工具调用 **服务端拦截**，仅白名单可执行。  
- **钉住的** SDK/runtime **无法证明**上述边界 → **MVP BLOCKED**（禁止另起自研 Agent 框架凑数）。

---

## 4. 对接合同（Phase 2 · 形状在 Phase 1 就冻结）

Phase 1 结束前（或 D3 并行）落盘短文，**不实现 edu 侧**：

| 合同文件 | 内容 |
|----------|------|
| `docs/contracts/delegated-auth.md` | claim 字段、签名、TTL、拒绝码（与 S4 一致） |
| `docs/contracts/tools.md` | 工具名、入参/出参、跨校 403 语义、幂等 |
| `docs/contracts/ai-facts.md` | Task/Run/Event/Artifact 字段 |
| `docs/contracts/change-handoff.md` | 提案 → edu Review/Commit 的未来边界（可先接口级） |

**原则：** Phase 1 实现 **遵从合同**；Phase 3 **只换适配器与签发方**，不推翻协议。

---

## 5. 架构（Phase 1）

```text
Pico Web (Vue 3 + Vite)
    │
Pico API + 凭证校验（测试签发 / 未来 edu 签发同形）
    │
Orchestrator: Kimi Agent（版本钉死）+ allowlist 网关
    ├── Model HTTPS API (Kimi | DeepSeek)
    └── Tools: FakeEdu 只读 + 其他白名单
    │
Pico DB ── Task / Run / Event / Artifact   ← 唯一 AI 真源
```

参考 edu：只读抄 IA（三栏、待确认）、事件命名习惯；**不双写 edu AI 表。**

---

## 6. D1 开工前冻结（并行写码前必须提交）

| 项 | 固定值 |
|----|--------|
| 语言 | **Python 3.11+**（API/编排） |
| 前端 | **Vue 3 + Vite** |
| Agent | **lock 文件钉死** Kimi Agent SDK/runtime 的 version 或 commit |
| 主模型 | **Kimi API**（无 key 则停表；DeepSeek 仅当 Kimi 不可用且仍为真 API） |
| 花费 | 单 Run 最大时长、最大 token、有限重试（防夜间刷爆） |
| 合同草稿 | §4 四份至少骨架入库 |

---

## 7. 三日节奏（含夜间）

| 日 | 有人 | 夜间（低风险） | 出口 |
|----|------|----------------|------|
| **D1** | §6 冻结；脚手架；Agent 钉版本；安全边界证明；模型流式 hello；测试签发 | 依赖/单测；**有界**重试 | 钉死 + 流式冒烟 + 安全证明 |
| **D2** | 落库；三栏接真流；工具时间线；FakeEdu 工具 | 集成/取消/超时（有 token/时间帽） | UI ← DB Event |
| **D3** | 跨校 Event；待确认；合同补全；**CANDIDATE**；CI；审查；**值守合并**；DEMO.md | 全量复跑；不合并 | **S1–S8** 在 main |

**并行（冻结后）：** W1 Agent+Provider+网关 · W2 API+DB+鉴权 · W3 UI。  
**串行热点：** schema、鉴权中间件、allowlist。  

**夜间禁止：** 合并 main、改 Secrets、生产发布、无上限打模型。

---

## 8. CI / 合并门（固定）

```text
CANDIDATE PR（exact SHA）
  → GitHub Actions CI 绿
  → 独立审查 PASS
  → 有人值守 merge → main
```

S1 的真 provider 证据可走带 secret 的 job 或值守命令，**不得**用纯 mock 关闭 S1。

---

## 9. 演示脚本（Phase 1）

1. 用 **测试签发器** 取 School A membership 凭证。  
2. 建任务；见模型流式 + Agent 步骤。  
3. 调用 FakeEdu 只读工具；时间线有 Event。  
4. 产物区有一文/表。  
5. 伪造 School B 工具上下文 → **拒绝 + Event**。  
6. 提案 → UI 确认 → 审计行。  
7. 取消 Run → 终态正确。  

（Phase 3 演示再换成 edu 真签发 + 真 API + edu AI 已退役。）

---

## 10. Phase 3 对接清单（开发完再协调 · 预告）

1. edu 实现签发（与 `delegated-auth.md` 一致）。  
2. FakeEdu → Edu 适配器；跨校 403 在 edu 再测一枪。  
3. 变更提案回写路径。  
4. edu 工作台改为打开/嵌入 Pico。  
5. **原子** tombstone edu AI runtime/workbench/API/worker；禁止并行。  
6. 独立审查 + CI + 值守合并（edu 侧与 pico 侧各按门禁）。

---

## 11. 风险与停止

| 风险 | 动作 |
|------|------|
| 钉不住 Agent 或关不掉 Shell/File/Web/MCP | **BLOCKED** |
| 无真模型 API Key | **停表**，不算 S1 |
| 范围膨胀回 edu 联调 | 拒；推 Phase 3 |
| 合同不写就合并 | 拒；D3 出口缺 Phase 2 骨架 |

---

## 12. 与历史版本关系

| 版 | 状态 |
|----|------|
| v1 | 初稿；含「先本地再对齐」模糊 |
| v1.1 | Codex 六条；**D3 真连 edu** 过紧 |
| **v1.2** | **已固定**：独立 Phase 1 + 合同形状 + 对接后置；安全/唯一账本/CI 保留 |

---

## 13. 执行授权

```text
PLAN STATUS: FIXED
NEXT: D1 冻结清单落地 + 脚手架
变更本计划：须新版本 v1.3+ 并写明 delta（禁止静默改 S1–S8）
```
