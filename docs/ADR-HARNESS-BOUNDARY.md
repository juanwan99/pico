# ADR：Pico 控制面与 Harness 可替换边界

```
DOC: docs/ADR-HARNESS-BOUNDARY.md
STATUS: ACCEPTED
DATE: 2026-08-01
SCOPE: Architecture boundary only; no external Harness selected by this ADR
```

## 1. 上下文

Pico 已有 LibreChat 产品壳、服务端 Task/Run/Event/Artifact 账本、白名单工具和
`pico-agent` 多步执行。当前执行热路径由 Pico Python 代码直接调用 OpenAI-compatible
模型 API；仓库虽钉住 Kimi Agent SDK/CLI，完整 Kimi Agent Runtime 并未承担当前执行热路径。

长期目标不是继续扩张自研 Agent Runtime，也不是把产品状态交给某个模型厂商的 Harness。
Pico 需要稳定自己的产品地基，同时允许未来以低成本接入、升级或替换成熟 Harness 和模型。

## 2. 决策

采用以下稳定分层：

```text
LibreChat 产品壳
        ↓
Pico Control Plane（租户、项目、唯一账本、自动化、产物）
        ↓
Pico Harness Contract
        ↓
Harness Adapter
        ↓
可替换 Harness Runtime
        ↓
可替换 Model Provider
```

### 2.1 Pico 永久拥有

- `conversation_id / task_id / run_id` 的产品级关联。
- 租户、成员、范围和工具授权。
- Task/Run/Event/Artifact 的唯一可信账本与终态。
- 项目上下文、输入资产、产物归属和版本。
- 自动化触发、幂等、取消、恢复、审计和使用量。
- 技能启用策略与运行时不可变快照。

### 2.2 Harness 只负责

- 模型调用循环、规划与多步执行。
- 上下文管理、压缩和执行期重试策略。
- 通过 Pico 网关调用已授权工具。
- 发出结构化执行事件和候选产物。

Harness 不得直接访问 Pico 数据库、绕过租户/工具网关、直接写产品终态，或把自己的
Thread/Session/Run 变成第二套产品事实。外部运行标识只能作为 Pico Run 的关联字段。

## 3. 最小 Harness 合同

合同是目标边界，不等同于当前已发布 API；实现时优先从现有调用路径提取最小接口。

### 3.1 输入 `RunRequest`

- Pico IDs：`conversation_id`、`task_id`、`run_id`、幂等键。
- 已解析 Principal 的安全引用；不把客户端自报租户当事实。
- prompt、允许的历史、项目上下文和输入资产引用。
- skill/model 不可变快照、执行上限、允许工具列表。

### 3.2 输出 `RunEvent`

至少规范化为：

- `run.started`
- `agent.step`
- `tool.started` / `tool.completed` / `tool.failed`
- `approval.required`
- `artifact.proposed`
- `run.succeeded` / `run.failed` / `run.cancelled`

只有 Pico 控制面可以校验事件顺序、持久化 Artifact 并提交最终 Run 状态。

### 3.3 控制能力

Adapter 应逐步提供：`start`、`cancel`、`status`、`recover`、`health`、`capabilities`、
`version`。`resume` 只在底层 Harness 和 Pico 账本都能证明恢复语义时开放，不能用重新发起冒充恢复。

## 4. 当前实现映射

| 目标角色 | 当前实现 | 说明 |
|----------|----------|------|
| 产品壳 | `apps/librechat` | React Web 壳；Mongo 保存通用用户/会话数据 |
| Pico 控制面 | `services/api` | FastAPI；鉴权、Task/Run/Event/Artifact、自动化 |
| 隐含 Adapter | `openai_compat.py` + `run_service.py` | 尚未形成独立 Harness 接口 |
| 当前 Harness | `pico_orchestrator.runner.run_agent_loop` | Pico 薄 tool-calling 循环 |
| 安全网关 | `pico_orchestrator.gateway` / `skill_policy` | fail-closed 工具和技能策略 |
| Provider | `pico_orchestrator.provider` | Kimi 优先，DeepSeek 备用 |

当前薄循环继续作为默认实现；本 ADR 不授权立即替换，也不预选尚未经过生产验证的外部 Harness。

## 5. 接入门槛

任何外部 Harness 必须：

1. 许可证允许目标部署和分发方式。
2. 支持固定版本、无头服务运行和明确健康检查。
3. 能禁用宿主 Shell/File/Web/MCP，或完整服从 Pico 能力网关。
4. 支持结构化事件、取消、错误和运行标识关联。
5. 不要求成为 Pico 产品状态真源。
6. 通过同一组契约测试：成功、工具、拒绝、失败、超时、取消、重复请求、重启恢复、产物和事件终态一致。

仅“能调用模型并返回文字”不构成合格 Harness。

## 6. 实施原则

- 不为尚不存在的第二个实现设计万能框架；先从现有调用提取最小端口。
- 不 Fork 后深改第三方 Harness；优先原样运行并在 Pico 侧写 Adapter。
- Provider 专属字段不得扩散到项目、账本和 UI 领域对象。
- 替换 Harness 或模型不得要求迁移 Pico 的项目、历史、Task/Run 或 Artifact。
- CI 绿色只证明自动检查；Harness 切换仍需 exact-SHA 契约测试和真实运行验收。

## 7. 后果

正向：Pico 产品事实稳定；可独立升级 UI、Harness 和模型；第三方故障不会定义 Pico 终态；
未来接入成熟 Harness 时无需重建产品地基。

代价：Pico 必须维护一层小而严格的反腐适配层、事件规范和契约测试；外部 Harness 的专有能力
只有在能映射为诚实的 Pico 语义后才能开放。

## 8. 明确非目标

- 本 ADR 不选择 DeepSeek Harness、Codex、Kimi Agent 或其他具体终局实现。
- 不建设多 Harness 市场或运行时编排平台。
- 不新增第二套 Task/Run/Event/Artifact 账本。
- 不以更换 Harness 为由重写 LibreChat 产品壳。
