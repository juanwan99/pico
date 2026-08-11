# 运行 drain 与双停止语义

```text
DOC: docs/RUN-DRAIN-AND-STOP.md
STATUS: BINDING ops 说明 · T-PACK-UX-HARDEN (#447)
DATE: 2026-08-11
关联: docs/RESEARCH-RUN-SURVIVE-RESTART.md · #443/#445/#446
法律: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
CLAIM-WB: NO
```

## 1. 为什么需要 drain

生产 `prod-update` / 容器 recreate 会向 API 进程发 SIGTERM。账本 run 若由 **本进程内** `asyncio` 任务持有，硬杀会导致 owner 丢失；启动时 `reconcile_orphaned_runs` 会把孤儿 run 标为 failed。

历史文案曾裸露英文 `run owner was lost during API restart`。现已：

1. **B1 soft drain**（降低中断概率）
2. **失败人话 + 重新运行**（中断后仍可理解、可恢复）

**诚实预期：** drain **不是** 零中断 SLA。长任务仍可能在 grace 用尽后失败；UI 应显示中文失败与「重新运行」，而不是机房英文。

## 2. Drain 参数（与代码一致）

| 项 | 值 | 代码位置 |
|----|-----|----------|
| 进程内等待 inflight | **45s** | `run_service.drain_inflight_runs(timeout_s=45.0)` · `main.py` lifespan `finally` |
| Docker 停止宽限 | **60s** | `docker-compose.host.yml` → `stop_grace_period: 60s` |
| 顺序 | drain → `reconcile_orphaned_runs` → 进程退出 | lifespan shutdown |

```text
SIGTERM
  → stop scheduler
  → await inflight runs ≤ 45s（超时则 cancel 剩余 task）
  → reconcile 仍 open 的账本行 → failed + 人话 user_message
  → 容器 grace 60s 须 ≥ drain 45s
```

维护建议：

- 短任务（秒～数十秒）多半能在 drain 窗口内收尾
- 部署窗口尽量避开已知长跑任务高峰
- **禁止**宣称「永不失败 / 永不中断」
- 中断后：侧栏/主区应见中文「服务维护或重启…请重新运行」类，**无**常态裸 `owner was lost`

## 3. 双停止语义（用户可见）

| 控件 | 文案（zh-Hans） | 作用 | 不做什么 |
|------|-----------------|------|----------|
| 输入区停止 | **停止生成（仅停屏幕输出，云端任务可能继续）** | 中止浏览器流式输出 / 屏幕生成 | **不**保证取消云端 ledger run |
| 任务栏停止 | **停止任务** | 取消云端任务（真停止） | 不是「只清屏幕」 |

`data-testid`：

- 停止生成：`stop-generation-button`
- 停止任务：`task-stop-button`（任务栏 `task-run-bar` 内）

审查读图时：两文案须可辨；不得只剩含糊的「停止生成」。

## 4. 失败人话（列表 / 侧栏）

客户端 `humanizeRunError` 与 API `user_message` 共同覆盖：

| 原始信号 | 用户可见（示例） |
|----------|------------------|
| `owner was lost` / `api restart` / `greenlet` | 服务维护或重启导致任务中断，请打开后点「重新运行」。 |
| 过长 traceback | 任务失败，请打开查看详情后重试。 |

列表/历史失败行不得依赖用户读英文堆栈。

## 5. 本文件不覆盖

```text
B2 断点续跑 · B4 外置 worker · 零中断 SLA
W1–W5 全量终验（#448）
CLAIM-WB 材料/代签（#449）
```

## 6. 验证提示

```text
tip: GET /api/pico/tip → 40 位 git_sha
类人: 登录公网 · 失败行读图 · 运行中见双停止
禁: curl 冒充 READY · 无帧写 PASS
CLAIM-WB: NO
```
