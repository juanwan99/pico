# 日间任务 · N7 停止根治（VQ-006 二次 FAIL）

```
TYPE: HOTFIX
STATUS: OPEN
RISK: 黄 · FAST
context_reset: false
PRIOR: #107 已部署 6fd3007；VQ-006 FAIL
```

## 验证事实（禁止再争论）

部署 SHA `6fd3007` 上公网：

- 按钮显示「停止」，点击后 **不变「停止中」**
- `cancel_requested=0`，无 `run.cancel_requested`
- 终态 `failed/token_cap`，不是 `cancelled`
- 历史时间线 PASS

因此：**点击未进入有效 cancel 请求链**（或请求失败被静默），不是「没部署」。

## 目标（必须公网可证）

1. 点击「停止」后 **100ms 内** UI 变为「停止中」或可见错误条  
2. DevTools Network（或 Playwright request log）出现：  
   `POST /api/pico/v1/runs/<uuid>/cancel` 且 status **200**  
3. 账本：`cancel_requested=1` + event `run.cancel_requested`  
4. 终态 **`cancelled`**（禁止 token_cap failed 冒充）  
5. 单测不够：要有 **浏览器级** 集成（可 Playwright 或 LibreChat 已有 e2e 钩子）证明 **真实 click → 真实 fetch**

## 强制排查（PR 正文逐条填证据）

| # | 查 | 证据形式 |
|---|-----|----------|
| 1 | 点击是否触发 onClick（log / data-testid 计数） | 截图或测试 |
| 2 | `cancellableRunId` 是否为当前 inflight run uuid | console/assert |
| 3 | `getTokenHeader()` 在 cancel 时是否空导致 401 被 catch | Network status |
| 4 | 是否被上层 pointer-events / 遮罩挡住 | DOM |
| 5 | `isSubmitting` 与 ledger.run 不同步导致假 canCancel | 状态机说明 |
| 6 | 代理 cancel 是否要求与 chat 不同 scope | 502/403 body |

## 建议修复方向（任选验证）

- cancel 时 **强制** 用 TaskRunBar 点击瞬间闭包的 runId（已有）+ **ref** 防 stale  
- 无 token 时 **立即** 红条错误，不要安静  
- 临时 `console` 仅开发不行：用可见错误 + 测试断言 fetch mock **被调用**  
- 若 LibreChat 主「停止生成」与账本「停止」混淆：两按钮 data-testid 分离，验证点 `task-run-bar` 内按钮  

## 非目标

改 token_cap、M5、像素。

## 交付

- PR RISK 黄 FAST  
- ## CANDIDATE  
- E3 ## DEPLOYED  
- 验证 VQ-007 PASS  
