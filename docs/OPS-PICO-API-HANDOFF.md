# Pico API 发版交接（#1474）

在 `/opt/pico` 按现有方式运行 `prod-update.sh`。edu 继续经原来的两跳 socat 接入。第二跳、LibreChat、pi-runner 和发版探针继续连 `127.0.0.1:18765`。Nginx stream 持有这个 loopback 监听，API 在 loopback 的 18769、18770 之间交接。

Linux 在关闭 `SO_REUSEPORT` 的旧监听 socket 时，默认会丢掉握手中及 accept 队列里的连接。因此这里用 Nginx 的原生平滑重载。HUP 由新 worker 继承监听，旧 worker 停止接受新连接，并继续服务已经接受的 TCP 连接。stream 转发保留 HTTP、SSE、WebSocket 和 TCP 半关闭语义。 [Linux 内核文档](https://docs.kernel.org/networking/ip-sysctl.html#tcp-migrate-req) · [Nginx 重载文档](https://nginx.org/en/docs/control.html)

## 发版顺序

1. 保留构建后的在飞任务等待。配置或镜像有变化时，用 Compose 保留旧容器并创建另一端口的候选容器。
2. 启动候选，按容器 ID 和候选端口查 `/health`。确认 `ok`、目标 `git_sha` 和实际监听端口，再重载 Nginx。候选日志读取失败也会执行回退。首次迁移回退先停候选、恢复旧 API，然后删除候选。
3. HUP 后立即从 18765 核对目标 SHA 和候选端口。失败时重载旧配置，确认旧 API 已经接流再停候选。成功后等旧 worker 排空，再停止并删除旧 API。Nginx 排空和 API 停止各有 60 秒宽限。保留原运维容器名，后端端口通过 `env-set` 写入本机 `.env` 并记录发版原因。Nginx 配置保存在 `data/pico-api-listener/`。
4. 继续现有的 office、edu 网关、Meili、UI 和 `bash scripts/e2e-smoke.sh --prod` 检查。

首次从旧版迁移时，旧容器占用 18765，也没有后台锁。它须先停止，候选启动后再由 Nginx 接住 18765。这一次存在空窗。迁移后两个后端都走平滑交接。回退到采用本方案的旧 SHA 沿用同一流程。回退到迁移前的 SHA 时，在切换 checkout 前先在 `/opt/pico` 运行 `docker compose -f docker-compose.host.yml stop pico-api-listener`，再走原发版入口。这种回退也存在空窗。

发版中断后重跑时，若还留有两个 API 容器，脚本会用 18765 的健康响应确认正在接流的实例，再排空 worker 并收尾另一实例。

## 重叠期后台与账本

| 工作 | 交接行为 |
| --- | --- |
| Lifespan 的配置和 SQLite 初始化 | 候选校验配置并建表、迁移，旧进程继续处理请求。初始化由 SQLite 串行处理各次写入。历史 `usage_events` 清理完成后记入 `PRAGMA user_version`，后续启动跳过全表扫描。普通请求仍用 WAL、现有 busy timeout 和账本事务。 |
| 孤儿清理和工作区 run 恢复 | 持有后台文件锁的进程只恢复存活锁已释放或旧版无归属的 run。每笔新 run 记录本进程的归属，恢复后归属迁到当前进程。旧实例停止时只清理自己的遗留 run。存活锁先于后台锁释放。接管失败写日志并独立重试，HTTP 持续在线。 |
| Automation 定时任务 | 后台锁持有者启动 scheduler。旧实例先停 scheduler，再排空本进程在飞 run，最后释放锁。候选在等锁期间正常响应 HTTP。 |
| KB reindex | 全库入口共享排队锁，保留重复增量请求的已在跑回执和重复强刷的 409。全库和会员重建还共享 Meili 写锁。索引准备和文档批次的写入都在提交与状态轮询处分开。取消时等当前提交拿到 `taskUid` 即释放锁，下一次重建沿用 Meili 的待处理任务检查。发版在旧容器退出后调用现有 reindex 入口。 |
| 请求触发的工作 | REST、聊天、手动 automation 和 durable job 从各自收到的请求创建 run。文件投影和交付归档仍由对应请求或 run 触发。它们继续写原账本，由 SQLite 串行提交。 |
| Pi 模型调用中的附件 | `true_pi/runtime.py` 调用 `llm_file_pass.pass_base_url()` 生成直连地址。盒内请求经 runner 进入 `ws_llm()`，再用同一地址发起进程内回环调用。这个地址优先使用 `PICO_API_BACKEND_PORT`，让旧 API 在交接期间继续从自己的内存读到附件原件。runner 进入 Pico 仍使用 18765。 |
