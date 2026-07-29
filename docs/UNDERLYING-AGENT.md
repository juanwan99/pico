# 底层 Agent 是什么

```
不是：自研 Agent OS / 前端假进度
是：钉版本 Kimi 模型 HTTPS API + 服务端多步 tool-calling 环 + 白名单网关
```

## 结构

```
NextChat (产品 UI)
    │  OpenAI 兼容
    ▼
Pico API  POST /v1/chat/completions
    │  Task / Run / Event 账本
    ▼
pico_orchestrator.run_agent_loop
    │  tools = 白名单 only
    ├─ Kimi Chat Completions API (tool_choice=auto)
    └─ AllowlistGateway.invoke
         ├─ pico_echo
         ├─ fake_edu_list_classes   (S6 只读学校形状)
         └─ pico_propose_change     (S7 提案，不写库)
```

## 钉版本

| 包 | 版本 |
|----|------|
| `kimi-agent-sdk` | 0.0.5 |
| `kimi-cli` | 1.12.0 |

危险工具（Shell/File/Web/MCP）在 `agents/pico.yaml` **强制关闭**。

## 如何验证已接入

1. NextChat 选模型 **Pico 智能体**
2. 发送：`列出我学校的班级`
3. 应出现工具产物（班级表）+ 账本 Event `tool.call` / `tool.result`

```bash
curl -s localhost:8000/v1/chat/completions \
  -H 'Authorization: Bearer pico-dev' -H 'Content-Type: application/json' \
  -d '{"model":"pico-agent","messages":[{"role":"user","content":"列出我学校的班级"}]}'
```
