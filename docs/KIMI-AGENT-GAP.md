# 开源 Kimi Agent 真接差距清单（只读 · 正本清源阶段）

```
DOC: docs/KIMI-AGENT-GAP.md
STATUS: NEXT-PHASE inventory（非运行时选型备选清单；integration NOT started）
DATE: 2026-08-01
TRUTH: docs/TRUTH-FREEZE.md O1–O4 · docs/WHAT-IS-PICO.md §4
SCOPE: 只读盘点；不切换生产运行时；不预埋其它 harness
```

---

## 0. 结论摘要

| 问题 | 答案 |
|------|------|
| 目标运行时 | **开源 Kimi Agent**（唯一路径） |
| 今日执行核 | `pico_orchestrator.runner.run_agent_loop`（AsyncOpenAI 工具环） |
| pin 包 | `kimi-agent-sdk==0.0.5`、`kimi-cli==1.12.0` |
| pin 实际用途 | 版本检查 + `kimi_cli.agentspec.load_agent_spec` 读 yaml 做危险工具关断证明 |
| 是否主路径调用 SDK 跑多步 | **否** |
| 本阶段是否换核 | **否**（业主要求：先正本清源；换核另阶段 + 核验） |

---

## 1. 调用链（现状）

```text
LibreChat / 客户端
  → Pico API (openai_compat / run_service)
      → run_agent_loop()     ← 真执行
          → AsyncOpenAI(base_url=Kimi…)
          → AllowlistGateway 工具
      → 账本 Event / Artifact / 终态

并行（非执行核）:
  startup / security_proof
      → assert_dangerous_tools_off(pico.yaml)
          → kimi_cli.agentspec.load_agent_spec
  CI / check_agent_pin
      → pins.assert_pins()
```

**入口文件（归位时改接线）：**

| 路径 | 现状 |
|------|------|
| `run_service.py` | 任务/Run 执行 → **`run_agent_loop`** |
| `openai_compat.py` **pico-agent**（非流式/流式） | → **`run_agent_loop`** |
| `openai_compat.py` **直连模型**（默认 chat） | → **`stream_chat` / 直连补全**，**不**走 `run_agent_loop` |
| `runner.py` | 过渡多步实现体 |

---

## 2. 已有「Kimi 相关」资产（可复用 vs 装饰）

| 资产 | 角色 | 归位时 |
|------|------|--------|
| `KIMI_API_KEY` / provider | 模型 HTTPS | **保留** |
| `agents/pico.yaml` + `system.md` | 角色与危险工具 exclude 列表 | 可能迁到真 Agent 配置 |
| `safety.py` | 启动证明 tools 不含 Shell/File/Web | 真接后改证「运行时配置」或保留双证 |
| `pins.py` | 包版本锁 | 真接后锁**实际跑的**包/版本 |
| `runner.py` | 过渡执行 | **真接后默认移除生产路径**；是否短暂 dual-run **禁止预写进方案**，须业主书面再议 |
| allowlist gateway / 账本 emit | Pico 控制面 | **必须保留**；Agent 事件映射进来 |

---

## 3. 真接完成定义（下一阶段验收 · 非本阶段宣称）

必须同时满足：

1. 生产多步 Run（如 `pico-agent`）主路径 **进入开源 Kimi Agent 运行时**（进程内 SDK 或受控子进程，须可审计）。  
2. 工具仅经 **Pico 白名单网关**（或等价强制策略），Host Shell/File/Web 默认关。  
3. 步骤/工具/终态 **写入 Pico 账本**（Event 可追踪）。  
4. 停止/取消与现控制面语义兼容（或文档化差异 + 测试）。  
5. **禁止**仅靠 `assert_pins()` 绿或 yaml 存在宣称「已接入」。  
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
| G1 | 无运行时适配层 | 没有 `KimiAgentRuntime.run(prompt) -> events` 适配器 |
| G2 | 事件模型未映射 | Agent 事件 → Pico `run.*` / tool 事件表未设计落地 |
| G3 | 取消/超时 | 现 cancel 挂在自研环；真接需同等契约 |
| G4 | 技能快照 | Skill 与工具交集现挂 runner；需挂真运行时 |
| G5 | 发行源与可重复安装 | KA-0 已证公网 PyPI 可装 pin；仍未固定 wheel hash / 内部镜像，见 §7 |
| G6 | 测试 | 大量单测 mock `run_agent_loop`；归位需新契约测 |
| G7 | 名实 | 历史文档/注释已清一波；归位 PR 须再扫 |

---

## 5. 建议实施切片（仅规划 · 本阶段不执行）

```text
切片 KA-0  固定可安装的 Kimi Agent 发行物 + 最小 hello（非生产）
切片 KA-1  适配器：单次多步 → 账本事件（fake/录制测）
切片 KA-2  **迁移门**（临时开关仅用于切流；默认仍过渡环；**不是**长期双运行时产品）
切片 KA-3  生产默认切真运行时 + 取消/技能回归；**关闭**过渡环生产入口
切片 KA-4  卸装饰依赖或降级；TRUTH-FREEZE 升版 O2=已接入；**生产无 optional fallback runner**
```

**本正本清源阶段在 KA-0 之前结束。**

---

## 6. 明确不在本阶段做

- 切换生产默认运行时  
- 预埋 Pi/OpenCode  
- 删除 `runner.py` 导致现网不可用  
- 宣称 S2「已钉版本 Kimi Agent 跑多步」为已完成  

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
