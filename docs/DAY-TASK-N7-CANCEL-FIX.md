# 日间任务 · N7 停止按钮热修（VQ-005 FAIL）

```
TYPE: HOTFIX
STATUS: OPEN
RISK: 黄 · FAST
context_reset: false
PRIOR: PR #99 ## TEST REPORT verdict FAIL（停止未进账本）
```

## 故障（验证窗证据）

- 公网结果区 **「停止」** 可点，但：
  - `cancel_requested` 仍为 0
  - 无 `run.cancel_requested` 事件
  - run 最终 `failed`（token_cap），不是 `cancelled`
- 历史时间线 PASS；问题 **仅取消路径**

## 目标

1. 点击「停止」必须 `POST /api/pico/v1/runs/{runId}/cancel`（经现有代理）且 **200**
2. 账本：`cancel_requested=1` + event `run.cancel_requested`
3. 终态：`cancelled`（或 running 时尽快收敛到 cancelled，轮询可见）
4. UI：按钮进入「停止中」；终态显示已停止/cancelled（N5）
5. 失败时 **可见错误**，禁止静默 catch 后无网络请求
6. 回归测试：真实点击路径或集成级断言 **请求已发出**（勿再只 mock 成功）

## 排查清单（必须写进 PR）

- [ ] `TaskRunBar` 的 button `type="button"`，未被表单提交吞掉
- [ ] `onCancel` / `cancelRun` 是否因 `run.status` 不在 `queued|running|preparing` 早退
- [ ] `run.id` 是否为当前 inflight run（历史 run 误绑）
- [ ] `cancelPicoRun` / `picoFetch` 的 URL、JWT、membership 头
- [ ] 代理 `pico.js` POST cancel 是否 401/404 被吞
- [ ] API `request_cancel` 对 running 是否只标位、worker 是否轮询

## 非目标

M5、像素、改 token_cap 策略。

## 验收

- 本地/单测绿
- ## CANDIDATE + CI
- ## DEPLOYED（E2 或 E3）
- 验证窗 **VQ-005 复测** 仅 B 项 cancel 也可出短报告，总 verdict 以 cancel PASS 为准
