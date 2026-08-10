# L3 · 工程层（本轮）

## 日志（prod pico-pico-api-1 · 无密）

各 run_id 在 API access log 中均为 `GET /v1/runs/<id>/events` → **200**（本窗账本轮询 + 前端订阅），**未见** 同窗 5xx/Traceback 对应该批 run。

更细的工具成败在 **L2 事件流**（见各 `ledger.json` key_events）：

### R3 恢复链（账本事件 · 可定位）

1. `tool.call` `workspace_write_file` title=eye-timer.html  
2. `tool.result` **ok=false** · `tool.invalid_arguments` · 禁止用 workspace_write_file 写 .html  
3. `tool.call` `generate_html_document`  
4. `tool.result` **ok=true** · artifact eye-timer.html  
5. `delivery.summary` ok=true · min=1/art=1 · status=succeeded  

### 源码锚点（无 P0 回潮说明）

| 主题 | 锚点 |
|------|------|
| 「可下载**的**」min=1 | `services/orchestrator/pico_orchestrator/delivery_policy.py` · `_SINGLE_UNIT` · `可下载\s*(?:的\s*)?`（#418） |
| HTML 禁 workspace 写 | `services/orchestrator/pico_orchestrator/artifact_types.py` · 禁止 workspace_write_file 写 .html |
| 徽章「失败 · 已恢复」 | `apps/librechat/client/src/components/Chat/RunTimeline.tsx:64` · 事件流恢复步标签 |
| 欠交付人话 | `services/orchestrator/pico_orchestrator/pi_runtime.py` · deliverable_missing 人话（门闩语义未在本轮触发 terminal failed） |

本地 `analyze_delivery` 抽检（与 live 一致）：R1 min=3 · R2 min=1 · R3 min=1 · R5 min=0。
