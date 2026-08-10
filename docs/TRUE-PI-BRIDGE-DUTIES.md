# 真 Pi 薄桥 · 职责清单与禁区

```text
DOC: docs/TRUE-PI-BRIDGE-DUTIES.md
DATE: 2026-08-10
Issue: #431
CLAIM-WB: NO
```

## 模块路径

| 路径 | 职责 |
|------|------|
| `pico_orchestrator/true_pi/config.py` | 环境开关与路径 |
| `pico_orchestrator/true_pi/client.py` | RPC JSONL 客户端 |
| `pico_orchestrator/true_pi/tool_server.py` | 127.0.0.1 工具回调服 |
| `pico_orchestrator/true_pi/events.py` | Pi 事件 → Pico ledger |
| `pico_orchestrator/true_pi/runtime.py` | 旁路 `run_true_pi_agent` + 门闩 |
| `pico_orchestrator/true_pi/shadow.py` | 双跑 + diff 报告 |
| `services/true_pi_bridge/pico-gateway-tools.ts` | Pi extension：注册 7 工具 |

## 允许的工具（v0 · 不可放大）

```text
workspace_list_files
workspace_read_file
workspace_write_file
generate_html_document
generate_docx_document
generate_pptx_document
verify_html_document
```

## 禁止在桥内做

- host shell / bash / 任意文件系统
- 未登记 MCP
- delivery_policy 全文复刻（只复用现有 `count_write_tool_successes` / min 门闩）
- 第二业务账本 / 第二 OS
- 切换生产 `default_runtime`
- 密钥写入日志 / Issue
