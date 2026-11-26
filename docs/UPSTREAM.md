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

## 上游调用规则

- **预算**：一次逻辑调用最多 3 个上游请求（`CALL_BUDGET`），首发、重试、换模型合起来算。
- **一次运行一个备用池**：同一个 run 的重试、续跑（resume）共用 6 个额外请求（`RUN_SPARE`）。用完以后每个调用只发一次。
- **重试只有一层**：
  - 每个上游调用串行尝试。Pi 快档的首选模型在拿到名额、发出 New API 请求后才开始等首字；排队和重试间隔不计。单次请求等首字超时（`PICO_PI_STALL_SWITCH_S`，默认 25 s）后换下一个。120 s 内三次首字超时把模型置于备用链尾部 120 s。直连关闭思考时首字节超时为 60 s。
  - 只在首字之前，而且只针对 429 / 5xx / 连不上的情况重试，第一次隔 2 s，第二次隔 6 s。上游给了 `Retry-After` 就照它等，最多 20 s。换模型不等。
  - 三次都忙（429 / 503 / 529），老师看到「Pico 这会儿忙，请稍后再试。」。老师看到的话里不出现「模型」（`teacher_text`）。
  - 上游回 401 / 402 / 403（钥被停、没额度）或没有渠道时换模型，不重试。
  - Pi 自己的重试已关（`PI_RETRY_MAX = 0`）。流到一半断了，由 Pico 同会话续跑处理，续跑也从备用池扣。
- **换模型最多一次**：主模型加一个备用（`brain_candidates(...)[:2]`）。直连、Pi、阅卷三条路都会换；429（如 Vertex 共享配额）、安全拦截、超时不换。
- **按发出去的模型选线**：gpt-* / grok-* 走 Responses，Gemini 走 chat/completions。直连、Pi、阅卷三条路都看这一跳实际发的模型，不看主脑。阅卷原来看主脑，把 gpt-5.6-sol 发到 chat/completions，New API 回 400（pico#1288）。
- **聊天主脑、读卷和转写**：
  - 主脑 = `DEEPSEEK_MODEL`，现网快档 11-14 起 `gemini-3.8-flash`（edu-core#5603），11-24 起 `gpt-6.2-sol`（edu-core#6410）。`pico-fast` 和 `pico-deep` 默认都用这个模型，`PICO_BRAIN_DEEP_MODEL` 可单独配置深档。
  - `/v1/exam/answer-extract` 用 `PICO_EXAM_READ_MODEL`，空值跟随 `pico-fast`。edu-core#6319 发版时在 `/opt/pico/.env` 配 `PICO_EXAM_READ_MODEL=deepseek-flash`（DeepSeek 官方，New API 渠道 8）。渠道 4 的旧别名 `deepseek-v4-flash` / `deepseek-reasoner` 映射到 Gemini。带图由 `vision_model_for_images` 选可读图的模型，用量按实际回答的模型记。
  - `pico-ocr` 是阅卷手写转写档，后端是 `PICO_OCR_MODEL`（现网 11-24 起 `gpt-6.1-terra`，edu-core#6410），没设就跟 pico-fast 一样。只有 edu 阅卷的两处转写点名这一档：主观题转写、填空转写。
  - 这一档不进 `/v1/models`。线上白名单只要有 pico-fast / pico-deep，就放行 pico-ocr。
  - 计价按 `PICO_OCR_MODEL` 那一行算（`channel_rates._lane_backend`）。
  - 备用顺序看 `PICO_BRAIN_FALLBACKS`。现网 11-25 是 `gpt-6.1-terra,deepseek-flash,gpt-5.6-sol`，排在第一位的主模型自动去重：
    - 聊天快档：gpt-6.2-sol → gpt-6.1-terra；转写档：gpt-6.1-terra → deepseek-flash
    - 读卷：deepseek-flash → gpt-6.1-terra
  - 换脑用 `brain-switch.py --ocr <model>`：先预检转写模型能不能读图，切完后检里多一项 pico-ocr 读图。pico-api 起不来也自动回滚。
- **阅卷单列**（pico#1379，业主 11-02「阅卷需要单列，至于用哪个模型 我需要灵活可方便切换」）：带 `ai:exam-grading` 的票（edu AI 阅卷的转写和评分）整次请求都在阅卷范围里（`grading_models.enter_grading`）。
  - 上游 key 换成 `PICO_GRADING_API_KEY`（New API 令牌 `pico-grading`，分组 `grading`）。哪些渠道接阅卷、谁主谁备，在 New API 这个分组里配（UU 优先级高、米醋备）。没设就用正式 key，和以前一样。
  - 模型看 `data/grading-models.json`（容器 `/app/data`），按学校覆盖：`pico-ocr` 用 `ocr`，其他档（评分）用 `score`；阅卷只评一次，原来的第二评分档 `pico-score2` / `score2` 已删（edu-core#5598，旧文件里的 `score2` 不读，下次写入时去掉）。顺序是学校、`default`、环境变量（`PICO_OCR_MODEL` / 主脑）。文件改了下一次调用就生效，不重启；文件写坏了，接着用上一份读通的。
  - 切换：宿主上 `python3 scripts/grading-model.py show`，`set [--school <id>] --ocr <m> --score <m> --card … --why …`（可加 `--dry-run`），`clear --school <id>`。先用阅卷令牌直打中转预检：转写模型要读图，评分模型要文字加读图。不过就不写。写完在 `~/pico-env-changes.log` 记一行旧 → 新。
  - 阅卷分组缺某个模型的渠道时，只在这一次调用里跳过它，不把聊天用的这个模型标坏（`mark_down`）。
  - 阅卷评分和转写一样，用阅卷那组名额（每把 key、每人各 16 个），不占聊天的 8 / 2。
  - 记账：用量行 `extra.lane = "grading"`，模型记实际发出的那个。edu 钱包据此单列「阅卷」。
- **按 key 限并发**：同一把 key 默认同时最多 8 个请求（`PICO_UPSTREAM_KEY_MAX`），同一个老师同时最多 2 个（`PICO_UPSTREAM_MEMBER_MAX`），超了排队，最多等 120 s；先排老师自己的，排着的不占 key 的名额（pico#1344：现网 14 天同时运行最多 5 次、每人基本 1 次）。阅卷识别（`pico-ocr`，一问一答、单次 1–2 s）另有一组名额：同一把 key、同一个老师各 16 个（`PICO_UPSTREAM_OCR_KEY_MAX` / `PICO_UPSTREAM_OCR_MEMBER_MAX`），和聊天 / Pi 的 8 / 2 互不占用（edu-core#3927：共用每人 2 个时一科 400 份要 573 s）；读试卷（`exam-answer-extract`，用途 `exam`）同一把 key 另有 6 个（`PICO_UPSTREAM_EXAM_KEY_MAX`，一份卷 4 页 + 2 个卡住页的副本正好一波），也不占聊天的 8 个（edu-core#4095：后台补题干占满当时的 4 个名额，老师在同一张卡上问侧栏排了 186 s）；识别只走 `PICO_OCR_MODEL` 和不走 AIProxy 的备用模型，测试 `test_handwriting_reads_never_reach_aiproxy` 守着。尺子栈只给 1 个，`pico-ruler.py` 在宿主上一次只跑一遍（锁 `/tmp/pico-ruler.lock`，后来的等着）。
- **一个对话一个会话**（pico#1344）：AIProxy 10-18 封了 key，说每次请求都新开对话、并发高。New API 自带「codex cli trace」规则，把客户端的 `session_id` 等头原样转给上游；原先代理只转四个头，会话头被丢了。现在 Pi 的请求带 `session_id` = Pi 自己的 `prompt_cache_key`（会话文件按对话钉死，同一对话不变）；直连路在 `upstream.caller_scope` 里带 `pcs-<对话哈希>`，同时当 `prompt_cache_key`。对账见下一条。
- **AIProxy 只给多轮长会话**（pico#1344，业主 10-18 07:3x PDT「根本不是速率问题 是使用方式问题」）：AIProxy 是编程订阅，一个会话多轮用。四条：① 只有 Pi 的多轮会话能用；② 一问一答的调用（直连路、阅卷、探针）一律不去；③ 测试、尺子、探针不打现网 key 上的 AIProxy；④ 并发上限只是兜底。实现：`PICO_LONG_SESSION_MODELS`（默认 `gpt-5.6-sol`）里的模型只出现在 `brain_candidates(..., long_session=True)`（Pi 运行时），直连路的候选里没有；直连路只剩它一个时直接报错，不发请求。别的一问调用同样不用：联网搜索、知识库检索词扩写走 `one_shot_model()`（主模型是它就换第一个备用，没有就不调），换脑预检 `brain-switch.py` 不探它、也不许它当主模型，`kb-eval.py` 点名它就退出。尺子栈起栈时 `scripts/pico-ruler-env-guard.py` 把它们从备用里摘掉，主模型或别的覆盖还点名它们就不起栈。对账：`python3 scripts/pico-upstream-pressure-report.py --days 1`（宿主上只读 New API 库：一问请求（`pcs-` / `pico-` / 无会话键）= 0、同一对话第 2 步起命中缓存 ≥ 90%、同时请求峰值 ≤ 8，不过退出 1；只发一次的 Pi 会话另列不判；只判令牌 `pico-gateway`，冒烟、探针等其他令牌另列次数，#1346）。
- **本机 403 和上游 403 分开**：
  - 只有上游回的错误状态，才由 run proxy 记进 `upstream.note_upstream_error`。
  - brain 换模型时看的是这条记录（`should_failover(..., relay=...)`）。所以上游回一个光秃秃的 403 也会换模型；本机 proxy 自己回的 403（`proxy.no_run` / `auth.denied`）不会。
- **在途去重**（复审 #1259）：管家用同一个 json_only 信封重发时，如果第一次还在算，就等那一次的结果（响应头 `X-Pico-Replay: inflight`），不再起第二次模型调用。

## 四把 token（New API）

| token | 环境变量 | 谁用 |
|---|---|---|
| 正式 | `DEEPSEEK_API_KEY` | 对话、Pi、托管循环（阅卷令牌没设时也走它） |
| 阅卷 pico-grading | `PICO_GRADING_API_KEY`（分组 `grading`） | edu AI 阅卷的转写、评分；`grading-model.py` 预检 |
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
- **知识库重建限速**：pico-api 在后台跑发版增量重建。设置 `PICO_KB_REINDEX_FORCE=1` 可发起整库重建。发版门确认入队 HTTP 202 和 `pico_materials` 至少有 1 个文档，然后照常跑冒烟。
  - 每批最多 20 个分块。等 Meili 完成上一批后，再留出空闲时间，取分块数 × 60 ÷ `PICO_KB_REBUILD_PER_MIN`（默认 600）与上一批实际耗时中的较大值。重建批次占用 Meili 的时间最多为忙闲周期的一半。
  - Meili 容器的内存上限须容纳整份索引 `data.mdb` 和额外的 1 GB 建索引内存，避免 LMDB 文件页反复被淘汰和读回。
  - 完成、失败和取消结果由 `log_rebuild_result` 记在 pico-api 日志。成功时在 WARNING 级别输出 `kb reindex completed` 和重建计数。

## 看数

`/health` 的 `upstream` 字段：

- `calls.<用途>`：用途有 direct / exam / hosted / pi_step / pi_pass（沙箱里带附件的那一跳）/ image / rerank，各自给 sent / retry / budget_spent / busy / http_<状态码> 的次数；
- `inflight`：每把 key 当前在途的请求数；
- `peak`：每把 key 的峰值并发；
- `key_max`：每把 key 的并发上限；
- `down_models` 按模型名列出当前判下线的模型，包含 `remaining_seconds` 和 `reason`（`stall` 为反复首字超时，`dead` 为渠道或密钥不可用）。每次判下线时，`brain mark_down` 以 WARNING 记录模型、原因和持续秒数。

key 只显示 sha256 的前 8 位。进程重启后清零（`since` 是起点）。

## 测试

`tests/unit/test_upstream.py` 对直连和 Pi 两条路各测四种情形：按顺序、并发、503、换模型。每种都断言一条消息最多发几个上游请求。CI 必跑。

另外还测重试的等待时间（2 s、6 s、`Retry-After`）、阅卷和托管循环及 llm-pass 的重试预算，以及切换至 Responses 模型时走正确的 API。

## 沙箱实时画面（pico#1446）

Playwright 1.63.0 通过 Chromium CDP 取 JPEG。DPR 大于 1 的会话使用 Chromium 原生虚拟显示器，标签页随当前沙箱的 DPR 切换显示器，关桌时移除。用一次 `Emulation.setDeviceMetricsOverride` 提交 CSS 尺寸和 DPR。同一标签调整 CSS 尺寸或 DPR 时沿用 CDP 投屏，Chromium 捕获新的合成画面。换标签时才重新挂捕获。标签页尺寸适配失败时记录原因，画面回到现有 PNG 轮询。worker 丢弃时间戳早于最近一次改尺寸的帧，再按 Chromium 的 float32 取整核对 CDP metadata 与 JPEG 像素尺寸（不留容差），然后按 CSS 尺寸发帧；同一视口代次内重复画面才丢，每代首帧必送。Chromium 用 `--disable-lcd-text` 绘制灰阶文字，减轻 JPEG 色度采样带来的字体边缘模糊。[CDP Emulation](https://chromedevtools.github.io/devtools-protocol/tot/Emulation/) · [Chromium 投屏和截图源码](https://chromium.googlesource.com/chromium/src/+/refs/tags/153.0.8010.12/content/browser/devtools/protocol/page_handler.cc)

PNG 在持有 DPR 的 CDP 会话通过 `Page.captureScreenshot` 读取当前窗口，不裁剪或改变窗口布局。worker 将 PNG 像素缩回 CSS 尺寸，保留当前滚动位置。真 Chromium 回归覆盖滚动 500 px 后按图点击、投屏期间连截三次 PNG、非整数 DPR 切换及不同会话并用和关桌回收。

Chromium 的帧到达 worker 即向 CDP 确认，worker 只留最新一帧待发。新前端通过 `ack=1` 声明每路 SSE 有两帧的确认窗口。网页解码后按顺序发起确认请求，同时继续读流。确认丢失时，超过 15 秒的名额释放，有待发帧就发送最新一帧，包括页面静止前的最后一帧。未声明确认的旧前端仍连续接收。实时输入只回网址、标题、输入框标记和操作结果，登录保存按 15 秒节流。网页将滚轮增量合并，每次只挂一条滚动请求。Office、老师盘和推帧不可用时继续轮询 PNG。[CDP Page 协议](https://chromedevtools.github.io/devtools-protocol/tot/Page/) · [noVNC 的 RFB 消息](https://github.com/novnc/noVNC/blob/master/docs/rfb_notes)

确认帧的客户端在画面变化时接收约 0.65× CSS 像素、质量 32 的 JPEG。worker 用 Pillow 缩放即将发送的帧，保留同一张原生 DPR、质量 75 的帧供静止后补发。最近画面变化或滚轮请求后 280 ms 补清晰帧。新视口首帧的细化从尺寸生效时起算 150 ms，Chromium 出帧已超过该时限时直接推清晰帧。尺寸变化会废弃上一布局仍待发的帧，晚到的旧 CDP 帧按时间戳丢弃。两档 JPEG 都按帧对应的 CSS 宽高显示和换算点击。未声明确认的客户端仍接收原生 JPEG。[TurboVNC Automatic Lossless Refresh](https://github.com/TurboVNC/turbovnc/blob/main/doc/performance.txt)

### JPEG 测量

返修 3 的本地 Chromium 153.0.8010.12，DPR 1.5。同一份 12 CSS px 中英文长表分别测试表格和带彩色图表的布局。统一从实拍原生 1.5× PNG 的同一文字区域计算 RGB 均方根误差。1× 对照使用双三次放大对齐像素。开关对照统一使用灰阶文字栅格和 JPEG 75，括号内依次为 JPEG KiB、base64 经 gzip level 1 后的 KiB 和误差。

| CSS 尺寸与画面 | 强制 DSF 2，缩成 1.5× | 关闭强制 DSF，默认显示器 1× | 原生 1.5× |
|---|---:|---:|---:|
| 1280×800 表格 | 276.5 / 237.7 / 25.43 | 160.8 / 142.2 / 34.67 | 291.9 / 247.7 / 4.63 |
| 1920×1080 表格 | 436.6 / 344.6 / 20.93 | 250.6 / 204.6 / 25.77 | 456.7 / 362.3 / 3.89 |
| 1920×1080 表格及图表 | 378.5 / 291.6 / 21.06 | 216.4 / 174.2 / 25.94 | 395.9 / 306.5 / 3.98 |

单关强制 DSF 只获得 1× 图。用原生 1.5× 输出可保住文字边缘。保留 LCD 子像素文字时，同一原生 1.5×、JPEG 75 的两张最大化画面误差为 9.03 和 9.20。以下为启用灰阶文字后的质量比较，每格为 gzip KiB 与误差。

| CSS 尺寸与画面 | JPEG 65 | JPEG 70 | JPEG 75 | JPEG 80 | JPEG 85 |
|---|---:|---:|---:|---:|---:|
| 1280×800 表格 | 216.0 / 5.86 | 232.6 / 5.23 | 247.7 / 4.63 | 272.3 / 3.91 | 305.0 / 3.24 |
| 1920×1080 表格 | 311.7 / 4.94 | 335.4 / 4.41 | 362.3 / 3.89 | 400.0 / 3.29 | 442.3 / 2.73 |
| 1920×1080 表格及图表 | 264.6 / 5.02 | 284.5 / 4.53 | 306.5 / 3.98 | 337.5 / 3.36 | 374.4 / 2.78 |

保留统一质量 75，最大化小字误差约 4，大小比质量 80 少约 9%。LibreChat 按客户端支持压缩 SSE 并逐块刷新。[Node.js zlib 流式刷新](https://nodejs.org/api/zlib.html#flushing)

### 限速浏览器复测

本地 Chromium 153.0.8010.12 加载实际的沙箱面板，经 LibreChat 的 Pico 路由、Pico API 和 worker，本地测量使用独立测试身份。链路双向各 97 ms，共享下行 5.5 Mbps，512 KiB 校准请求约 0.98 s。DPR 1.5，从 720×700 调到 1920×1080。点击测到按钮变色上屏，最大化测到 2880×1620 帧出现新布局标记，滚动按 8 秒内实际变化的画面计数。小字用同一 CSS 尺寸和原生 DPR 走一遍相同尺寸变化后截取的 PNG 作参考。

| 画面（三轮） | 点击到新帧 | 最大化到清晰帧 | 滚动中位数 | 清晰帧小字误差 | 动态 / 清晰 gzip KiB |
|---|---:|---:|---:|---:|---:|
| 表格 | 356–378 ms | 1361–1501 ms | 2.63 帧/s | 3.65 | 53.4 / 420.2 |

表格复测的分段样本，单位为 ms。滚动行从浏览器发出对应滚轮请求计时，沿用同一视口。

| 样本 | 操作 → 发尺寸 | 前端请求 → worker 收到 | worker 收到 → metrics 完成 | metrics 完成 → Chromium 出帧 | Chromium 出帧 → worker 发送 | worker 发送 → 网页收完 | 网页收完 → 解码显示 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 最大化，第 2 轮清晰帧 | 16 | 178 | 64 | 281 | 8 | 744 | 70 |
| 滚动，第 3 轮动态帧 | — | 139 | — | 284（从 worker 收到起） | 77 | 186 | 30 |

同一张最大化表格图上，动态 JPEG 试过 1×/质量 30、0.8×/35、0.75×/32 和 0.65×/30，gzip 后分别约 103、70、83、51 KiB。选用 0.65×/32，保留原生 JPEG 75 作为清晰帧。原生 WebP 100 的同一表格帧 gzip 约 114 KiB，试拍从尺寸请求算起需 649–703 ms，原生 JPEG 75 为 311–431 ms。本轮保留 JPEG 的帧格式和质量。

最大化 <1 s 仍未达。生产俄勒冈链路、10 个会话的混合办公负载和统筹老师试用待部署后验证。

对账测试页在 `scripts/night-sandbox/sandbox-latency-fixture.html`，合入后通过 GitHub HTML Preview 渲染公开仓库里的 HTML。自备 HTTPS 地址时可用 `node scripts/night-sandbox/p-sandbox-latency.mjs --print-fixture` 导出同一份页面。表格加图表模式用 `chart=1`，可加在下方现网测试页 URL 的末尾（`&chart=1`）。现网经 GitHub 加载测试页，河源侧偶尔连不上。开页返回 `sandbox.fetch_failed` 或 60 秒内未画出测试页时整轮重来，每轮最多尝试三次，报告的 `retries` 按轮记录重来次数。

使用专用测试老师。同一账号不要并发跑。每次尝试先确认账号无开着的桌，再开新对话发送「打开 URL」，由对话开页并挂到右栏。收尾时，若云端任务仍在运行，先点停止并等停止按钮消失（最多 30 秒），再通过 `DELETE /v1/sandbox/sessions/current` 逐张关桌，最多删五次，直到 `GET current` 返回 404。关桌依赖 pico#1459 的 `current` 删除修复。收尾成功后才可重试。末轮收尾后额外查询一次 `current`，报告中 `currentMs` 记录这次 404 的请求耗时（毫秒）。脚本需要支持 CDP 虚拟显示器的 Chromium 153，可用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指定可执行文件。

本地邮箱登录使用 `PICO_E2E_EMAIL` 和 `PICO_E2E_PASSWORD`。现网用建校演练校的 `drill.*` 任课老师，`--edu-school` 必填，`--edu-base` 默认 `https://edu.weiyuji.cn`。以 `drill.t701` 为例，依次读取 `ACCEPT_PASSWORD_DRILL_T701`、`EDU_ACCEPT_PASSWORD`、`EDU_SMOKE_PASSWORD` 中首个已设置的口令。

```bash
node scripts/night-sandbox/p-sandbox-latency.mjs --base-url http://127.0.0.1:3090 --limit --fixture-url "$FIXTURE_URL"
node scripts/night-sandbox/p-sandbox-latency.mjs --base-url https://pico.aivia.asia \
  --edu-login drill.t701 --edu-school dd792255-de1c-4c6e-a750-5b15c7a213c1 \
  --fixture-url 'https://htmlpreview.github.io/?https://raw.githubusercontent.com/juanwan99/pico/main/scripts/night-sandbox/sandbox-latency-fixture.html?pico-latency=1'
```

每次运行三轮，报告和清晰帧 JPEG 原图写到 `.gpt-out/sandbox-latency/`。连接本机时另存原生 DPR 参考 PNG，按原像素计算小字 RMS，门限为 5。连接现网时报告点击和最大化时延、滚动帧率，小字清晰度用保存的 JPEG 原图放大核对。未达自动测量阈值时命令退出 1。

### 容量测量

返修 3 在一个本地 Chromium 实例开 10 个 context，每个 3 个跨站标签，1920×1200 CSS px、DPR 2。十路各完成六次点击及取帧，关桌后虚拟显示器全部移除。按进程树采样，单桌两标签为 494.4 MiB PSS、85 个线程，三标签为 517.8 MiB PSS、97 个线程。十桌并行操作的样本峰值为 2076.7 MiB PSS、396 个线程。这次采样覆盖浏览器和测试进程，混合办公负载和 tmpfs 的容器账见上一轮数据。

上一轮在本地 Linux 容器中用 cgroup v2 测量。十个老师各一个 Chromium context，每个 context 打开分属三个站点的标签，浏览器 1920×1200 CSS px、DPR 2。每个会话同时保留 Word、Excel、PPT 窗各一个，共 30 对 Xvfb + soffice。办公窗全部打开后十路浏览器各完成六次点击及取帧。第 11 个会话由现有会话额度拒绝。测量为每个 Xvfb 分配独立显示号，统计内存和 PID 容量。

| 负载 | cgroup 内存 | PID 计数 |
|---|---:|---:|
| worker + 空闲 Chromium | 1092 MiB | 55 |
| 1 个会话、2 个标签 | 1334 MiB（增加 242 MiB） | 89（增加 34） |
| 1 个会话、3 个标签 | 1427 MiB（增加 335 MiB） | 100（增加 45） |
| 10 个会话、30 个标签 | 峰值 5.46 GiB | 峰值 463 |
| 10 个会话、30 个标签、30 个办公窗，浏览器并行操作 | 峰值 7.55 GiB | 峰值 660 |

内存统计已包括文件缓存、`/tmp` 中的 profile 和共享内存。混合负载结束前采样到 `shmem` 约 1.33 GiB，其中含已解除链接的 Chromium 共享内存，`/dev/shm` 实测占用为 0。混合负载复测的 `memory.events` 中 max、oom、oom_kill 和 `pids.events` 中 max 均为 0。Compose 使用 9 GiB 和 1024 PID，运行时与 Compose 都设 10 个会话，启动中的会话先占额度。

未启用 init 的对照容器在两轮压测退出后累积了 305 个僵尸进程。Compose 启用 Docker 的 init 回收孤儿进程。复测关掉十个会话后，容器剩 3 个 PID（含采样进程），僵尸进程为 0。现网十会话仍需部署后重测。[Docker Compose init](https://docs.docker.com/reference/compose-file/services/#init)
