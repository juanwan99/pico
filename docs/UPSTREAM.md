# 上游调用层（pico#1271）

Pico 发给 New API 的每一个请求都走 `services/orchestrator/pico_orchestrator/upstream.py` 这一扇门：

| 出口 | 走法 |
|---|---|
| 直连对话（侧栏、管家 json_only、阅卷） | `provider.stream_chat` → `upstream.race` |
| Pi 智能体每一步 | pi-runner → `ws_proxy_router`（`/internal/ws-proxy/l/…`）→ `upstream.race`；带附件的 GPT 再经 `llm_pass_router` |
| 知识库 rerank | `meili_kb.rerank_documents_with_usage`（只计数） |
| 生图 | `image_generate._post_gateway` |
| 嵌入（入库、查询） | Meili 自己调 New API（不经 Pico 进程，见下） |

## 规则（都在 upstream.py 里，不再分散在 hedge / brain_ha / provider 各自一套）

- **预算**：一次逻辑调用最多 3 个上游请求（`CALL_BUDGET`），首发、补发、重试、换模型合起来算。
- **一次运行一个备用池**：同一个 run 的补发、重试、续跑（resume）共用 6 个额外请求（`RUN_SPARE`）。用完以后每个调用只发一次，不再补发也不再重试。
- **补发最多 1 路**：没有首字时等 25 s 再补（约为上游首字 p95）。高推理档等 60 s。环境变量 `PICO_HEDGE_{FAST,MEDIUM,DEEP}_S` 只取一个值，`off` 表示关掉补发。
  - Pi 快档已经有「25 s 没首字就换模型」（`PICO_PI_STALL_SWITCH_S`），这种 run 不再同时补发同一个模型。
- **重试只有一层**：
  - 只在首字之前，而且只针对 429 / 5xx / 连不上的情况，重试一次。
  - 上游回 401 / 402 / 403（钥被停、没额度）或没有渠道时换模型，不重试。
  - Pi 自己的重试已关（`PI_RETRY_MAX = 0`）。流到一半断了，由 Pico 同会话续跑处理，续跑也从备用池扣。
- **换模型最多一次**：主模型加一个备用（`brain_candidates(...)[:2]`）。
- **按 key 限并发**：同一把 key 同时最多 16 个请求（`PICO_UPSTREAM_KEY_MAX`），超了排队，最多等 120 s。
- **本机 403 和上游 403 分开**：
  - 只有上游回的错误状态，才由 run proxy 记进 `upstream.note_upstream_error`。
  - brain 换模型时看的是这条记录（`should_failover(..., relay=...)`）。所以上游回一个光秃秃的 403 也会换模型；本机 proxy 自己回的 403（`proxy.no_run` / `auth.denied`）不会。
- **在途去重**（复审 #1259）：管家用同一个 json_only 信封重发时，如果第一次还在算，就等那一次的结果（响应头 `X-Pico-Replay: inflight`），不再起第二次模型调用。

## 看数

`/health` 的 `upstream` 字段：

- `calls.<用途>`：用途有 direct / pi_step / image / rerank，各自给 sent / hedge / retry / budget_spent / busy / http_<状态码> 的次数；
- `inflight`：每把 key 当前在途的请求数；
- `peak`：每把 key 的峰值并发；
- `key_max`：每把 key 的并发上限。

key 只显示 sha256 的前 8 位。进程重启后清零（`since` 是起点）。

## 测试

`tests/unit/test_upstream.py` 对直连和 Pi 两条路各测四种情形：按顺序、并发、503、换模型。每种都断言一条消息最多发几个上游请求。CI 必跑。
