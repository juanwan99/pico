# Pico Phase 1 Demo Script

```
PLAN: docs/MVP-3DAY.md v1.2 FIXED
```

## Prerequisites

```bash
cp .env.example .env
# set KIMI_API_KEY in .env

python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
make api
# other terminal
cd apps/web && npm install && npm run dev
```

## Script (S1–S7)

1. **测试签发 School A**  
   UI 左侧：`school-a` / `member-1` → 签发 token。  
   或 `POST /v1/dev/token`.

2. **真流式 + Agent 多步**  
   输入：`列出我学校的班级，并简要说明。` → **创建任务并运行**。  
   主区应出现：`agent.step`、`tool.call` / `message.delta`、终态 `succeeded`。

3. **FakeEdu 工具 Event**  
   时间线含 `fake_edu_list_classes` 的 `tool.call` / `tool.result`。

4. **产物**  
   右侧产物区出现班级表 markdown。

5. **跨校拒绝 + Event**  
   点 **跨校拒绝演示**。  
   时间线含 `auth.deny`（token=school-a，请求 school-b）。

6. **待确认**  
   **新建提案** → 左侧待确认列表 → **确认**。  
   审计行出现；**无学校业务库写入**。

7. **取消 Run**  
   发起长任务后立即 **取消 Run** → 终态 `cancelled` 或尽快结束。

## curl 速查

```bash
TOK=$(curl -s -X POST localhost:8000/v1/dev/token \
  -H 'Content-Type: application/json' \
  -d '{"school_id":"school-a","membership_id":"m1"}' | jq -r .access_token)

curl -s -X POST localhost:8000/v1/tasks \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"prompt":"列出我学校的班级"}' | jq .

# poll events
RUN=<run_id>
curl -s localhost:8000/v1/runs/$RUN/events -H "Authorization: Bearer $TOK" | jq .
```

## Non-goals shown

- 未连接 edu-cloud  
- 未启用 Shell/File/Web/MCP  
- 确认 ≠ 写教务库  
