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
> 老师看见的**积分**是同一本账的派生（服务端换算，三位小数），不是第二套账、不是点池。  
> **禁止** 定价、人民币、套餐、扣款、支付、发票、点池/余额列。本表与 API **不得** 出现 `price` / `currency` / `cost` / `charge` / `billing` 列。  
> **edu-core：** 只拉 [`docs/contracts/usage-export.md`](./contracts/usage-export.md) 上的 `points` 数字扣点；禁止再乘。钱包仍在 edu。

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
| `estimated` | 0/1 | **不再写入 1。** 历史 char/4 启动时 scrub 成 0 + unknown |
| `task_id` | string \| null | 关联 Task（运行账本） |
| `run_id` | string \| null | 关联 Run |
| `source` | string | 写入点：`openai_compat` / `run_service` / 后续卡 |
| `extra_json` | object | 非钱元数据（时长、查询次数等） |
| `idempotency_key` | string unique | 失败重试不重复记账 |
| `created_at` | datetime UTC | 记账时间 |

**没有** `price` / `currency` / `cost` / `charge` / `amount` / `billing` 列。

Token 规则：

- 有提供方 usage（Responses `response.completed` / chat `include_usage` / **真 Pi** `agent_end.messages[].usage` 与 compaction usage）→ 记整数，`estimated=0`。
- 无 usage → 三字段 null 且 `tokens_unknown=1`。**禁止**用用户可见正文做 char/4 冒充 token。
- **禁止写入 `estimated=1`。** 历史 char/4 行在启动时 scrub 成 unknown（§8）。
- `extra.ui_model` = 档位；`extra.cached_tokens` / `extra.cache_write_tokens` / `extra.reasoning_tokens` 可选。`prompt_tokens` 必须是**完整输入**（含 cache 命中）；提供方把 cache 从 prompt 拆出去时，写入路径要把 cache 加回 prompt，列不能混。reasoning 是输出的子集，不另加一遍。导出给 edu，老师面不回 token。
- 禁止用 `0` 假装「没用量」。
- `model` 禁止长期留 `pico-fast` / `pico-deep`；档位只进 `extra.ui_model`。
- **禁止**把 Pi `cost`、倍率、公式写入账本或 extra。

**积分（派生 · 业主 2026-09-03）：** 读路径附加 `points`（`N.NNN` 或 `null`）。换算**只**在 `app/points_meter.py` + `config/channel-rates.json`。表上**不增加**人民币列。token 列仍是提供方桶。

```text
成本 = 该渠道价签 × token（或出图/检索按次）
售价 = 成本 × 2.5
积分 = 售价(元) × 1000     # 1 元 = 1000 积分
```

价签按 **渠道×模型**（同一模型不同渠道必须各有一条）。无价签 → 该渠道锁死，不准调用。钱/钱包在 edu-core；edu 拉 export 的 `points` **禁止再乘**。Pico 不做充值/支付/余额。`pico-fast`/`pico-deep` 是档位不是计费型号。出图优先用提供方 `usageMetadata`；没有则用价签的 `per_image_yuan`。unknown 且无按次价签 → `points=null`（不是 0）。老师面只见积分，禁止 token / 公式。每一轮钉在该条回复末尾：有积分显示「实际」。

---

## 3. kind

| kind | 谁 emit |
|------|---------|
| `llm` | pico-api：`openai_compat` / `run_service` 终态。优先提供方 usage |
| `search` | gateway `web_search` / `web_fetch` |
| `sandbox` | preview / HTML 写入 / browser |
| `image` | `generate_image`（New API Gemini）。优先 `usageMetadata` token；没有则按张 `per_image_yuan` |
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

true_pi / hosted Pi **不另开第二账本**：走上述终态钩子。真 Pi 本轮用量只从 `agent_end.messages[].usage` 与 `compaction_end` 入账；**禁止**对 `message_update` 累计值逐条加，**禁止**把会话 jsonl / `get_session_stats` 当本轮。Pi `cost` 剥掉。提供方未回 usage 仍记 **诚实 unknown**。

LibreChat 气泡 TokenUsage **不是** 本账；老师壳 `chat.completion` **不回** usage token 字段。

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
| POST | `/v1/usage/points/quote` | 发任务 UX 预计积分（不写 token 列） |
| GET | `/v1/usage/points?run_id=` | 本轮停下后的实际积分或 pending |
| GET | `/v1/internal/usage/export` | **edu 拉数**：`PICO_HOOK_SERVICE_TOKEN` · 见 [usage-export.md](./contracts/usage-export.md) |

查询参数：`kind` · `day=YYYY-MM-DD` · `limit` · `offset` · `membership_id`（仅 admin 且必须同校）。

响应 **无** 金额字段。`billing: false` 明示本账不是收费系统。老师 JSON **无** token 列；导出才有 token 列 + `points`。

---

## 7. 验收对照

1. 一次聊天后，该账号至少 1 条 `kind=llm`（backend model + native token **或** `tokens_unknown`）。
2. 另一账号拉不到该明细。
3. schema 无 price/currency 收费列。
4. 本文写清 search/sandbox/image emit。
5. edu 导出无金额字段；`billing: false`。
6. 不在 Pico 实现点池。

---

## 8. 历史脏行（一次性 scrub）

业主令：假 token 不得留在账上。启动 `init_db` 对 sqlite 执行 `scrub_dirty_usage_events_sync`：

| 旧行 | 处理后 |
|------|--------|
| `estimated=1`（char/4） | token 三字段 null · `tokens_unknown=1` · `estimated=0` · `extra.scrubbed=estimated_char4` |
| `model` = `pico-fast` / `pico-deep` 等档位 | `extra.ui_model` 保留档位；有 `run.model` 的 `backend_model` 则回填，否则 `model=null`（不拿「今天的脑」去猜旧行） |

**不删行**（谁/何时/kind 仍在）。LibreChat 气泡 `usage` 只回原生提供方数字，缺则省略字段。

edu 拉数：主机 `.env` 的 `PICO_HOOK_SERVICE_TOKEN`（`prod-update.sh` 空则生成；值不进 GitHub）。
