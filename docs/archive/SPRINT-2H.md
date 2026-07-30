# 2h 冲刺记录（WorkBuddy 对齐 · clean-room）

```
BRANCH: grok/pico-preview-librechat-p0
SHELL: apps/librechat
```

## 已交付

| 项 | 说明 |
|----|------|
| 侧栏 | 单栏；导航 + **任务列表** + 空间 |
| 路由 | `/assistants` `/capability` `/automation` `/more` |
| 助理 | 本地助理 + 微信后置，非纯市场 |
| 能力中心 | 专家 / 技能 / 连接器三 Tab |
| 自动化 | 列表 + 创建表单壳 |
| 更多 | 六项入口 |
| 项目详情 | 动态/计划/任务/资产 + 右轨配置 |
| 会话 | TaskRunBar + 右侧结果区（概览/文件/浏览器） |
| Composer | 工作空间/权限/模型菜单 |

## 下一棒

- Task/Run 账本与会话 id 稳定映射（API）
- 结果区接真实 Artifact 流
- 工作空间服务端 ACL
- 自动化服务端 scheduler

## 续作（ledger）

| 项 | 状态 |
|----|------|
| Task.conversation_id / workspace_id | ✅ |
| Workspace API CRUD | ✅ |
| chat/completions 一律入账 + 回复摘要产物 | ✅ |
| LibreChat `/api/pico` 代理 | ✅ |
| 前端 usePicoTaskLedger + 结果区接产物 | ✅ |
| 发送注入 Pico-Convo | ✅ |
| 自动化 scheduler | 未做（P2） |

## 续作 2（绑定 + 调度）

| 项 | 状态 |
|----|------|
| 首条消息 pending_* → rebind | ✅ |
| POST /v1/tasks/rebind-conversation | ✅ |
| /v1/automations + 20s 调度循环 | ✅ 已验证单次触发 |
| 自动化页接服务端 | ✅ |
