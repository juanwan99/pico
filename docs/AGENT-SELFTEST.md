# Agent 自测能力说明（效率）

```
DOC: docs/AGENT-SELFTEST.md
```

## 我能测什么 / 不能测什么

| 目标 | Agent 能否测 | 说明 |
|------|--------------|------|
| 本沙箱 8080 UI / 18765 API | **能** | `bash scripts/agent-selftest.sh` |
| Playwright 登录截图 | **能** | 沙箱 Chromium |
| Kimi S1 真聊（本地 .env） | **能** | key 仅本地 `.env`，不进 Git |
| 生产 https://pico.aivia.asia | **多数不能** | 沙箱出口 TLS 常 RST / Beaver |
| 生产 SSH / 宝塔 | **不能** | 22 不通 |
| 业主浏览器观感 | 需业主 1 句确认 | 公网最终验收 |

## 高效协作约定

1. **默认：** Agent 在沙箱起栈 → selftest → 改代码 → push 分支。  
2. **仅当必须动 VPS：** 给业主 **一条** 宝塔命令（pull + compose），不再来回猜。  
3. **禁止** 用「请你打开域名告诉我」代替 Agent 本可做的本地测试。  
4. 生产闭环证据：业主一句「能登录/能回」即可；细节用 selftest 本地复现。

## 命令

```bash
# 栈已启动时
bash scripts/agent-selftest.sh
# 期望 SELFTEST_OK
```
