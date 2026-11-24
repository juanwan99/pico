# Pico 工作台可靠性盘点 · #1419

盘点窗口为 2026-10-25 13:00 至 11-24 13:00 UTC。11-24 工作台打不开，卡面定位到 ECS 公网上行约 5.5 Mbps 跑满，主要流量是 ap-gpt 经俄勒冈代理上传。浏览器开页时，23 个静态包当时每次都从 ECS 跨洋回源，卡面抽测一个约 630 KB 的包用了 21 秒。俄勒冈 nginx 当场为 `/assets/` 开缓存，同一个包降到 0.6 秒。公网抽查确认有 `X-Pico-Edge-Cache: HIT`，而 `/login` 的 3 秒探测曾超时。缓存解决重复回源，登录、鉴权、对话和冷缓存仍要访问 ECS。[事故卡](https://github.com/juanwan99/pico/issues/1419)

## 30 天错误与重启

| 要取的量 | 本轮证据 | 补齐口径 |
|---|---|---|
| pico-api、LibreChat 容器错误与重启次数 | 缺原始日志和 Docker 事件。挂载的 `/data/ops/logs` 下只见 edu-core。允许查询的 PostgreSQL 中 Pico 相关表为 edu 的钱包和策略数据 | 从 `/opt/pico` 的生产 compose 导出窗口内两服务的带时间戳日志，按容器实例合并窗口内的 `start`、`die`、`oom` 事件。逐服务按日计被替换的容器和同实例重启，区分发版与意外退出 |
| true_pi 错误与重启次数 | 缺生产原始日志。真 Pi 按会话启动，Compose 的 `pi-runner` 容器与会话进程的重启是两个量 | 导出 `pi-runner` 容器日志及 pico-api 中对应的 Pi RPC 退出、续跑记录。用 `run-continuity-report.py --days 30` 对账受重启中断的运行和结局。正常开关会话单列 |
| 公网 5xx | 缺俄勒冈和 ECS 的 access/error log。单次 `public-502-monitor.sh` 为 `/login` 200、`/health` 200。另有一次 3 秒探测收到 0 字节 | 从两端轮转日志按小时统计 `status` 和 `upstream_status`，按路径与时间关联边缘 5xx、回源 5xx 和超时。用 `pico-upstream-failure-report.py --days 30` 从账本另计模型上游失败，避免把模型 502 与公网 502 相加 |

三项 30 天总量均为**未知**。取证需平台运维把窗口内的日志、事件及聚合计数提供到该线的只读挂载。当前探测只覆盖其请求时点，Docker 当前实例的 `RestartCount` 也无法还原已替换实例的 30 天历史。[现有巡检与记录](./OPS-WATCH.md)

11-24 公网复测版本为 `eea8d046b270893c19eea06314b4b6fbedc6e1df`，`/login` 0.373 秒，`/api/pico/tip` 0.625 秒，当前 HTML 中 23 个 JS/CSS 包均是 HIT。初测 `/login` 的 3 秒超时仍计作失败。公网登录和聊天缺演练账号，本次没有做完。

### 窗口内已能定位的问题

| 时间 | 现象和根因 | 修复及状态 |
|---|---|---|
| 10-28 | ECS 到当时的 dmit 公网回程丢包，发版末尾 tip 返回 000。另有后台读卷共用聊天上游名额，让侧栏聊天等 186–207 秒 | 当时发版探针走 Tailscale；后由 11-14 和 11-18 的变更接替。读卷已分开上游名额。[回程丢包](https://github.com/juanwan99/pico/pull/1367) · [读卷挤占](https://github.com/juanwan99/pico/pull/1368) |
| 11-01 | SQLite 初始化在每次对话重跑迁移和清账本，争用写锁，模型 1–2 秒的调用经 Pico 要 30–100 秒。Pico 备份也曾和 edu-core 同抢代理，2.14 GB 用了 2 小时 50 分 | SQLite 初始化已经改为每进程一次。备份超时和完整性处理已修，共用出口的带宽争用仍在。[SQLite](https://github.com/juanwan99/pico/pull/1374) · [备份](https://github.com/juanwan99/pico/pull/1377) |
| 11-14 | dmit 停机，旧 Tailscale IP 仍被发版探针固定使用，冒烟假报 11/12。侧栏两行 CSV 上传等 110 秒，上传请求同步等 Meili 投影 | tip 去掉旧 IP，恢复公网探测。文件先落地，Meili 投影放后台。[旧探针](https://github.com/juanwan99/pico/pull/1405) · [Meili](https://github.com/juanwan99/pico/pull/1406) |
| 11-16 起 | ECS 直连工作台公网 TCP 失败，发版 tip 检查受影响 | 11-18 已改为经本机出口代理做公网 tip 检查。[发版探针改道](https://github.com/juanwan99/pico/pull/1413) |
| 11-18 | 推理把输出额度用完且无正文，重复原样重试仍可能空回 | 现有变更把该类空回标为 `output_exhausted`，不原样重试。[空回修复](https://github.com/juanwan99/pico/pull/1412) |
| 11-24 | ECS 上行跑满，首屏静态包重复跨洋回源 | 当班已在边缘开缓存。本卡将缓存配置纳入仓库，并用 nginx 的缓存锁合并同一静态包的并发首次回源。共享上传流量仍待平台侧处置。 |

## 单点及改法

| 单点 | 影响和依据 | 处置 |
|---|---|---|
| ECS 公网上行 | 静态冷回源、动态回复及 ap-gpt 上传共用同一条上行。11-24 已出现饱和 | 静态缓存落俄勒冈边缘。平台侧按 11-24 高峰的出口流量分来源复核，在既有上传端限速或错峰，为工作台动态流量留余量。带宽扩容及费用由业主决定 |
| 俄勒冈 nginx / 公网入口 | 本轮 DNS 查询只见一个 IPv4 地址。边缘失联时，热缓存也无法经这条公网路径送达。公开采样只能从外部看到结果 | 现有 `pico-ops-watch` 继续做公网和本机探测。缓存配置进仓，替换或恢复边缘时可复现。第二公网入口或托管 CDN 涉及拓扑，待业主决策 |
| Tailscale | 运维入口依赖 tailnet，旧发版探针也曾钉死 dmit tailnet IP。公网探针当前走出口代理。俄勒冈到当前 ECS 源站是否走 tailnet，须由平台运维从边缘 vhost 核实 | 保留现有公网探针，恢复时核对边缘真实回源地址与 tailnet 直连或中继状态。若回源经 tailnet 且无第二链路，边缘缓存只能减轻静态回源；备用回源链路由平台运维提出设计 |
| 单台 ECS 的 pico-api / LibreChat / Mongo / Pi runner | 生产 compose 在同一宿主运行；发布时 API 会重建，Pi 运行通过已有会话续跑。宿主丢失会同时影响动态服务 | 现有备份、恢复演练和续跑对账继续用。跨机恢复及数据库高可用是另一步设计。[生产 compose](../docker-compose.host.yml) · [备份与演练](./BACKUP.md) |

## 边缘缓存配置和发版验收

- 由平台运维在**俄勒冈边缘 nginx**现有 `http` 块引用 [缓存区配置](../deploy/nginx/pico-edge-cache-http.conf)，在同一 vhost 当前 `/assets/` 回源 location 引用 [缓存指令](../deploy/nginx/pico-edge-cache-assets.inc)。替换同作用域的临时缓存指令，沿用当前回源地址和代理请求头。缓存遵循 LibreChat 返回的 `s-maxage`、`Vary` 和 `no-store`，静态包换哈希即换缓存键。[nginx 代理缓存指令](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache)
- 在该 location 生效的现有安全响应头所在作用域加入 `add_header X-Pico-Edge-Cache $upstream_cache_status;`。对象使用完整 Host 与请求 URI，登录、API 和聊天仍走各自的原回源 location。运维侧先 `nginx -t` 再 reload。
- 发版后从公网客户端运行 `bash tests/acceptance/reliability-live.sh`。准备 curl 7.84+、Python 3、Node 和 LibreChat 的现有 Playwright 依赖及 Chromium，使用专用演练账户的 `PICO_E2E_EMAIL`、`PICO_E2E_PASSWORD`。脚本验 `/login`、`/api/pico/tip` 在 3 秒内返回，从实际 HTML 提取首屏 JS/CSS（含旧浏览器引用的包）逐个验证 HIT，再用浏览器登录、发送一句话、等助手的完整回复。部署产生新哈希后的冷缓存也按实测判定，MISS 会报失败。
- 现有 `bash scripts/e2e-smoke.sh --prod` 仍是 ECS 发版自身的合同检查；工作台公网验收单独从用户网络路径跑。

## 本次清理

全仓按文件名、模块名和 compose／Dockerfile／CI 入口检索，再看文件内实际职责。历史证据和仍有独立手动入口的巡检脚本保留。

| 删除项 | 依据 |
|---|---|
| `scripts/retire-dify-ecs.sh` | 一次性停用旧 Dify 用户服务、移走旧目录和密钥。现行架构已记录 Dify 退役（EXPERIENCE §28）。基线全仓仅脚本自身含旧服务名，无入口、测试或 compose 引用 |
| `deploy/nginx/workbench.aivia.asia.retired.conf` | 旧迁移时返回 410 的备用副本。现行 owner 控制台用 `deploy/nginx/workbench.aivia.asia.conf`，`apply-gateway-nginx.sh` 只读取现役配置。基线无任何文件名引用，无测试或 compose 挂载 |
| `docs/DAY-TASK-DEPLOY-CAP-9e0ce68.md` | 旧一次性发版卡，命令只服务固定旧 SHA `9e0ce68`。基线全仓查文件名、卡名和 SHA 均只命中该文档，无运行入口或测试。发布核对现在以 `AGENTS.md` 和 `prod-update` 为准 |
| `scripts/cutover-brain-to-newapi.py` | 一次性把原有 AIProxy 直连配置迁到 New API，全仓只命中脚本自己的用法。现行运行已走 New API，脚本无测试或 compose 入口，且直接重建生产容器绕过现行发版流程 |
| `scripts/wire-brain-via-newapi.py` | 同一次迁移的旧渠道初始化脚本。它覆盖指定渠道配置，并以 `stream: false` 试 Responses，已经与 EXPERIENCE §34 的流式合同冲突。全仓只命中脚本自己的用法，无测试或 compose 入口 |

## 给业主的讨论稿

先从已观察到的上传饱和着手。平台运维以工作台动态入口高峰时延和出口流量为依据，比较限速、错峰后是否还有持续拥堵，再决定是否值得升级 ECS 上行。单边缘风险可比较托管静态 CDN 与第二个公网入口，重点核算回源路由和故障切换。涉及费用、拓扑变化时由业主拍板。

产品侧可讨论打开慢时的提示、断线返回后继续查看任务、短聊首字时间与长任务完成率的取舍。先用登录成功率和运行中断数据确认主要问题，再定是否需要调整界面、功能或模型。
