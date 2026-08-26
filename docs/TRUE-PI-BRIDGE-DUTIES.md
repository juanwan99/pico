> **项目法律：** [`LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md) — 桥必须薄；加厚 = 违法。

# 真 Pi 薄桥 · 职责清单与禁区

```text
DOC: docs/TRUE-PI-BRIDGE-DUTIES.md
DATE: 2026-08-10
Issue: #431 · #433 · #435 · #436
默认 multi-step: pi-true（DEFAULT=1）· 回滚: HOSTED_LOOP=1
CLAIM-WB: NO
```

## 模块路径

| 路径 | 职责 |
|------|------|
| `pico_orchestrator/true_pi/config.py` | 开关：shadow / canary / default / hosted 回滚 |
| `pico_orchestrator/true_pi/client.py` | RPC JSONL 客户端 |
| `pico_orchestrator/true_pi/tool_server.py` | 127.0.0.1 工具回调服 |
| `pico_orchestrator/true_pi/events.py` | Pi 事件 → Pico ledger（含 compaction.*） |
| `pico_orchestrator/true_pi/runtime.py` | `run_true_pi_agent` + 门闩 + 最小 history |
| `pico_orchestrator/true_pi/shadow.py` | 双跑 + diff 报告 |
| `services/true_pi_bridge/pico-gateway-tools.ts` | Pi extension：注册 gateway 工具（含 #507 web_search/web_fetch） |
| `docs/OPS-TRUE-PI-ROLLBACK.md` | 部署 / 回滚一页 |

## 允许的工具（v2 · #507 web_search/web_fetch）

```text
workspace_list_files
workspace_read_file
workspace_write_file
generate_html_document
generate_docx_document
generate_pptx_document
edit_docx_document
edit_pptx_document
generate_image
verify_html_document
web_search
web_fetch
```

v1 曾增加：skill_instruction 注入、近 N 条 user/assistant history 文本、skill_snapshot 工具交并集。  
v2（#507）：DeepSeek 官方 `web_search` 转发 + 网关 `web_fetch`（SSRF 拒绝内网/metadata/管理域）。仍禁 bash / 任意 FS / 浏览器代登。  
v3（#608）：改已有 `.docx`/`.pptx` 走 PyPI `python-docx` / `python-pptx` 薄适配（禁止 `generate_*` 另造冒充改原件）。出图走 SiliconFlow HTTPS `images/generations`（禁自研扩散）。侧栏仍空工具。  
v4（#646 T-GROK-PATH）：禁止把 Skill / Landing / 历史焊进 `prompt()`。短纪律进 Pi `SYSTEM.md`（通用，无场景 if）。`prompt()` 只留老师原文。工具白名单仍挂载，模型决定调不调。跑后门只认「声称交件却没落盘」，不认正文词表。  
v5（#690 卡 1）：办公文档核见 [`docs/ADR-OFFICE-DOC-PIPELINE.md`](./ADR-OFFICE-DOC-PIPELINE.md)。Pi 少动词 inspect/render/edit/verify；`generate_*` 内部走 spec。禁桥内 bash、禁模型即兴 python-docx、禁 MCP 办公室栈。

## 禁止在桥内做

- host shell / bash / 任意文件系统
- 未登记 MCP
- delivery_policy 全文复刻（只复用现有 `count_write_tool_successes` / min 门闩）
- 第二业务账本 / 第二 OS
- 无 live 冒烟强制切主
- 密钥写入日志 / Issue
- 删除 `pi_runtime.py`（回滚必须保留）
