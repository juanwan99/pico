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
| 嵌入（入库、查询） | Meili 自己调 New API（不经 Pico 进程，见下「知识库」） |

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
- **按 key 限并发**：同一把 key 同时最多 4 个请求（`PICO_UPSTREAM_KEY_MAX`），同一个老师同时最多 2 个（`PICO_UPSTREAM_MEMBER_MAX`），超了排队，最多等 120 s；先排老师自己的，排着的不占 key 的名额（pico#1344：现网 14 天同时运行最多 5 次、每人基本 1 次）。尺子栈只给 1 个，`pico-ruler.py` 在宿主上一次只跑一遍（锁 `/tmp/pico-ruler.lock`，后来的等着）。
- **一个对话一个会话**（pico#1344）：AIProxy 10-18 封了 key，说每次请求都新开对话、并发高。New API 自带「codex cli trace」规则，把客户端的 `session_id` 等头原样转给上游；原先代理只转四个头，会话头被丢了。现在 Pi 的请求带 `session_id` = Pi 自己的 `prompt_cache_key`（会话文件按对话钉死，同一对话不变）；直连路在 `upstream.caller_scope` 里带 `pcs-<对话哈希>`，同时当 `prompt_cache_key`。对账见下一条。
- **AIProxy 只给多轮长会话**（pico#1344，业主 10-18 07:3x PDT「根本不是速率问题 是使用方式问题」）：AIProxy 是编程订阅，一个会话多轮用。四条：① 只有 Pi 的多轮会话能用；② 一问一答的调用（直连路、阅卷、探针）一律不去；③ 测试、尺子、探针不打现网 key 上的 AIProxy；④ 并发上限只是兜底。实现：`PICO_LONG_SESSION_MODELS`（默认 `gpt-5.6-sol`）里的模型只出现在 `brain_candidates(..., long_session=True)`（Pi 运行时），直连路的候选里没有；直连路只剩它一个时直接报错，不发请求。尺子栈起栈时 `scripts/pico-ruler-env-guard.py` 把它们从备用里摘掉，主模型或别的覆盖还点名它们就不起栈。对账：`python3 scripts/pico-upstream-pressure-report.py --days 1`（宿主上只读 New API 库：一问请求（`pcs-` / `pico-` / 无会话键）= 0、同一对话第 2 步起命中缓存 ≥ 90%、同时请求峰值 ≤ 4，不过退出 1；只发一次的 Pi 会话另列不判；只判令牌 `pico-gateway`，冒烟、探针等其他令牌另列次数，#1346）。
- **本机 403 和上游 403 分开**：
  - 只有上游回的错误状态，才由 run proxy 记进 `upstream.note_upstream_error`。
  - brain 换模型时看的是这条记录（`should_failover(..., relay=...)`）。所以上游回一个光秃秃的 403 也会换模型；本机 proxy 自己回的 403（`proxy.no_run` / `auth.denied`）不会。
- **在途去重**（复审 #1259）：管家用同一个 json_only 信封重发时，如果第一次还在算，就等那一次的结果（响应头 `X-Pico-Replay: inflight`），不再起第二次模型调用。

## 三把 token（New API）

| token | 环境变量 | 谁用 |
|---|---|---|
| 正式 | `DEEPSEEK_API_KEY` | 对话、阅卷、Pi、托管循环 |
| 知识库 pico-kb | `PICO_KB_API_KEY`（没设就用正式的） | Meili 嵌入、rerank |
| 探针 pico-probe | `PICO_PROBE_API_KEY` | `brain-switch.py` 预检、`model_hello.py`、`kb-eval.py`、`true-pi-live-smoke.py` |

- 脚本用 `scripts/probe_key.py` 取 token。设成了正式 / 知识库的 token，脚本直接退出，一个请求都不发。还没设的时候先用正式 key，stderr 打醒目警告（brain-switch 是 gemini 出事时切主脑的工具，不能卡在还没建的 token 上）。
- CI 不打真中转，单测都用假中转。

## 请求上带的标记

- 每个请求带 `user`：`pico-direct` / `pico-exam` / `pico-hosted`，只说是哪条路发的，不带人。
- Responses（gpt / grok）另带 `prompt_cache_key`：在对话里 = 这个对话的会话号（见上）；不在对话里才用系统提示的哈希。
- Pi 自己发的请求原样转发，不加这两项。

## 知识库（Meili 嵌入）

- **本机实测**（Meili v1.13.3，假嵌入服务数请求，pico#1271）：
  - 改 `apiKey`：重嵌 0 条；改 `headers`：重嵌 0 条。
  - 改 `request` / `response`（比如换成批量格式）：所有文档全部重嵌。现网 7 万多条，等于打 7 万次。
  - 所以嵌入**不改批量**，保持一条一发。日常量很小（10-15 那 6 小时 97 次，峰值 4 次/分）。
  - 真要整库重灌那天，用「先把现有向量标 `regenerate:false` 钉住，再改批量格式」的办法，单开卡做。本机验过这样重嵌 0 条。
- **换 token**：Meili 读回来的 `apiKey` 是打码的，看不出换没换。所以嵌入配置带一个请求头 `X-Pico-Key`（token 的 sha256 前 8 位），`ensure()` 看到它变了就只 PATCH apiKey 和这个头。本机用真 `ensure()` 验过：重嵌 0 条，之后新文档用新 token。
- **整库重建限速**：`rebuild_materials` 每分钟最多写 `PICO_KB_REBUILD_PER_MIN`（默认 600）个分块。每个分块就是 Meili 打一次嵌入。
  - 09-16 整库入库时 ch5 峰值约 2100 次/分，0 报错；现在 7.2 万块约 2 小时。
  - 第一分钟的量直接放行，所以发版时的增量入库不会多等。
  - `PICO_KB_REINDEX_FORCE=1` 的整库重建在后台跑，日志在 `~/logs/pico-kb-reindex-force.log`，不再因为 600 s 超时让发版失败。

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
