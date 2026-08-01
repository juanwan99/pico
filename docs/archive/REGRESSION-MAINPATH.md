# 主路径回归清单（W1）

```
DOC: docs/REGRESSION-MAINPATH.md
PHASE: W1 — 主路径硬化
STATUS: CHECKLIST（执行时勾选；非 PASS 证书）
DATE: 2026-07-30
SHELL: apps/librechat @ :8080
API: 127.0.0.1:18765
LOGIN: teacher@example.com / <redacted-demo-password>
```

## 使用方式

1. 每条：`[ ]` → 通过改 `[x]`，失败写 **FAIL + 现象**（勿删条）。  
2. 产品 UI 以 **直连/本机 8080** 为准；Live Preview 见 §P。  
3. 全绿 = W1 退出候选；**不等于** Phase1 PASS / 可合 main。

---

## A. 进程与拓扑

| # | 检查 | 期望 | 结果 |
|---|------|------|------|
| A1 | `curl -sf http://127.0.0.1:18765/health` | `ok: true` | [ ] |
| A2 | `curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/` | 200 | [ ] |
| A3 | 8080 HTML 含 `Pico 正在加载` 或登录文案 | 非空 HTML | [ ] |
| A4 | `curl -sf http://127.0.0.1:3080/health` 或首页 | LibreChat 起 | [ ] |
| A5 | Mongo :27017 可连 | 是 | [ ] |
| A6 | 主 JS：`index.html` 中 `assets/index.*.js` 对 3080/8080 | 200 + JS MIME | [ ] |
| A7 | 未登录 `GET /api/pico/v1/tasks` | **401** | [ ] |

---

## B. 登录与首页

| # | 检查 | 期望 | 结果 |
|---|------|------|------|
| B1 | 打开 `/login` | 「欢迎回来」等中文 | [ ] |
| B2 | 演示账号登录 | 进入任务台 /c/new | [ ] |
| B3 | 首页标题/输入 | Pico 任务台，非 API JSON | [ ] |
| B4 | 侧栏六入口可点 | 新建/助理/项目/能力/自动化/更多 | [ ] |
| B5 | 控制台无持续 uncaught | 可有噪音；无整页白 | [ ] |

---

## C. 对话与模型（S1）

| # | 检查 | 期望 | 结果 |
|---|------|------|------|
| C1 | 首页发「只回：回归OK」 | 流式或完整回复含回归OK | [ ] |
| C2 | 用户气泡 | **无** Pico-User/Convo 裸标记 | [ ] |
| C3 | 顶部运行条 | 等待 → 完成/就绪 | [ ] |
| C4 | 刷新后会话仍在 | 侧栏或历史可见 | [ ] |
| C5 | API 无 key 类错误时 | 中文可读失败（可另测） | [ ] |

---

## D. 账本与产物（S3 / 结果区）

| # | 检查 | 期望 | 结果 |
|---|------|------|------|
| D1 | 发消息后 | 任务列表或 ledger 有对应任务 | [ ] |
| D2 | 结果区概览 | 有「回复摘要」或产物卡 | [ ] |
| D3 | 「请创建 hello.txt，内容为 hi」 | 概览/文件中有 **hello.txt** | [ ] |
| D4 | 打开产物 | 可见正文 hi | [ ] |
| D5 | 首条 new 会话 | rebind 后 conversation_id 非 pending 可查（API 或二次消息） | [ ] |

---

## E. 项目 / 自动化 / 鉴权（抽样）

| # | 检查 | 期望 | 结果 |
|---|------|------|------|
| E1 | 建项目 + 新任务 | URL 带 project；项目任务数增加 | [ ] |
| E2 | 项目指令保存后发消息 | 行为受约束或 API 侧带入 system（抽测） | [ ] |
| E3 | 自动化列表（已登录） | **非** 原始 401 JSON；可空列表 | [ ] |
| E4 | 两 membership 列任务 | 互不可见（API 头测） | [ ] |

---

## P. 预览诚实（Live Preview）

| # | 检查 | 期望 | 结果 |
|---|------|------|------|
| P1 | 直连 8080 | 登录/加载文案可见 | [ ] |
| P2 | `curl -sS -w '%{http_code} %{size_download}' http://127.0.0.1:6014/` | 常 **403 0**（无 preview-auth） | [ ] |
| P3 | 用户 Live Preview 仍白 | **不得**仅凭 A2 宣称预览已通 | [ ] |
| P4 | 证据 | 必要时更新 `docs/PREVIEW-WHITE-SCREEN.md` | [ ] |

---

## 退出（W1）

- [ ] A–E 无未解释 FAIL  
- [ ] P 节已理解并对外叙事一致  
- [ ] 已知缺陷列表（最多 5 条）写入 Issue/PR 草稿  

**下一步：** `docs/ORCHESTRATION-PLAN.md` → W2（S2 叙事 + S7）或 W3（CANDIDATE）。
