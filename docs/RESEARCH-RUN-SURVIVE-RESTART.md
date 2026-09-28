# 调研 · 运行抗 API 重启（#445 Phase B）

```text
DOC: docs/RESEARCH-RUN-SURVIVE-RESTART.md
STATUS: BINDING 选型结论已由业主 2026-09-28 放开 C（#1090）· 旧 B2/B4 否决 SUPERSEDED
DATE: 2026-08-11
UPDATED: 2026-09-28
法律: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md §3b
CLAIM-WB: NO
```

## 问题

生产 `prod-update` / 容器 recreate 会杀死 in-process `asyncio` 任务。账本 run 在启动时由 `reconcile_orphaned_runs` 标 failed，历史文案曾裸露 `run owner was lost during API restart`。

## 方案对照

| ID | 方案 | 成本 | 法律 | 体验 | 结论 |
|----|------|------|------|------|------|
| **B1** | **SIGTERM soft drain**：lifespan 等 in-flight ≤N 秒 + compose `stop_grace_period` | 低 | **合规**（不增第二 worker OS） | 短任务多半可跑完 | **选用** |
| **B2** | 检查点 resume（tool 步后可续） | 中高 | 薄适配 Pi `--session` | 长任务更强 | **业主 2026-09-28 放开**（C：中断用 Pi `--session` 续跑） |
| **B3** | 失败人话 + 一键重新运行 | 已部分落地 | 合规 | 必须保留 | **保留加固** |
| **B4** | 执行与 pico-api 进程分离（上游 Pi 进程 + session，不是自研 worker OS） | 中 | 薄适配 | 部署不杀在飞 | **业主 2026-09-28 放开**（C）。自研第二套任务队列核仍违法 |

## 选型（定稿）

```text
旧结论（B2/B4 否决）SUPERSEDED · 业主 2026-09-28 放开 C（#1090）。
现行：B1 drain 仍可作部署缓冲；B2 = 薄适配 Pi --session 续跑；
      B4 允许的是「执行与 pico-api 进程分离」（上游 Pi 进程活过部署），
      禁止自研第二套 worker OS / 任务队列核。
实现走 T-LONGTASK 第 2 张卡。
```

## 实现要点（C）

1. `run_service` / openai_compat / durable_job 登记 inflight task  
2. lifespan `finally`: `drain_inflight_runs(45s)` → `reconcile_orphaned_runs`  
3. `docker-compose.host.yml` `stop_grace_period: 60s`  
4. UI/API：失败列表 `user_message` + 侧栏 `taskFailureHint` 映射，禁裸 English  

## 人测

- 长任务中途 `prod-update`：尽量无中断；中断则中文失败 +「重新运行」  
- 禁止用 curl 冒充 READY  

## CLAIM-WB

本调研 **不签** Ready / CLAIM-WB。
