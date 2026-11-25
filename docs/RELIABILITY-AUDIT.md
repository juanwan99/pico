# Pico 工作台可靠性盘点 · #1419

盘点窗口为 2026-10-25 13:50 至 11-24 13:50 UTC。11-24 工作台打不开时，ECS 约 5.5 Mbps 的公网出口已经跑满。统筹抽测 ECS 到家宽机的 SSH 复用连接占 320–364 KB/s，rclone 经代理上传约占 250 KB/s。首屏当时每次跨洋回源拉 23 个静态包，抽测一个约 630 KB 的包用了 21 秒。俄勒冈边缘 nginx 当班为 `/assets/` 开缓存，同一个包降到 0.6 秒。登录、鉴权、对话和冷缓存仍要访问 ECS。[事故卡](https://github.com/juanwan99/pico/issues/1419)

## 30 天错误与重启

证据为统筹在 11-24 05:50 PST 导出的 `/data/gpt/in/pico-1419-logs/`。巡检、备份和留痕时间用 PST。文件名里的 `30d` 是请求导出的范围。巡检实际有 407 轮和 3 条发信记录（11-22 20:00 至 11-24 05:50），备份 journal 有 127 行（11-22 21:00 至 11-24 05:00）。容器的错误行是筛选后的摘录，pico-api 的日志覆盖现存实例。各层按自己的记录计数，同一请求可能跨层出现。

| 证据 | 导出内计数 | 根因与改法 |
|---|---|---|
| pico-api | 41 行。18 条 loopback `POST /v1/chat/completions` 502、4 条读卷 Gemini 429 后试备用、4 条 Meili 投影 `RuntimeError`、5 组 SQLite 关闭连接时 `CancelledError` | 读卷日志明确报上游额度耗尽，复用已上线的上游重试和备用链。18 条 502 缺请求 ID 和响应正文，暂无法逐条归因。投影 `RuntimeError` 缺内部栈，不能与 Meili 的 7 条 503 一一对上。连接关闭遭取消，摘录缺时间和触发上下文，需和完整日志、实例退出时间及续跑结局对账 |
| LibreChat | 1 条启动警告，导出无 5xx | `RAG_API_URL` 未配置，LibreChat 启动仍检查其 `/health`。生产 compose 使用 Pico 的文件与知识路径，现有日志无证据表明这条警告导致上传失败 |
| true_pi / pi-runner | 412 条内部模型代理 503，其中 410 次 `/chat/completions`、2 次 `/responses`（10-28、10-29、10-30 分别 53、135、224 条） | Pi 请求已到 pico-api 的 `/internal/ws-proxy/l/…/v1/`。当前代理会透传上游错误。摘录没有响应体或同期 New API 渠道日志，具体渠道根因待对账。按现有 `pico-upstream-failure-report.py` 统计账本失败，用 `run-continuity-report.py` 对账运行中断和续跑 |
| Meili / Mongo / 其他容器 | Meili 7 条嵌入 503，每条附 1 行响应正文。Mongo 94 条均为 INFO。网关、office 和 sandbox 共 4 份错误摘录均为空 | Meili 的 New API 响应明确为 CPU 99.8% 超过 90% 阈值。由平台侧对齐 CPU 高峰和嵌入流量，已有后台投影路径承接索引写入。Mongo 是 WiredTiger 启动或检查点信息 |
| 公网 5xx | 本次缺俄勒冈和 ECS 公网访问日志。巡检有 280 轮公网 BAD、127 轮 OK、0 轮本机 health BAD | 这些轮次记录了探测结果。公网 5xx 总量需按两端的 `status` / `upstream_status` 和时间核算，区分边缘超时、回源失败和模型 API 错误 |
| 当前容器重启与替换 | 9 个现存实例全为 `RestartCount=0`。LibreChat 和 pi-runner 当前实例始于 10-26 23:15 UTC，pico-api 当前实例始于 11-23 23:49 UTC，另有 11-23 02:15 PST 重建记录。Docker 事件和 OOM 导出均为空 | 实例替换会重置容器计数。30 天累计启动、替换、异常重启以及 Pi 会话进程重启次数仍缺完整证据。需用带实例标识的部署或 Docker 事件及 Pi 会话记录对账 |
| ops-watch 的其他检查 | New API relay 摘要记 397 次 429、0 次 403 或 5xx，24 轮达告警阈值。runs 有 1 轮检查自身超时，53 个滚动窗口看到任务失败，最高一窗 281 个任务中失败 35 个。构建缓存 0 轮 BAD。env 4 轮 BAD | 429 是渠道限流，汇总缺各渠道响应明细。滚动窗口重叠，任务故障须从账本按 run 去重。runs 超时发生于日备打包期间，缺锁和资源明细，暂未定位。用既有 `report` 和完整 journal 对账。.env 留痕情况见下节 |

### 11-23 至 11-24 的处置

| 时间 | 现象和根因 | 修复及状态 |
|---|---|---|
| 约 11-17 至 11-23 | ECS 巡检默认访问公开域名的 `/health`、`/login`，旧代码未显式指定出口代理。#1413 已记录 ECS 直连该域名 TCP 失败。导出起点已连败 1738 轮，11-23 15:50 达卡面所记的 1976 轮，19:15 达 2017 轮。11-23 的三次探针提醒记为 `sent`，19:20 已恢复，导出无恢复原因。没有当时的路由表和俄勒冈回源配置，ECS → 俄勒冈 → ECS 回环尚未证实 | ECS 公网巡检改走 #1413 发版冒烟使用的本机出口代理 `127.0.0.1:7893`，本机 API health 直连。手动 `public-502-monitor.sh` 在两条路径全窗均无成功响应时退出 1，仍生成采样和汇总。平台侧还要核对持续告警无人接手的流程 |
| 11-23 02:10–02:15 | 日备 02:10 起跑，02:10:51 开始 SQLite 在线拷库。02:15 本线按 edu-core#6121 第 3 步去掉 `PICO_BRAIN_FALLBACKS` 中的 `grok-4.6` 并重建 pico-api。02:15:55 容器内快照的 `docker exec` 拷出中断，日备报 `FAIL pico.db copy`。第二轮评审确认宿主缺 `sqlite3` 且定时器用户 `ops` 的 `sudo` 需要密码 | 用本地 `pico-api:v13` 镜像起一次性容器，从 `pico_pico_data` 卷以 `mode=ro` 在线拷库。容器内运行 `quick_check`，把快照交给备份目录属主，保留原 gzip 格式。这一步与运行中的 API 容器分离。后续 tar 和 Meili 仍通过运行中的容器导出 |
| 11-23 06:37–18:37、11-24 02:10 起 | 11-23 补跑 06:51 开始上传 2.7 GB，18:37 被 systemd 判超时。11-24 日备 02:26 开始上传 2.7 GB，导出截止无成功记录。03:00 新鲜度告警已到 38.5 小时。恢复演练无结果行 | 补跑从启动到退出是 12 小时，仓内 unit 配的是 6 小时。运维需核对实际加载的 unit 与 rclone 上传日志，以及最新 `COMPLETE` 和恢复演练。共享出口挤占已在 11-24 观察到，现有导出缺上传失败明细 |
| 11-23 02:15、15:50 | 两次本线变更未通过 `env-set` / `env-record`，巡检显示没留原因。前一条为 edu-core#6121 去掉 Grok 备用（业主定不换模型、不充 Grok，备份 `.env.bak-20261123-grok`），后一条为 pico#1344 把 `PICO_HEDGE_*` 从 off 改为 unset（备份 `.env.bak-1344-11231550`） | 卡面确认两条已补进 `~/pico-env-changes.log`。导出的全段留痕中有 14 条 `watch:UNLOGGED`，本次短窗内 4 轮。后续改配置用既有 `env-set` |

### 窗口内其他已定位的问题

| 时间 | 现象和根因 | 修复及状态 |
|---|---|---|
| 10-28 | ECS 到当时的 dmit 公网回程丢包，发版末尾 tip 返回 000。另有后台读卷共用聊天上游名额，让侧栏聊天等 186–207 秒 | 当时发版探针走 Tailscale；后由 11-14 和 11-18 的变更接替。读卷已分开上游名额。[回程丢包](https://github.com/juanwan99/pico/pull/1367) · [读卷挤占](https://github.com/juanwan99/pico/pull/1368) |
| 11-01 | SQLite 初始化在每次对话重跑迁移和清账本，争用写锁，模型 1–2 秒的调用经 Pico 要 30–100 秒。Pico 备份也曾和 edu-core 同抢代理，2.14 GB 用了 2 小时 50 分 | SQLite 初始化已经改为每进程一次。备份超时和完整性处理已修，共用出口的带宽争用仍在。[SQLite](https://github.com/juanwan99/pico/pull/1374) · [备份](https://github.com/juanwan99/pico/pull/1377) |
| 11-14 | dmit 停机，旧 Tailscale IP 仍被发版探针固定使用，冒烟假报 11/12。侧栏两行 CSV 上传等 110 秒，上传请求同步等 Meili 投影 | tip 去掉旧 IP，恢复公网探测。文件先落地，Meili 投影放后台。[旧探针](https://github.com/juanwan99/pico/pull/1405) · [Meili](https://github.com/juanwan99/pico/pull/1406) |
| 11-16 起 | ECS 直连工作台公网 TCP 失败，发版 tip 检查受影响 | 11-18 已改为经本机出口代理做公网 tip 检查。[发版探针改道](https://github.com/juanwan99/pico/pull/1413) |
| 11-18 | 推理把输出额度用完且无正文，重复原样重试仍可能空回 | 现有变更把该类空回标为 `output_exhausted`，不原样重试。[空回修复](https://github.com/juanwan99/pico/pull/1412) |
| 11-24 | ECS 上行跑满，首屏静态包重复跨洋回源。原缓存到期后，请求仍会等跨洋回源 | 当班已在边缘开缓存。本卡将缓存配置纳入仓库，用 nginx 的缓存锁合并并发首次回源，缓存到期后先发旧副本并在后台发起条件请求。共享上传流量仍待平台侧处置。 |

首轮公网复测在 `eea8d046b270893c19eea06314b4b6fbedc6e1df` 上测得 `/login` 0.373 秒、`/api/pico/tip` 0.625 秒、23/23 首屏包 HIT。此前同入口也出现过一次 3 秒超时。

## 单点及改法

| 单点 | 影响和依据 | 处置 |
|---|---|---|
| ECS 公网上行 | 静态冷回源、动态回复、SSH 复用和备份上传共用同一条上行。11-24 已出现饱和 | 静态缓存落俄勒冈边缘。平台侧按 11-24 高峰的出口流量分来源复核，在既有上传端限速或错峰，为工作台动态流量留余量。带宽扩容及费用由业主决定 |
| 俄勒冈 nginx / 公网入口 | 本轮 DNS 查询只见一个 IPv4 地址。边缘失联时，热缓存也无法经这条公网路径送达。公开采样只能从外部看到结果 | `pico-ops-watch` 经 ECS 出口代理探真实公网入口，本机 API 继续直连。缓存配置进仓，替换或恢复边缘时可复现。第二公网入口或托管 CDN 涉及拓扑，待业主决策 |
| Tailscale | 运维入口依赖 tailnet，旧发版探针也曾钉死 dmit tailnet IP。发版公网探针已走出口代理，本卡对齐定时巡检。俄勒冈到当前 ECS 源站是否走 tailnet，须由平台运维从边缘 vhost 核实 | 保留公网域名探针，恢复时核对边缘真实回源地址与 tailnet 直连或中继状态。若回源经 tailnet 且无第二链路，边缘缓存只能减轻静态回源；备用回源链路由平台运维提出设计 |
| 单台 ECS 的 pico-api / LibreChat / Mongo / Pi runner | 生产 compose 在同一宿主运行；发布时 API 会重建，Pi 运行通过已有会话续跑。宿主丢失会同时影响动态服务 | 现有备份、恢复演练和续跑对账继续用。跨机恢复及数据库高可用是另一步设计。[生产 compose](../docker-compose.host.yml) · [备份与演练](./BACKUP.md) |

## 边缘缓存配置和发版验收

- 由平台运维在**俄勒冈边缘 nginx**现有 `http` 块引用 [缓存区配置](../deploy/nginx/pico-edge-cache-http.conf)，在同一 vhost 当前 `/assets/` 回源 location 引用 [缓存指令](../deploy/nginx/pico-edge-cache-assets.inc)。替换同作用域的临时缓存指令，沿用当前回源地址和代理请求头。缓存遵循 LibreChat 返回的 `s-maxage`、`Vary` 和 `no-store`，静态包换哈希即换缓存键。[nginx 代理缓存指令](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache)
- 默认 24 小时的新鲜期结束后，边缘先送已有副本，再在后台用 ETag 或 Last-Modified 向源站校验。源站连接出错、超时或返回 502、504 时，边缘仍可送已有副本。[nginx 缓存更新与旧副本](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache_use_stale)
- 在该 location 生效的现有安全响应头所在作用域加入 `add_header X-Pico-Edge-Cache $upstream_cache_status;`。对象使用完整 Host 与请求 URI，登录、API 和聊天仍走各自的原回源 location。运维先运行 `nginx -t`。改动 `keys_zone` 对应的缓存路径时要 restart。其他改动 reload 后查 nginx `error.log`，确认本次加载没有 `emerg`。`systemctl reload` 可能返回 0，而 nginx 拒绝加载并继续使用旧配置。
- 每次发版可能换首屏包的哈希。发版冒烟通过后，`prod-update` 经 ECS 出口代理 `127.0.0.1:7893` 读取 `https://pico.aivia.asia/login` 并请求其中每个首屏包一次。预热和公网验收共用脚本，请求相同的浏览器缓存变体。取包失败时发版命令退出非零。[首屏包脚本](../scripts/pico-first-screen-assets.sh)
- 发版后从公网客户端运行 `bash tests/acceptance/reliability-live.sh`，需要 curl 7.84+ 和 Python 3。脚本核对 `/login`、`/api/pico/tip` 在 3 秒内返回，从实际 HTML 提取首屏 JS/CSS（含旧浏览器引用的包），使用 `Accept-Encoding: gzip, deflate, br, zstd` 检查浏览器使用的缓存变体。`HIT`、`STALE`、`UPDATING`、`REVALIDATED` 均算命中，`MISS` 会报失败。
- 第二轮从工作区测得现网同一版本的 `/login` 2.165 秒、`/api/pico/tip` 0.607 秒及 23/23 HIT。登录聊天待演练账号（待业主）。
- 现有 `bash scripts/e2e-smoke.sh --prod` 仍是 ECS 发版自身的合同检查。发版命令成功返回后立即从用户网络跑工作台公网验收，核对首次即 23/23 命中。

## 删除

以首轮修改后的 `90cf875c` 为基线，用 `git ls-files` 遍历全仓，按文件名、模块名和导出名检索。复核 Python 导入、TS/JS 的 import、re-export 和动态加载、命令入口、测试、compose、Dockerfile、CI、Makefile、systemd 和文档引用。目录打包会带上整个源码树，实际使用按入口和模块引用核对。上游源码、仍有测试覆盖的路径、有历史证据链接或可能有外部调用的工具保留。

### 第一轮

| 删除项 | 依据 |
|---|---|
| `scripts/retire-dify-ecs.sh` | 一次性停用旧 Dify 用户服务、移走旧目录和密钥。现行架构已记录 Dify 退役（EXPERIENCE §28）。基线全仓仅脚本自身含旧服务名，无入口、测试或 compose 引用 |
| `deploy/nginx/workbench.aivia.asia.retired.conf` | 旧迁移时返回 410 的备用副本。现行 owner 控制台用 `deploy/nginx/workbench.aivia.asia.conf`，`apply-gateway-nginx.sh` 只读取现役配置。基线无任何文件名引用，无测试或 compose 挂载 |
| `docs/DAY-TASK-DEPLOY-CAP-9e0ce68.md` | 旧一次性发版卡，命令只服务固定旧 SHA `9e0ce68`。基线全仓查文件名、卡名和 SHA 均只命中该文档，无运行入口或测试。发布核对现在以 `AGENTS.md` 和 `prod-update` 为准 |
| `scripts/cutover-brain-to-newapi.py` | 一次性把原有 AIProxy 直连配置迁到 New API，全仓只命中脚本自己的用法。现行运行已走 New API，脚本无测试或 compose 入口，且直接重建生产容器绕过现行发版流程 |
| `scripts/wire-brain-via-newapi.py` | 同一次迁移的旧渠道初始化脚本。它覆盖指定渠道配置，并以 `stream: false` 试 Responses，已经与 EXPERIENCE §34 的流式合同冲突。全仓只命中脚本自己的用法，无测试或 compose 入口 |

### 第二轮

删除 51 个文件、3229 行。其中 44 份过期文档、5 个脚本、2 个 TS 模块。两轮合计删除 56 个文件、3647 行。下表的引用为基线文件名或去扩展名的检索结果，路径以仓根为基准。

| 删除项 | 依据 |
|---|---|
| `apps/librechat/client/src/components/Workbench/TaskListSection.tsx` | `git grep -i TaskListSection` 只命中本文件。旧轨道组件无 import、路由、导出或测试。当前任务列表入口为 `TeacherTaskHome` / `ConversationsSection` |
| `apps/librechat/client/src/hooks/Nav/useUnifiedSidebarLinks.ts` | `git grep -F useUnifiedSidebarLinks` 只命中本文件。无 import、导出或测试。当前 `Root` 加载 `UnifiedSidebar`，其 `Sidebar` 直接引用 `ConversationsSection` |
| `scripts/capture-result-open-in-pane.sh` | 文件名全仓零外部命中。仅为固定 `pack-result-open-in-pane` 历史截图渲染本地 HTML，无 CI / 定时器 / 测试入口 |
| `scripts/capture-sandbox-stage-grok.sh` | 文件名全仓零外部命中。仅渲染固定 `pack-sandbox-stage-grok` 本地历史截图，无 CI / 定时器 / 测试入口 |
| `scripts/capture-tasklist-fix.mjs` | 文件名全仓零外部命中。仅为固定 `pack-ui-tasklist-fix` 收图，无 CI / 定时器 / 测试入口。正式任务列表测试仍保留 |
| `scripts/capture_b2_real_browser_frames.py` | 文件名、模块名全仓零外部命中。只写固定 `pack-b2-real-browser` 历史证据截图，无 import、CI 或测试入口 |
| `scripts/oneflow-status.sh` | 文件名全仓零外部命中。旧 OneFlow 的本机提示工具，状态由 GitHub、CI 与公网 tip 直接提供，无定时器或测试入口 |
| `docs/DAY-TASK-2026-07-30-SKILL-UX.md` | #55/#56 已完成。命中旧索引已移除。仅命中 `docs/README.md` |
| `docs/DAY-TASK-CAP-GENERAL-P0.md` | 标准任务卡 · T-CAP-GENERAL-P0，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-CAP-GENERAL-P1.md` | 标准任务卡 · T-CAP-GENERAL-P1，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-CAP-HEURISTIC-DEEP.md` | 标准任务卡 · T-CAP-HEURISTIC-DEEP，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-CLAIM-WB-DEGREE-WEB.md` | 标准任务卡 · T-CLAIM-WB-DEGREE-WEB，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-E2E-DEFAULT-CHAT.md` | 标准任务卡 · T-E2E-DEFAULT-CHAT，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-HUMAN-DELIVERY-SURFACE.md` | 标准任务卡 · T-HUMAN-DELIVERY-SURFACE，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-N2-PROXY-RUNONCE.md` | 热修 · N2 UI 运行一次 proxy 路由，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-OPS-TRUE-PI-HYGIENE.md` | 日卡 · T-OPS-TRUE-PI-HYGIENE，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-P0-SECURITY.md` | 日间任务书 · P0 安全收口（执行），旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-P1-WB-SURFACE.md` | 标准任务卡 · T-P1-WB-SURFACE，旧一次性任务。仅命中 `docs/TEST-TASK-P1-WB-SURFACE.md` |
| `docs/DAY-TASK-P2-EXTEND.md` | 标准任务卡 · T-P2-EXTEND，旧一次性任务。仅命中 `docs/TEST-TASK-P2-EXTEND.md` |
| `docs/DAY-TASK-PI-TRUE-KERNEL-P2.md` | 日卡 · T-PACK-PI-TRUE-KERNEL-P2，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-PUBLIC-ENTRY-HOTFIX.md` | 标准任务卡 · T-PUBLIC-ENTRY-HOTFIX，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-STAGE1-PUBLIC-WB.md` | 标准任务卡 · T-STAGE1-PUBLIC-WB，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-STAGE2-WB-POLISH.md` | 标准任务卡 · T-STAGE2-WB-POLISH，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-TRUE-PI-WB-LONGHAUL.md` | 日卡 · T-TRUE-PI-WB-LONGHAUL，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/DAY-TASK-WB-STYLE-W1-W5.md` | 标准任务卡 · T-WB-STYLE-W1-W5，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/HANDOFF-NEW-WINDOW-2026-08-11.md` | 8-11 总管交接采用旧目标口径，现况入口改为 STATE-NOW。文件名及去扩展名零外部命中 |
| `docs/HANDOFF-NEW-WINDOW-2026-08-23.md` | #634 明示 SUPERSEDED。旧索引链接已移除。仅命中 `docs/README.md` |
| `docs/TEST-TASK-CAP-GENERAL-P0.md` | TEST · T-CAP-GENERAL-P0，旧一次性任务。仅命中 `docs/DAY-TASK-CAP-GENERAL-P0.md` |
| `docs/TEST-TASK-CAP-GENERAL-P1.md` | TEST · T-CAP-GENERAL-P1，旧一次性任务。仅命中 `docs/DAY-TASK-CAP-GENERAL-P1.md` |
| `docs/TEST-TASK-CAP-HEURISTIC-DEEP.md` | TEST · T-CAP-HEURISTIC-DEEP，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/TEST-TASK-E2E-DEFAULT-CHAT.md` | TEST · T-E2E-DEFAULT-CHAT，旧一次性任务。仅命中 `docs/DAY-TASK-E2E-DEFAULT-CHAT.md` |
| `docs/TEST-TASK-HUMAN-DELIVERY-SURFACE.md` | TEST · T-HUMAN-DELIVERY-SURFACE，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/TEST-TASK-P1-WB-SURFACE.md` | 测试任务 · T-P1-WB-SURFACE，旧一次性任务。仅命中 `docs/DAY-TASK-P1-WB-SURFACE.md` |
| `docs/TEST-TASK-P2-EXTEND.md` | 测试任务 · T-P2-EXTEND，旧一次性任务。仅命中 `docs/DAY-TASK-P2-EXTEND.md` |
| `docs/TEST-TASK-PUBLIC-ENTRY-HOTFIX.md` | 测试 · T-PUBLIC-ENTRY-HOTFIX，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/TEST-TASK-WB-STYLE-W1-W5.md` | TEST · T-WB-STYLE-W1-W5，旧一次性任务。仅命中 `docs/DAY-TASK-WB-STYLE-W1-W5.md` |
| `docs/archive/CODEX-HOTUPDATE-PROMPT.md` | 早期 VPS 热更提示词。现行发版入口是 prod-update。文件名及去扩展名零外部命中 |
| `docs/archive/HANDOFF-CORRECTION.md` | 旧 Kimi / DeepSeek 交接附页。文件名及去扩展名零外部命中 |
| `docs/archive/I18N-CN.md` | 旧 LibreChat 汉化阶段说明。文件名及去扩展名零外部命中 |
| `docs/archive/KIMI-CONNECT.md` | 旧 Kimi 厂牌直连说明，模型路径已归 New API。文件名及去扩展名零外部命中 |
| `docs/archive/SPRINT-2H.md` | 早期两小时冲刺记录。文件名及去扩展名零外部命中 |
| `docs/archive/WORKBENCH-CLICK-MAP.md` | 旧界面对齐点击地图。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N5-FAILED-RUN-VISIBLE.md` | 日间任务 · N5 失败/取消 Run 可见，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N6-RATELIMIT-MEMBERSHIP.md` | 日间任务 · N6b 限流键优先 membership，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N6-SKILL-HUB-TOOLS.md` | 日间任务 · N6 能力中心展示技能工具绑定（只读），旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N7-CANCEL-ROOTFIX.md` | 日间任务 · N7 停止根治（VQ-006 二次 FAIL），旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N7-CANCEL-RUN.md` | 日间任务 · N7 运行中取消（最小），旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N7-EVENT-SEQ-UNIQUE.md` | 日间任务 · N7b 事件序号约束（底座），旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N7-HISTORY-RUN-TIMELINE.md` | 日间任务 · N7 历史任务打开 Run 时间线，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/DAY-TASK-N8-UNKNOWN-SKILL-NO-ARTIFACT.md` | 日间任务 · N8 未知 skill 禁止旁路产物，旧一次性任务。文件名及去扩展名零外部命中 |
| `docs/archive/completed-tasks-2026-07/NIGHT-CARD-N4-THICK.md` | 任务卡 N4-THICK · 先收口 N3 债 · 再 Skill/体验加厚，旧一次性任务。文件名及去扩展名零外部命中 |

### 待核，保留

- `docs/HANDOFF-WB-PI.md` 仍被 `TRUTH-FREEZE` 和产品合同引用。其余留在 `docs/archive/` 的内容有历史记录链或仍被现行文档引用，例如 `DEPLOY-PUBLIC.md` 引用过往部署证据，`DEAD-CODE-SWEEP.md` 保留诊断样本索引。仍有引用的成对旧任务书和模板一并保留。
- `publish_confirm.py` 仅有测试导入，`test_html_public_api.py` 用真签名确认令牌验证 Pico 发布入口依旧拒绝，另有单测钉住令牌行为。`prefetch_models.py` 由两个 Pico API Dockerfile 执行，`fetch_mermaid.py` 和 `fonts/mpl_cjk_defaults.py` 由 sandbox worker 的 Dockerfile 执行。`pi_runner/attack_test.py` 是可手动运行的 runner 安全验证，外部调用待核。
- `scripts/night-sandbox/`、`scripts/pico-*-report.py`、`scripts/pico-my-endpoint-check.py`、`scripts/check-deploy-channel.sh`、`scripts/preview-diagnose.mjs`、`scripts/vps-*.sh`、云端工位启动和证书脚本可能由验收窗、外部运行手册或计划任务直接运行。`scripts/t-result-open-in-pane-helpers.mjs` 仍可手动核对在用的预览行为。上述命令的外部使用待核。当前 systemd 单元、compose 构建配置与边缘 nginx 配置有明确用途。
- LibreChat 上游目录内零入边的候选还包括组件、诊断工具以及运维命令，需核上游同步范围、配置与发行入口。未因零文本命中删除上游工具、fixture 或现行回归测试。

## 给业主的讨论稿

先从已观察到的上传饱和着手。平台运维以工作台动态入口高峰时延和出口流量为依据，比较限速、错峰后是否还有持续拥堵，再决定是否值得升级 ECS 上行。单边缘风险可比较托管静态 CDN 与第二个公网入口，重点核算回源路由和故障切换。涉及费用、拓扑变化时由业主拍板。

产品侧可讨论打开慢时的提示、断线返回后继续查看任务、短聊首字时间与长任务完成率的取舍。先用登录成功率和运行中断数据确认主要问题，再定是否需要调整界面、功能或模型。
