# pico 备份（pico#1270）

每天 02:10（ECS 用户定时器 `pico-backup.timer`）把 pico 的数据打包，传到本机以外的 Google Drive `gdrive:pico-backup/<时间戳>/`，保留 15 天。脚本：`scripts/backup-pico.sh`，定时器：`deploy/systemd/pico-backup.*`。

| 文件 | 内容 | 怎么导 |
|--|--|--|
| `mongo.archive.gz` | LibreChat 对话 | `mongodump --archive --gzip` |
| `pico.db.gz` | 任务、账本（pico_data 里的 sqlite） | sqlite 在线 backup，上传前 `quick_check` |
| `pico-data.tgz` | pico_data 其余（会话、记忆）；不含 `*.bak*` 临时副本 | tar |
| `teacher-disks.tgz` | 老师盘 | tar |
| `librechat-files.tgz` | LibreChat 上传和图片 | tar |
| `SHA256SUMS` | 以上校验 | |

Meilisearch 不备份（卡上合同）：索引从 pico.db 账本重建，见下面「真恢复」第 5 步。

- 大于 128 MB 的文件切成 `名字.part-000…` 分段上传：代理会在单个上传约 10 分钟后断开，分段后断了只重传那一段。`SHA256SUMS` 记的是整文件，演练时先拼回再校验。
- 上传后用 `rclone check --size-only` 对一遍远端；本地临时目录随即删掉（不占盘）。
- 失败：写 `~/logs/pico-backup-status.json`（state=FAIL），并用 `~/scripts/edu-backup-alert.py` 发信。日志 `~/logs/pico-backup.log`。
- 没跑起来（定时器停了、机器宕了）不会写 FAIL：`pico-backup-watch.timer` 每小时看一次，上次成功超过 26 小时就发信（12 小时内只发一封）。
- 通道：ECS 直连 Google 不通，走本机 sing-box 代理 `127.0.0.1:7893`（和 edu-core 备份同一个 rclone `gdrive` 远端）。

## 恢复演练

`bash scripts/backup-pico.sh drill`：拉最新一份，进临时容器恢复（`--network none`，不碰现网），打印：
- mongo 各集合条数；
- pico.db `quick_check` 和 runs 条数；
- 各 tar 的条目数。

## 真恢复（出事时，人工）

1. 停对应容器。
2. mongo：`docker exec -i pico-mongo-1 mongorestore --archive --gzip --drop < mongo.archive.gz`。
3. pico.db：解压后替换 pico_data 里的 `pico.db`（先删 `pico.db-wal` / `pico.db-shm`）。
4. tar：解到原卷。
5. meili：起空库后在 api 容器里 `curl -X POST 'http://127.0.0.1:18765/v1/kb/reindex-all?force=1'`，从账本重投影（不再 OCR，见 `docs/KB-INGEST-FORMATS.md`）。
