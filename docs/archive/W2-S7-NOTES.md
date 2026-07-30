# W2.3 S7 最小人确认 — 交付说明

```
DATE: 2026-07-30
TIP: (see git)
STATUS: 实现完成（候选；非 PASS）
```

## 行为

1. 后端：`POST /v1/changes` → `proposed`；`…/confirm` → `confirmed` + Audit；`…/reject` → `rejected` + Audit  
2. 列表按 **membership** 隔离  
3. LibreChat 代理：`/api/pico/v1/changes*`  
4. UI：`ChangeConfirmBanner`（任务视图顶栏）— 演示提案 / 确认 / 拒绝  
5. **不写**学校业务库（note 明示）

## API 实跑

- create → list proposed → confirm → `confirmed`  
- 其他 membership 列表为空  
- reject → `rejected`

## 未做

- Agent 工具 `pico_propose_change` 自动弹窗（仍可写库提案；UI 靠列表轮询）  
- edu 回写  
