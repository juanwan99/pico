# 污染清理记录（POLLUTION-SWEEP）

```
DOC: docs/POLLUTION-SWEEP.md
STATUS: LIVING
STARTED: 2026-08-01
TRUTH: docs/TRUTH-FREEZE.md v1.0
```

## 原则

1. **先诚实标注，再删代码** — 不在未接 Kimi Agent 前假装删掉过渡环导致生产不可用。  
2. **假完成表述**（文档/注释）优先清。  
3. **禁预埋 Plan B 运行时** 进真源。  
4. 大删 `runner.py` / 卸 pin 依赖 = **归位切片**，不在本 sweep 冒充完成。

## 本轮已做（代码+文档标注）

| 项 | 动作 |
|----|------|
| `runner.py` 模块/函数 docstring | 标明 TRANSITIONAL；禁「已是 Kimi Agent」 |
| `pico_orchestrator/__init__.py` | 去掉「Kimi Agent adapter」完成态 |
| `pins.py` / `check_agent_pin.py` | pin ≠ 运行时接入证明 |
| `docs/DEMO.md` / `SCOPE.md` / `VERSIONING.md` | 名实分离 |
| `scripts/pin-preview-8080.sh` 等 | 标注非业主公网主路径 |
| 真源冻结 | 见 TRUTH-FREEZE；archive 非真源 |

## 已登记、本轮不动（避免误伤生产）

| 项 | 原因 | 下一步 |
|----|------|--------|
| `run_agent_loop` 实现体 | 现网多步仍依赖 | Kimi Agent 真接切片替换 |
| `kimi-agent-sdk` / `kimi-cli` 依赖 | pin CI + safety 读 yaml | 真接后评估是否仍需要 |
| LibreChat 上游体积 | 产品壳 | 不在污染 sweep 范围 |
| 生产 compose 本地补丁 | 部署窗维护 | 不进本 PR |

## 禁止再引入

- 「薄控制面 = 已接开源 Agent」话术  
- Plan B / Pi / OpenCode 写入架构真源  
- 教师执行沙箱当主路径  
- 恢复 nextchat/web/workbench  

## 验证

- `python scripts/check_agent_pin.py`（若环境已装依赖）  
- 单测不因 docstring 变更失败  
- 不宣称产品 PASS / 编排归位完成  
