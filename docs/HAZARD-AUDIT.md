# 隐患排查报告（2026-07-30）

## 已修复（本轮）

| ID | 等级 | 问题 | 处理 |
|----|------|------|------|
| H1 | **P0** | `/api/pico/*` **无鉴权**，匿名可列任务/产物/建工作空间 | `requireJwtAuth` 强制登录 |
| H2 | **P0** | 代理 principal 全员共享 `nextchat-user`，租户串读 | `X-Pico-Membership-Id` + 消息内 `【Pico-User】` 作用域绑定 |
| H3 | **P1** | 结果区 `document.write` 拼接 body，XSS 风险 | 改为 `textContent`；URL 仅 http(s) |
| H4 | **P1** | taskId 路径参数未校验 | 仅允许 `[A-Za-z0-9_-]{1,128}` |
| H5 | **P1** | 查询串原样转发 | 仅转发 `conversation_id` |
| H6 | **P2** | 上游 host 若误配可成开放代理 | 默认拒绝非 local（`PICO_API_BASE` 显式覆盖） |

## 残留 / 接受风险

| ID | 等级 | 说明 | 缓解 |
|----|------|------|------|
| R1 | P1 | 对话补全走 `OPENAI_API_KEY=pico-dev`，若无 `Pico-User` 标记仍落默认 membership | 发送路径已注入 `Pico-User`；旧任务仍属旧 principal |
| R2 | P2 | 生产若误设 `PICO_ENV=development` 会接受 proxy key | 部署检查清单；prod 拒 `sk-pico-dev` |
| R3 | P2 | 首条消息 conversationId 可能仍为 `new`，账本绑定偏弱 | 第二条起稳定；后续可在 title 生成后回写 |
| R4 | P2 | 自动化无服务端 scheduler | 明确 P2，勿宣传「到点必跑」 |
| R5 | P2 | Workspace 文件视图仍为空壳 | UI 空态已标明 |
| R6 | 信息 | KIMI key 在 `.env`（gitignored） | 勿提交；轮换泄露 key |

## 验证命令（沙箱）

```bash
# 未登录必须 401
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3080/api/pico/v1/tasks
# 期望: 401
```

## 结论

阻断匿名账本读取与结果区 HTML 注入后，**可继续功能迭代**。  
多用户严格隔离依赖 `Pico-User` 标记 + 代理 membership 头；上线前再做一轮越权用例。
