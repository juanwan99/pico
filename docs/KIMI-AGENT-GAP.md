# 开源 Kimi Agent 真接差距清单（只读 · 正本清源阶段）

```
DOC: docs/KIMI-AGENT-GAP.md
STATUS: LIVING inventory（唯一目标路径 = Kimi Agent；**生产默认已切** · #278 · 全球 product PASS 未宣称）
DATE: 2026-08-05
TRUTH: docs/TRUTH-FREEZE.md O1–O4 · docs/WHAT-IS-PICO.md §4 · docs/STATE-NOW.md
SCOPE: 差距与切片状态；不切换生产默认运行时；不预埋其它 harness / Plan B
```

日常 health、限流与测试凭据纪律见 [KIMI-OPERATIONS.md](./KIMI-OPERATIONS.md)。

---

## 0. 结论摘要

| 问题 | 答案 |
|------|------|
| 目标运行时 | **开源 Kimi Agent**（唯一路径） |
| 今日**默认**执行核（生产） | `PICO_KIMI_AGENT_RUNTIME=1` + **空 canary** → **`run_kimi_agent`**（scope=all · #278） |
| canary 限制模式 | 非空 joint 名单时仅名单进 KA；RUNTIME=0 或 emergency → `run_agent_loop` |
| pin 包 | `kimi-agent-sdk==0.0.5`、`kimi-cli==1.12.0` |
| pin 实际用途（默认路径） | 版本检查 + `kimi_cli.agentspec.load_agent_spec` 读 yaml 做危险工具关断证明 |
| 是否**默认**主路径调用 SDK 跑多步 | **是**（生产 scope=all 时；见 #278 TEST REPORT） |
| 生产是否已换核 / 已开 flag | **是（ENGINEERING）**：#278 已授权、部署并复证 `scope=all`；全球 product PASS 未宣称 |
| 是否可宣称「已接入完成」 | **否**（见 §3 完成定义；mock 测 ≠ 真接） |

**切片进度（代码合 main ≠ 产品 PASS）：**

| 切片 | 状态 | 证据 |
|------|------|------|
| KA-0 可安装/入口 | **DONE（摸底）** | #137 |
| KA-1 Wire→账本契约 | **DONE（契约+单测）** | #140 |
| KA-2 flag-only Session | **DONE（默认 OFF）** | #145 · 见 §9 |
| KA-3 生产默认切核 | **ENGINEERING DONE** | #278 · AUTH #170 · tip `5baf0cf…` · scope=all |
| KA-4 卸过渡入口 / 升 TRUTH O2 | **部分** | loop 文件仍在；默认路径不可达；TRUTH O2 可升「默认已切 · PASS 未宣称」 |

---

## 1. 调用链（现状 · post-KA-3）

```text
LibreChat / 客户端
  → Pico API (openai_compat / run_service)
      → run_agent_runtime(use_kimi_agent=settings.pico_kimi_agent_runtime)
           │
           ├─ false / emergency 显式回滚
           │    → run_agent_loop()     ← 过渡回滚能力，非生产默认
           │         → AsyncOpenAI(base_url=Kimi…)
           │         → AllowlistGateway 工具
           │
           └─ true（生产默认空 canary=all；或 membership 命中非空 canary）
                → run_kimi_agent()     ← 生产默认路径（§9）
                     → Session.prompt(merge_wire_messages=True)
                     → KimiWireEventAdapter → 账本 emit
                     → 工具仅 kimi_tools → AllowlistGateway
      → 账本 Event / Artifact / 终态

并行（非执行核）:
  startup / security_proof
      → assert_dangerous_tools_off(pico.yaml | pico-kimi-runtime.yaml)
          → kimi_cli.agentspec.load_agent_spec
  CI / check_agent_pin
      → pins.assert_pins()
```

**入口文件：**

| 路径 | 现状 |
|------|------|
| `run_service.py` | → **`run_agent_runtime`**（生产 runtime=1、空 canary → Kimi Agent） |
| `openai_compat.py` **pico-agent**（非流式/流式） | → **`run_agent_runtime`**（同上） |
| `openai_compat.py` **直连模型**（默认 chat） | → **`stream_chat` / 直连补全**，**不**走 agent runtime |
| `runtime.py` | 选择器；所选路径才延迟 import 对应运行时 |
| `runner.py` | 过渡多步实现体（**软保留**；仅 runtime=0 / emergency） |
| `kimi_runtime.py` / `kimi_adapter.py` / `kimi_tools.py` | 生产默认 Kimi Agent 路径；工具仍只经 Pico gateway |

---

## 2. 已有「Kimi 相关」资产（可复用 vs 装饰）

| 资产 | 角色 | 归位时 |
|------|------|--------|
| `KIMI_API_KEY` / provider | 模型 HTTPS | **保留** |
| `agents/pico.yaml` + `system.md` | 角色与危险工具 exclude（旧环/安全证明） | 可能与 runtime agent 配置对齐 |
| `agents/pico-kimi-runtime.yaml` | KA-2 Session 专用 agent；仅 gateway wrapper 工具 | 真接默认后可能升为唯一 agent 文件 |
| `safety.py` | 启动证明 tools 不含 Shell/File/Web | 真接后改证「运行时配置」或保留双证 |
| `pins.py` | 包版本锁 | 真接后锁**实际跑的**包/版本 |
| `runner.py` | 过渡执行 | **KA-3/4 后默认移除生产路径**；是否短暂 dual-run **禁止预写**，须业主书面再议 |
| allowlist gateway / 账本 emit | Pico 控制面 | **必须保留**；Agent 事件映射进来 |

---

## 3. 真接完成定义（验收 · 禁止提前宣称）

必须同时满足：

1. 生产多步 Run（如 `pico-agent`）主路径 **进入开源 Kimi Agent 运行时**（进程内 SDK 或受控子进程，须可审计）。  
2. 工具仅经 **Pico 白名单网关**（或等价强制策略），Host Shell/File/Web 默认关。  
3. 步骤/工具/终态 **写入 Pico 账本**（Event 可追踪）。  
4. 停止/取消与现控制面语义兼容（或文档化差异 + 测试）。  
5. **禁止**仅靠 `assert_pins()` 绿、yaml 存在、或 **KA-2 flag 代码合 main** 宣称「已接入」。  
6. 文档 TRUTH-FREEZE / WHAT-IS-PICO **O2 现状句**更新为已接入，并升冻结小版本。  
7. **exact-SHA 验收证据（必须）：**  
   - 实际加载的 Kimi Agent runtime/发行物身份（版本或 commit）  
   - 路由断言：`run_service` + `openai_compat` 的 **pico-agent** 两入口进入真运行时；**direct chat** 仍不误走 Agent（除非产品改口径）  
   - 白名单 / 账本事件 / 取消 的集成测试挂在该 SHA  
   - 生产 `## TEST REPORT`（该 SHA）；**不得**用 pin、单文件 CI 或 yaml 代替  
8. **生产路径不存在可选过渡 `run_agent_loop` fallback**（dual-run 若曾用于迁移，须在 DONE 前关闭）。

---

## 4. 已知缺口（工程）

| ID | 缺口 | 说明 |
|----|------|------|
| G1 | 运行时适配层默认启用 | **已关**：#278 生产 `scope=all`；保留显式回滚能力，见 §9 |
| G2 | 事件映射待真实流验证 | KA-2 mock Session + Pico DB 路由已测；尚无获准凭据下的真实 Wire 集成证据 |
| G3 | 取消/超时待真实流验证 | KA-2 已实现 `is_cancelled → session.cancel` 与 timeout，mock 测通过；真实 provider 仍待测 |
| G4 | 技能快照 | Skill 与工具交集现挂 runner；需挂真运行时 |
| G5 | 发行源与可重复安装 | KA-0 已证公网 PyPI 可装 pin；仍未固定 wheel hash / 内部镜像，见 §7 |
| G6 | 测试 | 大量单测 mock `run_agent_loop`；归位需新契约测 |
| G7 | 名实 | 活动文档须持续扫；**禁止** harness「可替换多运行时」叙事回潮（见 #121 拒合） |

---

## 5. 实施切片（状态）

```text
切片 KA-0  固定可安装的 Kimi Agent 发行物 + 入口探测（非生产）     ✅ #137
切片 KA-1  适配器：Wire → 账本事件（契约 + 无密钥单测）           ✅ #140
切片 KA-2  flag-only Session 路径（默认 OFF；非长期双核产品）     ✅ #145
切片 KA-3  生产默认切真运行时 + 取消/技能回归；关闭过渡环默认入口      ✅ #278
切片 KA-4  卸装饰依赖或降级；TRUTH-FREEZE 升版 O2=已接入         ⏳
```

**正本清源文档阶段**已收口目标句；KA-3 工程默认路径已完成，KA-4 采用软收口：
不删除 `runner.py`，但默认配置不得静默进入过渡环。全球 product PASS 仍未宣称。

---

## 6. 明确不做（现行）

- 切换生产默认运行时 / 生产 `PICO_KIMI_AGENT_RUNTIME=1`（无授权）  
- 预埋 Pi / OpenCode / 「可替换 harness」多运行时真源（**#121 拒合**）  
- 删除 `runner.py` 导致现网不可用  
- 宣称 S2「已钉版本 Kimi Agent 跑多步」或「编排已接入完成」  
- 用日用修复（chat/stop）证明 O1 已完成（见 TRUTH-FREEZE O5）  

---

## 7. KA-0 可安装性与入口探测（2026-08-01）

### 7.1 结论

**结果：YELLOW（可合并的摸底结果，不是产品 PASS）。** 两个仓库 pin 均可从
**公网 PyPI** 安装，不需要私有源；SDK import、CLI 入口和 Pico agent spec 解析通过。
在不提供密钥、不读取操作员现有配置的隔离环境中，`hello` 已进入 SDK/CLI 运行入口，
随后因没有配置 LLM 而停止；因此本切片**没有证明一次真实模型回复成功**，更没有证明
Pico 生产路径已接入。

```
deployment: NONE
production runtime switch: NONE
run_agent_loop change: NONE
LibreChat wiring: NONE
```

### 7.2 安装证据

探测环境：Linux x86_64、CPython `3.12.13`、`uv 0.11.6`，使用全新的临时 venv；
命令显式把默认 index 设为 `https://pypi.org/simple`，未使用私有 index：

```bash
uv venv --python 3.12 /tmp/pico-ka0-venv
uv pip install \
  --python /tmp/pico-ka0-venv/bin/python \
  --no-cache \
  --default-index https://pypi.org/simple \
  'kimi-agent-sdk==0.0.5' \
  'kimi-cli==1.12.0'
```

解析并安装成功：`kimi-agent-sdk==0.0.5`、`kimi-cli==1.12.0`；SDK 元数据约束为
`kimi-cli>=1.12.0,<1.13.0`，与仓库 pin 相容。该次解析共安装 121 个包，说明运行时依赖面
较大；后续生产归位前仍应固定 wheel hash 或可信镜像，而不能把「本机装成功」当作供应链锁定。
两个发行物要求 Python `>=3.12`。

发行物元数据给出的 SDK 上游为
`https://github.com/MoonshotAI/kimi-agent-sdk`；`kimi-cli` 暴露 `kimi` 与 `kimi-cli`
两个 console script。本切片没有从 Git 仓库或私有包源安装。

### 7.3 API / CLI 最小探测

以下无密钥探测通过：

- `import kimi_agent_sdk`、`import kimi_cli`；安装版本分别为 `0.0.5`、`1.12.0`。
- `load_agent_spec(Path("services/orchestrator/agents/pico.yaml"))` 返回
  `ResolvedAgentSpec(name="pico", tools=[])`；此 API 要求 `Path`，传字符串会触发
  `AttributeError`。
- SDK 公共运行入口存在：高层异步生成器 `kimi_agent_sdk.prompt(...)`，以及低层
  `await kimi_agent_sdk.Session.create(...)` / `session.prompt(...)`。
- `kimi --version` 输出 `kimi, version 1.12.0`；`kimi --help` 可用，支持
  `--prompt`、`--print`、`--agent-file` 等运行参数。

隔离的 `hello` 使用空 `HOME` / `XDG_CONFIG_HOME`，明确不借用现有登录态或密钥：

```bash
# SDK：prompt("hello", agent_file=Path(".../pico.yaml"), max_steps_per_turn=1)
# 结果：进入 kimi_cli 运行栈后抛出 kimi_cli.soul.LLMNotSet: LLM not set（exit 1）

kimi --print --final-message-only \
  --prompt hello \
  --agent-file services/orchestrator/agents/pico.yaml
# 结果：输出 "LLM not set"；注意 CLI 1.12.0 在此失败场景仍返回 exit 0
```

所以可安装性与程序入口已确认；真正的模型 `hello` 仍需下一切片在获准的测试凭据与
provider 配置下验证。适配器还必须显式处理 `LLMNotSet`，不能只依赖 CLI 进程退出码判成成功。
本结果没有修改 `services/orchestrator/pico_orchestrator/runner.py`，也没有接线 LibreChat、
开启生产开关、删除 runner 或预埋其它 harness。

---

## 8. KA-1 适配契约与骨架（2026-08-01）

### 8.1 选择与边界

账本适配采用低层 `Session.prompt(..., merge_wire_messages=True)` 的 `WireMessage` 流。
高层 `kimi_agent_sdk.prompt(...)` 只产出聚合后的 `Message`，适合简单调用，但会丢失
`TurnBegin`、`StepBegin`、工具结果和中断等账本所需边界，因此**不作为 Pico 账本真接入口**。

KA-1 新增 `pico_orchestrator.kimi_adapter.KimiWireEventAdapter`：它是纯 mapper，只把一个
已合并的 Wire 消息转换为零个或多个 `{type, payload}`，不创建 `Session`、不调模型、
不运行工具、不写数据库。调用方后续把结果逐条交给现有 `append_event` emitter，数据库
继续负责 `run_id + seq` 的顺序和唯一性。

```
# 以下边界描述的是 **KA-1 合入当时**（#140）；KA-2（#145）已接线 selector + flag。
deployment: NONE
production runtime switch: NONE
run_service/openai_compat wiring: NONE   # KA-1 当时；现经 run_agent_runtime，见 §1/§9
feature flag: NONE                       # KA-1 当时；现有 PICO_KIMI_AGENT_RUNTIME 默认 0
run_agent_loop change: NONE
```

### 8.2 Wire → Pico 事件映射

| Kimi SDK / Wire 输入 | Pico 账本输出 | 关键 payload / 规则 |
|---|---|---|
| `TurnBegin` | `run.status` | `status=running`, `runtime=kimi-agent`；不重复存一份 prompt |
| `StepBegin(n)` | `agent.step` | `step=n`, `phase=model` |
| `TextPart` | `message.delta` | `text` 原样增量写入，空文本忽略 |
| `ThinkPart` | **不落账** | 禁止持久化私有推理 / chain-of-thought |
| `StatusUpdate` | `run.usage` | step 级 input/output/cache/total、`context_usage`、`message_id`；标 `scope=step`，不得误当累计值 |
| 已合并 `ToolCall` | `tool.call` | `tool`, JSON object `arguments`, `call_id`；坏 JSON / 非 object fail closed |
| `ToolCallPart` | **契约错误** | 表示调用方漏设 `merge_wire_messages=True`，禁止用残缺参数落账 |
| `ToolResult` | `tool.result` | 用 `call_id` 关联前置 call；`tool`, `ok`, `result`, `message`；孤立 result fail closed |
| `ApprovalRequest` | `tool.approval_required` | `request_id`, `call_id`, `sender`, `action`, `description`；当前无审批控制面，后续执行层必须 reject/fail closed，禁止 `yolo` 放行 |
| `ApprovalResponse` | `tool.approval_resolved` | `request_id`, `response`，仅作审计 |
| `CompactionBegin/End` | `agent.step` | `phase=compaction.begin/end` |
| `StepInterrupted` | `agent.step` | `phase=interrupted`；本事件本身不猜测 cancelled 还是 failed |
| `TurnEnd` | `run.status` | 无未完成 tool call 时唯一终态 `succeeded` |
| `SubagentEvent` | **契约错误** | Pico agent spec 已关闭 `Task`；出现即 fail closed，不递归执行 |
| 未知 Wire 类型 | **契约错误** | pin 升级后先补映射与测试，禁止静默丢审计事件 |

工具 call/result 必须同 `call_id` 配对，且 `tool.call` 永远先于 `tool.result`。一个 turn
只能有一个 `TurnBegin` 和一个终态；`TurnEnd` 后继续收到消息、重复 call id、未完成 call
均为契约错误。`KimiWireEventAdapter` 不记录 SDK 配置、provider secret 或操作员环境。

### 8.3 执行层终态与取消契约（KA-2/KA-3 实现）

KA-1 不实现执行层，但固定以下调用方责任，避免后续把 Wire 事件误当完整运行时：

1. 创建 `Session` 后并发观察 Pico `is_cancelled()`；命中时调用 `session.cancel()`。
2. `RunCancelled` 或已确认的 Pico cancel → 唯一 `run.status {status=cancelled}`。
3. `LLMNotSet` → `run.error {code=model.unconfigured}`，随后唯一 failed 终态。
4. `MaxStepsReached` → `run.error {code=kimi.max_steps}`，随后 failed。
5. provider / SDK / mapper 契约异常 → 安全化 `run.error`，随后 failed；不得把密钥、完整
   provider 响应或堆栈写进用户可见 payload。
6. 终态必须 exactly once；`StepInterrupted` 仅提供过程证据，不能自行决定终态。

### 8.4 工具安全契约

事件转换**不等于**工具隔离。真接执行层必须只把 Pico `AllowlistGateway` 包装成 Kimi
可调用工具，并继续携带 `Principal`；`agents/pico.yaml` 的 Host Shell/File/Web/MCP/Task
关闭证明仍是硬门禁。任何未经过 Pico gateway 的 `ToolCall` 都不得执行。KA-1 没有注册
Kimi host tool，也没有给生产代码增加 fallback、dual-run 或 feature 开关。

### 8.5 无密钥单测

`tests/unit/test_kimi_adapter.py` 直接构造 pin 版本的 Wire 类型，不创建 `Session`、不访问
网络或密钥，覆盖：正常 turn 顺序、call/result 关联、step usage、思考内容不落账、残缺
tool part / 非法参数 / 孤立 result / 未完成 call 的 fail-closed 行为。这只能证明 mapper
契约，**不能**证明 Kimi Agent 已接入或产品 PASS。

---

## 9. KA-3 后的 Kimi Session 默认路径（2026-08-05）

### 9.1 开关与路由

两级门禁为：

```dotenv
PICO_KIMI_AGENT_RUNTIME=0
PICO_KIMI_AGENT_CANARY_MEMBERSHIP_IDS=
```

代码/示例配置仍 fail-safe 默认 `False`；生产依据 #170/#278 授权显式设为 `1`，并以
**有意空 canary** 表示全员。非空但解析不出合法联合键的配置 fail-closed 为
`scope=canary` 且无人命中，不能误变成全员。`run_service`、OpenAI-compatible 非流式
`pico-agent`、流式 `pico-agent` 三处统一调用 `run_agent_runtime(...)`：

| flag | 执行路径 |
|---|---|
| 总闸未设置 / `0` / false | 全部主体走原 `run_agent_loop(...)`，参数与事件处理不变 |
| 总闸 `1` + 有意空 allowlist（生产默认） | 全部主体走 `run_kimi_agent(...)` |
| 总闸 `1` + 非空 canary 且 membership 未命中 | 该主体走 `run_agent_loop(...)` |
| 总闸 `1` + membership 命中 | `run_kimi_agent(...)` → `Session.prompt(..., merge_wire_messages=True)` → `KimiWireEventAdapter` → 原 `emit/append_event` |

Direct-chat 模型仍走 `stream_chat`，不受此门禁影响。selector 对未命中主体不导入或创建
Kimi Session；KA-3A 没有 fallback/dual-run：选中的路径失败就按该路径失败，不暗中重跑另一核。

```
deployment: #278
production flag value: 1 / ON (authorized)
production default runtime: run_kimi_agent (scope=all)
runner deletion: NONE
product PASS: NOT CLAIMED
```

### 9.2 Session 配置与 Wire 落账

flag 开启时，执行层用服务端 Kimi provider 构造内存 `Config`，创建隔离临时 work dir 与
空 skills dir，显式传入：

- `agent_file=agents/pico-kimi-runtime.yaml`
- `yolo=False`
- `mcp_configs=[]`
- `max_steps_per_turn` / retry / timeout 来自现有 `RunCaps`
- `merge_wire_messages=True`

Wire 消息逐条交给 KA-1 mapper，再逐条调用现有 emitter；`TextPart` 同时聚合成
`RunResult.final_text`。step usage 在账本保留原值并增加 `cumulative_*` 跨 step 累计，
累计 `total_tokens` 超过现有 Run cap 时取消 Session 并诚实 failed；Artifact 班级表与
change proposal 继续回到现有终态处理。
没有配置 Kimi key、step cap、timeout、mapper 契约错误与 SDK/provider 错误均输出安全化
`run.error` + failed 终态；不会把 key 或完整 provider 响应写账。

### 9.3 工具只能经过 AllowlistGateway

新 agent spec **没有** Kimi Shell/File/Web/MCP/Task，只列出
`pico_orchestrator.kimi_tools:*` 包装器。执行每个 turn 前创建
`build_default_gateway(artifact_store).restricted_to(caps.allowed_tools)`，再把 verified
`Principal` 与 gateway 绑定到 request/task-local context。每个 Kimi callable 的唯一实现是：

```text
typed args → AllowlistGateway.invoke(principal, tool_name, args) → ToolOk / ToolError
```

因此未在 global allowlist 或当前 skill intersection 内的调用 fail closed；没有直接调用
工具 handler 的旁路。Host 危险工具仍列入 `exclude_tools`，subagent 与 MCP 都为空/关闭。
`tenant.cross_school` gateway 拒绝会额外写与旧环对等的 `auth.deny`；`ApprovalRequest`
会落审计事件并立即 reject，因为 KA-2 尚无 Pico 审批控制面。

### 9.4 取消与终态

Session 运行期间有独立 watcher 轮询原 `is_cancelled()`：命中后调用 `session.cancel()`；
SDK `RunCancelled` 映射为唯一 `run.status=cancelled`。外层 task cancellation 也先调用
`session.cancel()` 再向上传播。timeout 与 token cap fail closed；`TurnEnd` 才能形成
succeeded，流结束却没有 `TurnEnd` 记为 failed。

### 9.5 无密钥测试与剩余边界

- selector 单测：代码默认/false 只调旧 `run_agent_loop`；生产授权配置 true+allow_all
  只调 Kimi path；emergency 显式强制旧环。
- mock Session 单测：断言 `merge_wire_messages=True`、`yolo=False`、无 MCP，Wire 事件经
  adapter 落账，不访问网络。
- cancel 单测：ledger cancel → `session.cancel()` → cancelled exactly once。
- gateway wrapper 单测：只有 `AllowlistGateway.invoke` 能产出工具成功结果。
- API/DB 集成测：同一 `pico-agent` 入口在 flag false/true 时分别命中旧/Kimi mock 路径。
- security 测：flagged agent 只暴露 gateway wrapper，危险 host tools 全部关闭。

KA-2 的历史边界已由 #278 的生产默认切核与 TEST REPORT 前进。保留边界包括 fresh
全产品登录态复审、真实 in-flight 取消竞态与全球 product PASS；不得把工程默认路径
完成扩写成全球产品完成。
