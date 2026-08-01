# 开源 Kimi Agent 真接差距清单（只读 · 正本清源阶段）

```
DOC: docs/KIMI-AGENT-GAP.md
STATUS: BINDING inventory for next phase (integration NOT started here)
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

**入口文件（保留，归位时改接线）：**

- `services/api/app/run_service.py` — 调 `run_agent_loop`
- `services/api/app/openai_compat.py` — 直连/agent 路径调 `run_agent_loop`
- `services/orchestrator/pico_orchestrator/runner.py` — 过渡实现体

---

## 2. 已有「Kimi 相关」资产（可复用 vs 装饰）

| 资产 | 角色 | 归位时 |
|------|------|--------|
| `KIMI_API_KEY` / provider | 模型 HTTPS | **保留** |
| `agents/pico.yaml` + `system.md` | 角色与危险工具 exclude 列表 | 可能迁到真 Agent 配置 |
| `safety.py` | 启动证明 tools 不含 Shell/File/Web | 真接后改证「运行时配置」或保留双证 |
| `pins.py` | 包版本锁 | 真接后锁**实际跑的**包/版本 |
| `runner.py` | 过渡执行 | **替换或降为 fallback（仅业主再授权）** |
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

---

## 4. 已知缺口（工程）

| ID | 缺口 | 说明 |
|----|------|------|
| G1 | 无运行时适配层 | 没有 `KimiAgentRuntime.run(prompt) -> events` 适配器 |
| G2 | 事件模型未映射 | Agent 事件 → Pico `run.*` / tool 事件表未设计落地 |
| G3 | 取消/超时 | 现 cancel 挂在自研环；真接需同等契约 |
| G4 | 技能快照 | Skill 与工具交集现挂 runner；需挂真运行时 |
| G5 | 包可安装性/文档 | 冻结环境未必能从公网 PyPI 拉到 pin（归位前要固定安装源） |
| G6 | 测试 | 大量单测 mock `run_agent_loop`；归位需新契约测 |
| G7 | 名实 | 历史文档/注释已清一波；归位 PR 须再扫 |

---

## 5. 建议实施切片（仅规划 · 本阶段不执行）

```text
切片 KA-0  固定可安装的 Kimi Agent 发行物 + 最小 hello（非生产）
切片 KA-1  适配器：单次多步 → 账本事件（fake/录制测）
切片 KA-2  接线 run_service / openai_compat 开关（默认仍过渡环）
切片 KA-3  生产默认切真运行时 + 取消/技能回归
切片 KA-4  卸装饰依赖或降级；TRUTH-FREEZE 升版 O2=已接入
```

**本正本清源阶段在 KA-0 之前结束。**

---

## 6. 明确不在本阶段做

- 切换生产默认运行时  
- 预埋 Pi/OpenCode  
- 删除 `runner.py` 导致现网不可用  
- 宣称 S2「已钉版本 Kimi Agent 跑多步」为已完成  
