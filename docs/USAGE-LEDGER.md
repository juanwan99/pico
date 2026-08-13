# USAGE-LEDGER · 用量账本合同（统计/管理 · 不做钱）

```
DOC: docs/USAGE-LEDGER.md
STATUS: BINDING · T-USAGE-LEDGER (#506)
REPO: juanwan99/pico ONLY
NOT: billing · price · currency · payment · packages · auto-debit
NOT: LibreChat TokenUsage UI · Task/Run/Event 运行账本
```

> **一本用量账，不是账单。** Pico 按账号记「谁、哪校、哪次任务、哪个模型、多少 token、何种用量」。  
> **禁止** 定价、人民币、套餐、扣款、支付、发票。本表与 API **不得** 出现 `price` / `currency` / `cost` / `charge` / `billing` 列或字段。

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
| `model` | string \| null | LLM 模型 id；非 llm 可空 |
| `prompt_tokens` | int \| null | 输入 token；未知则 null |
| `completion_tokens` | int \| null | 输出 token；未知则 null |
| `total_tokens` | int \| null | 合计；未知则 null |
| `tokens_unknown` | 0/1 | **诚实缺**：提供方未回 usage 且无法估计 |
| `estimated` | 0/1 | 1 = 字符估数，非提供方原生 usage |
| `task_id` | string \| null | 关联 Task（运行账本） |
| `run_id` | string \| null | 关联 Run |
| `source` | string | 写入点：`openai_compat` / `run_service` / 后续卡 |
| `extra_json` | object | 非钱元数据（时长、查询次数等） |
| `idempotency_key` | string unique | 失败重试不重复记账 |
| `created_at` | datetime UTC | 记账时间 |

**没有** `price` / `currency` / `cost` / `charge` / `amount` / `billing` 列。

Token 规则：有则记整数；无则三字段 null 且 `tokens_unknown=1`。禁止用 `0` 假装「没用量」。

---

## 3. kind

| kind | 本卡 | 谁 emit |
|------|------|---------|
| `llm` | **必须打点** | pico-api：`openai_compat` 终态 + `run_service` 终态 |
| `search` | 预留 | #507 搜索卡 |
| `sandbox` | 预留 | #508 沙箱卡 |
| `api` | 预留 | 其它出站 API |
| `other` | 预留 | 未分类 |

非法 kind 拒绝写入（fail-closed）。

---

## 4. 本卡 llm 写入点

主路径（LibreChat → `/v1/chat/completions`）在 `_finalize_run` **commit 之后** 记账。  
REST `/v1/tasks` 在 `_execute_run` **commit 之后** 记账。

- 幂等键：`llm:{run_id}`（一轮 chat/run 一条 llm；多步 agent 记累计 token）。
- 优先用编排层 `token_usage`（`prompt_tokens`/`input_tokens` + `completion_tokens`/`output_tokens`）。
- 提供方未回 usage 时：若有 prompt+completion 文本，记字符估数并 `estimated=1`；否则 `tokens_unknown=1`。
- **失败可重试、不得打断 Run**：写入吞掉异常；SQLite lock 最多 5 次；重复 `idempotency_key` 视为成功。

true_pi / hosted Pi 不另开第二账本：它们走上述终态钩子。true_pi 若尚未回 usage，本卡记 **诚实 unknown**（或估数），不编造计费级精度。

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

# --- #508 沙箱：一次隔离会话结束（或可计时长的预览）---
await record_usage_event(
    school_id=principal.school_id,
    membership_id=principal.membership_id,
    kind="sandbox",
    task_id=task_id,
    run_id=run_id,
    source="sandbox",
    extra={"duration_ms": 1234, "workspace_id": workspace_id},
    idempotency_key=f"sandbox:{run_id}:{session_id}",
)
```

约定：

- `record_usage_event` 永不抛到主路径（与 llm 相同）。
- search/sandbox **不必**填 token 字段（保持 null + `tokens_unknown=1` 即可）。
- `extra` 只放工具/时长/次数；禁止单价与币种。
- 幂等键必须含 run 或 tool_call / session，便于重试。

---

## 6. 只读查询 API

鉴权：`ai:read`（本人）或 `ai:admin`（同校其它成员）。**永远按 `principal.school_id` 隔离**；跨校不可见。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/usage/summary` | 按日 + kind 汇总 |
| GET | `/v1/usage/events` | 明细列表 |
| GET | `/v1/usage/events/{id}` | 单条明细（跨账号 404） |
| GET | `/v1/usage` | 极简「我的用量」HTML（只读 · 非运营后台） |

查询参数：`kind` · `day=YYYY-MM-DD` · `limit` · `offset` · `membership_id`（仅 admin 且必须同校）。

响应 **无** 金额字段。`billing: false` 明示本账不是收费系统。

---

## 7. 验收对照

1. 一次快速/深度聊天后，该账号至少 1 条 `kind=llm`（model + token 或 `tokens_unknown`）。
2. 另一账号拉不到该明细。
3. schema 无 price/currency 收费列。
4. 本文 §5 写清 search/sandbox emit。
5. `CLAIM-WB-DEGREE-WEB: NO`。
