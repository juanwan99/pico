# 调研 · 运行抗 API 重启（#445 Phase B）

```text
DOC: docs/RESEARCH-RUN-SURVIVE-RESTART.md
STATUS: BINDING 选型结论 · T-CLOSE-P0P1-UX-STABILITY-CLAIM
DATE: 2026-08-11
法律: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
CLAIM-WB: NO
```

## 问题

生产 `prod-update` / 容器 recreate 会杀死 in-process `asyncio` 任务。账本 run 在启动时由 `reconcile_orphaned_runs` 标 failed，历史文案曾裸露 `run owner was lost during API restart`。

## 方案对照

| ID | 方案 | 成本 | 法律 | 体验 | 结论 |
|----|------|------|------|------|------|
| **B1** | **SIGTERM soft drain**：lifespan 等 in-flight ≤N 秒 + compose `stop_grace_period` | 低 | **合规**（不增第二 worker OS） | 短任务多半可跑完 | **选用** |
| **B2** | 检查点 resume（tool 步后可续） | 中高 | 边界：勿自研会话树 | 长任务更强 | **不做本卡**（真 Pi 上游能力成熟后再薄适配） |
| **B3** | 失败人话 + 一键重新运行 | 已部分落地 | 合规 | 必须保留 | **保留加固** |
| **B4** | 外置 durable worker / 第二进程队列 | 高 | **易违法**（自研 worker OS） | 最强 | **否决本卡** |

## 选型（定稿）

```text
本卡实现: B1 + B3
不做: B2 完整 resume · B4 外置 worker
理由: 单节点 in-process 真源下，drain 是唯一低成本、法律安全的「降低伤害」；
      完整 resume 属于上游 harness 能力，禁止在 Pico 自研第二编排核。
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
