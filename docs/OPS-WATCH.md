# pico 运维巡检（pico#1273）

ECS 用户定时器 `pico-ops-watch.timer` 每 5 分钟跑一次 `scripts/pico_ops_watch.py check`。只读，不碰现网数据，不调模型。某项变坏时发一封信，恢复时再发一封；还坏着就每 6 小时提醒一次。发信复用 `~/scripts/edu-backup-alert.py`（和 edu-core 备份、健康探针同一个通道）。日志写 `~/logs/pico-ops-watch.log`，状态写 `~/logs/pico-ops-watch.json`。

| 项 | 看什么 | 什么时候算坏 |
|--|--|--|
| probe | 公网 `https://pico.aivia.asia/health`、`/login`，本机 `127.0.0.1:18765/health` | 连续 2 轮不通（发版时偶尔断一下不算）；信里写明是本机 pico-api 还是公网入口 |
| runs | pico.db 里近 60 分钟结束的任务（经 api 容器只读） | 失败（含系统取消）≥ 4 个且占 ≥ 30%。老师自己点停不算失败。信里按原因分组 |
| upstream | New API 容器日志（`docker logs --since 上一轮`）里的 relay 状态码和 `channel error` 行 | 出现 403（钥被停 / 被封，要人处理），或 429 + 5xx ≥ 5。`docker logs` 本身失败算「检查本身出错」并发信，游标不前移，下一轮补读 |
| buildcache | `docker buildx du` 的 Private（独占） | > 35 GB，和每小时清理的上限一致。`docker system df` 的总数含和镜像共用的层，删不到，不看它 |
| env | `/opt/pico/.env` 和上次记录的快照比 | 有改动但没走 `env-set` / `env-record`：自动补记一行 UNLOGGED 并发信 |

阈值可用环境变量改（`PICO_OPS_RUNS_RATE` 等，见脚本头）。任何一项检查自己报错（docker 不通、容器改名），都按「检查本身出错」发信，不当作正常。

根盘不在这里看：磁盘是整台机器的事，只留一处，由 edu-core 的 `edu-health-probe.py` 管（剩不到 30 GB 发信，30 GB 正是每小时构建缓存清理守的空闲底线，见 edu-core `docs/DEPLOY-ECS.md` #2699）。

## 失败原因查询

```bash
python3 /opt/pico/scripts/pico_ops_watch.py report --hours 24
```

按原因分组：钥被停 / 无权限、上游限流 429、上游 5xx / 连不上、模型不可用、流断 / 空输出、没交出文件、对话占用中、无进展熔断、超时、代码错误、系统取消、其他，每组带一条例子。

## .env 改动留痕

改 `/opt/pico/.env` 一律留一行在 `/home/ops/pico-env-changes.log`：时间、卡号、改了哪些键、原值 → 新值（含 KEY / SECRET / TOKEN / PASSWORD 的值只记 sha 前 8 位）、原因。

```bash
# 改：先备份，再改，再记一行
python3 /opt/pico/scripts/pico_ops_watch.py env-set PICO_HEDGE_FAST_S=25 --card pico#1269 --why "取消腿 60%"
# 别的工具已经改了：补记原因
python3 /opt/pico/scripts/pico_ops_watch.py env-record --card pico#1261 --why "..."
```

`scripts/brain-switch.py` 换模型时自己会记（`--card` / `--why` 必填，回滚也记）。手改没记的，5 分钟内会被巡检补记成 UNLOGGED 并发信。

## 演练

```bash
python3 /opt/pico/scripts/pico_ops_watch.py check --drill upstream   # probe / runs / upstream / buildcache / env
```

把那一项强制当成坏的，发一封标「演练」的信，不改状态文件。

## 安装

```bash
cp deploy/systemd/pico-ops-watch.* ~/.config/systemd/user/ && systemctl --user daemon-reload
systemctl --user enable --now pico-ops-watch.timer
```

旧的 `public-502-monitor.sh` crontab 行指向的目录 09-01 起就不存在，而且它只采样写文件、从不发信，已由本巡检的 probe 项取代，crontab 那行已删。脚本留着手动长窗采样用。
