# 上游调用层（pico#1271）

Pico 发给 New API 的每一个请求都走 `services/orchestrator/pico_orchestrator/upstream.py` 这一扇门：

| 出口 | 走法 |
|---|---|
| 直连对话（侧栏、管家 json_only） | `provider.stream_chat` → `upstream.race` |
| 阅卷读题（答案卷、逐页做题） | `extract.model_complete` → `provider.call_once`（不再有自己的 5 次重试）；主脑的钥或渠道死了（401 / 402 / 403、没渠道、额度没了）换备用脑，有图的页跳过看不了图的模型，两个模型合起来最多 3 发 |
| Pi 智能体每一步（沙箱） | pi-runner → `ws_proxy_router`（`/internal/ws-proxy/l/…`）→ `upstream.race`；带附件的 GPT 再经 `llm_pass_router`，只发一次（请求头 `x-pico-door: raced`） |
| Pi 智能体每一步（没有沙箱） | Pi 进程 → `llm_pass_router` → `upstream.race`（不再直连 New API） |
| 回滚用的托管循环（`PICO_HOSTED_LOOP=1`） | `pi_runtime` → `provider.call_once`（不再自建带重试的客户端） |
| 知识库 rerank | `meili_kb.rerank_documents_with_usage`（只计数） |
| 生图 | `image_generate._post_gateway` |
| 嵌入（入库、查询） | Meili 自己调 New API（不经 Pico 进程，见下） |

门外只剩旧的 Kimi CLI 灰度（`kimi_runtime`，现网没开）：它用 Kimi SDK 自己的 `max_retries_per_step`。要开它，先把 `PICO_UPSTREAM_KEY_MAX` 调低。

## 规则（都在 upstream.py 里，不再分散在 hedge / brain_ha / provider 各自一套）

- **预算**：一次逻辑调用最多 3 个上游请求（`CALL_BUDGET`），首发、补发、重试、换模型合起来算。
- **一次运行一个备用池**：同一个 run 的补发、重试、续跑（resume）共用 6 个额外请求（`RUN_SPARE`）。用完以后每个调用只发一次，不再补发也不再重试。
- **补发最多 1 路**：没有首字时等 25 s 再补（约为上游首字 p95）。高推理档等 60 s。环境变量 `PICO_HEDGE_{FAST,MEDIUM,DEEP}_S` 只取一个值，`off` 表示关掉补发。
  - 输掉的那一路当场挂断（`stream.close()`），不等垃圾回收，免得在中转那头一直占着连接。
  - Pi 快档已经有「25 s 没首字就换模型」（`PICO_PI_STALL_SWITCH_S`），这种 run 不再同时补发同一个模型。
- **重试只有一层**：
  - 只在首字之前，而且只针对 429 / 5xx / 连不上的情况重试，第一次隔 2 s，第二次隔 6 s。上游给了 `Retry-After` 就照它等，最多 20 s。换模型不等。
  - 三次都忙（429 / 503 / 529），老师看到「Pico 这会儿忙，请稍后再试。」。老师看到的话里不出现「模型」（`teacher_text`）。
  - 上游回 401 / 402 / 403（钥被停、没额度）或没有渠道时换模型，不重试。
  - Pi 自己的重试已关（`PI_RETRY_MAX = 0`）。流到一半断了，由 Pico 同会话续跑处理，续跑也从备用池扣。
- **换模型最多一次**：主模型加一个备用（`brain_candidates(...)[:2]`）。直连、Pi、阅卷三条路都会换；429（如 Vertex 共享配额）、安全拦截、超时不换。
- **按发出去的模型选线**：gpt-* / grok-* 走 Responses，Gemini 走 chat/completions。直连、Pi、阅卷三条路都看这一跳实际发的模型，不看主脑。阅卷原来看主脑，把 gpt-5.6-sol 发到 chat/completions，New API 回 400（pico#1288）。
- **按 key 限并发**：同一把 key 同时最多 16 个请求（`PICO_UPSTREAM_KEY_MAX`），超了排队，最多等 120 s。
- **本机 403 和上游 403 分开**：
  - 只有上游回的错误状态，才由 run proxy 记进 `upstream.note_upstream_error`。
  - brain 换模型时看的是这条记录（`should_failover(..., relay=...)`）。所以上游回一个光秃秃的 403 也会换模型；本机 proxy 自己回的 403（`proxy.no_run` / `auth.denied`）不会。
- **在途去重**（复审 #1259）：管家用同一个 json_only 信封重发时，如果第一次还在算，就等那一次的结果（响应头 `X-Pico-Replay: inflight`），不再起第二次模型调用。

## 看数

`/health` 的 `upstream` 字段：

- `calls.<用途>`：用途有 direct / exam / hosted / pi_step / pi_pass（沙箱里带附件的那一跳）/ image / rerank，各自给 sent / hedge / retry / budget_spent / busy / http_<状态码> 的次数；
- `inflight`：每把 key 当前在途的请求数；
- `peak`：每把 key 的峰值并发；
- `key_max`：每把 key 的并发上限。

key 只显示 sha256 的前 8 位。进程重启后清零（`since` 是起点）。

## 测试

`tests/unit/test_upstream.py` 对直连和 Pi 两条路各测四种情形：按顺序、并发、503、换模型。每种都断言一条消息最多发几个上游请求。CI 必跑。

另外还测：重试的等待时间（2 s、6 s、`Retry-After`）；阅卷、托管循环、llm-pass 都走这扇门；主脑 Gemini 挂了时直连换 sol 走 Responses、阅卷指定 sol 也走 Responses；补发输掉的那一路在 1 s 内挂断。最后这条用本机真 HTTP 假中转测，去掉 `stream.close()` 就会失败。
