# USAGE-LEDGER · 用量账本合同（统计/管理 · 不做钱）

```
DOC: docs/USAGE-LEDGER.md
STATUS: BINDING · T-USAGE-LEDGER (#506) · edu export 2026-08-29
REPO: juanwan99/pico ONLY
NOT: billing · price · currency · payment · packages · auto-debit · wallets · 点
NOT: LibreChat TokenUsage UI · Task/Run/Event 运行账本
EDU: docs/contracts/usage-export.md（edu-core 拉干净行；钱在 edu）
```

> **一本用量账，不是账单。** Pico 按账号记「谁、哪校、哪次任务、哪个**后端模型**、多少 token（或诚实缺）。  
> **禁止** 定价、人民币、套餐、扣款、支付、发票、点池。本表与 API **不得** 出现 `price` / `currency` / `cost` / `charge` / `billing` 列。  
> **edu-core 计费：** 只拉 [`docs/contracts/usage-export.md`](./contracts/usage-export.md)；汇率/点/钱包在 edu，不在 Pico。

与现有概念的边界：

| 概念 | 位置 | 用途 |
|------|------|------|
| **用量账本（本文件）** | `usage_events` · pico-api | 跨 Run 的产品用量统计 |
| Task / Run / Event | `services/api/app/db.py` | 一次办事的运行账本（步骤/产物） |
| LibreChat TokenUsage | `apps/librechat` UI | 会话气泡估算展示 · **不是** 本账 |

---

## 1. 不做钱（硬约束）

```text
统一计量 = 统计 / 管理
不做：价格、币种、支付、套餐、自动扣费、发票
schema 与 JSON 合同禁止 money 字段
写入 extra_json 时剥掉 price/currency/cost/charge/amount/billing/payment/package/debit
```

---

## 2. 字段表（`usage_events`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string UUID | 行主键 |
| `school_id` | string | 租户/学校 |
| `membership_id` | string | 账号（成员） |
| `kind` | string | 见 §3 |
| `model` | string \| null | **后端**模型 id（`gpt-5.6-sol` / 出图模型）。禁止把 `pico-fast` 当计费型号 |
| `prompt_tokens` | int \| null | 输入 token；未知则 null |
| `completion_tokens` | int \| null | 输出 token；未知则 null |
| `total_tokens` | int \| null | 合计；未知则 null |
| `tokens_unknown` | 0/1 | **诚实缺**：提供方未回 usage。**禁止当 0 计费** |
| `estimated` | 0/1 | 1 = 字符估数；**禁止当原生 usage 计费** |
| `task_id` | string \| null | 关联 Task（运行账本） |
| `run_id` | string \| null | 关联 Run |
| `source` | string | 写入点：`openai_compat` / `run_service` / 后续卡 |
| `extra_json` | object | 非钱元数据（时长、查询次数等） |
| `idempotency_key` | string unique | 失败重试不重复记账 |
| `created_at` | datetime UTC | 记账时间 |

**没有** `price` / `currency` / `cost` / `charge` / `amount` / `billing` 列。

Token 规则：

- 有提供方 usage（Responses `response.completed` / chat `include_usage` / Pi RPC 若带）→ 记整数，`estimated=0`。
- 无 usage（现网 Pi 主路径常见）→ 三字段 null 且 `tokens_unknown=1`。**禁止**用用户可见正文做 char/4 冒充 token（现网曾把 prompt=1 写成「用量」）。
- `extra.ui_model` = 档位；`extra.cached_tokens` / `extra.reasoning_tokens` 可选，edu 自己加权。
- 禁止用 `0` 假装「没用量」。

---

## 3. kind

| kind | 谁 emit |
|------|---------|
| `llm` | pico-api：`openai_compat` / `run_service` 终态。优先提供方 usage |
| `search` | gateway `web_search` / `web_fetch` |
| `sandbox` | preview / HTML 写入 / browser |
| `image` | `generate_image`（New API Gemini）。token 常 unknown；extra 记 bytes/provider |
| `api` | 预留 |
| `other` | 预留 |

非法 kind 拒绝写入（fail-closed）。

---

## 4. 本卡 llm 写入点

主路径（LibreChat → `/v1/chat/completions`）在 `_finalize_run` **commit 之后** 记账。  
REST `/v1/tasks` 在 `_execute_run` **commit 之后** 记账。

- 幂等键：`llm:{run_id}`（一轮 chat/run 一条 llm；多步若 Pi 回了分次 usage 则累加后再记）。
- 优先用编排层 `token_usage`（Responses / chat.completions native）。
- 提供方未回 usage：**记 unknown**，不要用 prompt+completion 字符估数当默认（估数会让 edu 收到 prompt_tokens=1 这种脏数）。
- **失败可重试、不得打断 Run**：写入吞掉异常；SQLite lock 最多 5 次；重复 `idempotency_key` 视为成功。

true_pi / hosted Pi 不另开第二账本：走上述终态钩子。Pi RPC 暂无 usage 时记 **诚实 unknown**。

LibreChat 气泡 TokenUsage **不是** 本账。

---

## 5. 搜索 / 沙箱如何 emit（给 #507 / #508）

后续卡 **只调适配函数**，不要自建表、不要写钱字段。

```python
from app.usage_ledger import record_usage_event

# --- #507 搜索：每次 web_search / web_fetch 成功或明确失败后 ---
await record_usage_event(
    school_id=principal.school_id,
    membership_id=principal.membership_id,
    kind="search",
    task_id=task_id,
    run_id=run_id,
    source="web_search",  # 或 web_fetch
    extra={"provider": "deepseek", "tool": "web_search", "query_count": 1},
    idempotency_key=f"search:{run_id}:{tool_call_id}",
)

# --- #508 沙箱：看页 / 隔离写入（可计时长的预览）---
await record_usage_event(
    school_id=principal.school_id,
    membership_id=principal.membership_id,
    kind="sandbox",
    task_id=task_id,
    run_id=run_id,
    source="sandbox",
    extra={"duration_ms": 1234, "workspace_id": workspace_id, "artifact_id": artifact_id},
    idempotency_key=f"sandbox:{run_id}:{session_id}",
)
```

约定：

- `record_usage_event` 永不抛到主路径（与 llm 相同）。
- search/sandbox **不必**填 token 字段（保持 null + `tokens_unknown=1` 即可）。
- `extra` 只放工具/时长/次数；禁止单价与币种。
- 幂等键必须含 run 或 tool_call / session，便于重试。
- **#508 / #513：** `sandbox` 已 emit（不再是预留）。写入点：`sandbox_preview_inspect`（含 S2 光栅）、`generate_html_document` 预览落盘、可选 `sandbox_workspace_exec`。合同见 [`docs/SANDBOX-S1.md`](./SANDBOX-S1.md) · [`docs/SANDBOX-S2.md`](./SANDBOX-S2.md)。截图 `artifact_id` 可放进 extra；仍禁止钱字段。

---

## 6. 只读查询 API

鉴权：`ai:read`（本人）或 `ai:admin`（同校其它成员）。**永远按 `principal.school_id` 隔离**；跨校不可见。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/usage/summary` | 按日 + kind 汇总 |
| GET | `/v1/usage/events` | 明细列表 |
| GET | `/v1/usage/events/{id}` | 单条明细（跨账号 404） |
| GET | `/v1/usage` | 极简「我的用量」HTML（只读 · 非运营后台） |
| GET | `/v1/internal/usage/export` | **edu 拉数**：`PICO_HOOK_SERVICE_TOKEN` · 见 [usage-export.md](./contracts/usage-export.md) |

查询参数：`kind` · `day=YYYY-MM-DD` · `limit` · `offset` · `membership_id`（仅 admin 且必须同校）。

响应 **无** 金额字段。`billing: false` 明示本账不是收费系统。

---

## 7. 验收对照

1. 一次聊天后，该账号至少 1 条 `kind=llm`（backend model + native token **或** `tokens_unknown`）。
2. 另一账号拉不到该明细。
3. schema 无 price/currency 收费列。
4. 本文写清 search/sandbox/image emit。
5. edu 导出无金额字段；`billing: false`。
6. 不在 Pico 实现点池。
