# pico 备份（pico#1270）

每天 02:10（ECS 用户定时器 `pico-backup.timer`）把 pico 的数据打包，传到本机以外的 Google Drive `gdrive:pico-backup/<时间戳>/`，保留 15 天。脚本：`scripts/backup-pico.sh`，定时器：`deploy/systemd/pico-backup*.{service,timer}`。

**只留这一套。** 原先 edu-core 的 `edu-backup-pico.timer`（每天 03:40，`edu-backup-ops.sh run-pico`，只备老师盘 + mongo 到 `gdrive:edu-backup/pico/`，不含 pico.db、pico_data、LibreChat 上传，没有演练和新鲜度告警）在本卡上线时停掉并 disable，edu-core 侧同步删掉安装项。旧备份留在 `gdrive:edu-backup/pico/`，由 edu 的 prune 按 15 天自然过期。

| 文件 | 内容 | 怎么导 |
|--|--|--|
| `mongo.archive.gz` | LibreChat 对话 | `mongodump --archive --gzip` |
| `pico.db.gz` | 任务、账本（pico_data 里的 sqlite） | sqlite 在线 backup，上传前 `quick_check` |
| `pico-data.tgz` | pico_data 其余（会话、记忆）；不含 `*.bak*` 临时副本 | tar |
| `teacher-disks.tgz` | 老师盘 | tar |
| `librechat-files.tgz` | LibreChat 上传和图片 | tar |
| `meili.dump` | Meilisearch 索引（含向量）。从账本重建要把全库重新打一遍嵌入，又慢又花钱、还冲上游，所以照备 | `POST /dumps` |
| `SHA256SUMS` | 以上校验 | |

- 大于 128 MB 的文件切成 `名字.part-000…` 分段上传：代理会在单个上传约 10 分钟后断开，分段后断了只重传那一段。`SHA256SUMS` 记的是整文件，演练时先拼回再校验。
- 上传后用 `rclone check --size-only` 对一遍远端；本地临时目录随即删掉（不占盘）。
- 失败：写 `~/logs/pico-backup-status.json`（state=FAIL），并用 `~/scripts/edu-backup-alert.py` 发信。日志 `~/logs/pico-backup.log`。
- 没跑起来（定时器停了、机器宕了）不会写 FAIL：`pico-backup-watch.timer` 每小时看一次，上次成功超过 26 小时就发信（12 小时内只发一封）。
- 通道：ECS 直连 Google 不通，走本机 sing-box 代理 `127.0.0.1:7893`（和 edu-core 备份同一个 rclone `gdrive` 远端）。

## 恢复演练

`bash scripts/backup-pico.sh drill`：拉最新一份，进临时容器恢复（`--network none`，不碰现网）。`pico-backup-drill.timer` 每周日 06:10 自动跑；任何一项不过就失败、写 `~/logs/pico-backup-drill-status.json` 并发信，只有全过才打 `DRILL_OK`。`drill --corrupt` 故意改坏一个字节，用来证明坏包会在 sha256 这一步被拦下。它只检验演练本身：坏包被拦下就打 `CORRUPT_CAUGHT` 并以 0 退出，不写正式的演练状态、不发信，免得巡检把这次故意的失败当成真失败报警。只有坏包一路过了所有检查（`CORRUPT_MISSED`），才写 FAIL 并发信。逐项检查：
- sha256 全部对上；
- mongo 各集合条数（conversations、messages 不能为 0）；
- pico.db `quick_check` = ok，runs 条数 > 0；
- 各 tar 能完整读出、条目数 > 0；
- meili 导入后起得来，各索引文档数合计 > 0。

## 真恢复（出事时，人工）

1. 停对应容器。
2. mongo：`docker exec -i pico-mongo-1 mongorestore --archive --gzip --drop < mongo.archive.gz`。
3. pico.db：解压后替换 pico_data 里的 `pico.db`（先删 `pico.db-wal` / `pico.db-shm`）。
4. tar：解到原卷。
5. meili：用 `--import-dump` 起。
