# 主路径回归实跑记录（W1）

```
DATE: 2026-07-30
TIP: 58cbb63 + startup bash fix
RUNNER: Grok-Pico写入
STATUS: W1 本机回归 **候选通过**（非 Phase1 PASS / 非 Live Preview PASS）
```

## 环境

- 服务曾全停：根因 `startup.sh` 用 `sh` 调用含 `pipefail` 的 bash 脚本 → **已改为 `bash run-product.sh`**
- 拉起后：18765 / 3080 / 8080 / mongo 正常
- 6014：`403` body `0`（与校准一致）

## 勾选结果

### A 拓扑
- [x] A1–A7 全 PASS（含主 JS 200、未登录 pico 401）

### B UI（Playwright 8080）
- [x] B1 登录页中文「欢迎回来」
- [x] B2 演示账号进入任务台
- [x] B3 Pico 首页/侧栏非 JSON
- [x] B4 六入口文案可见
- [x] B5 无 pageerror

### C 对话
- [x] C1 API「回归OK」
- [x] C2 UI 气泡无 Pico-User/Convo 泄漏（Playwright）
- [x] C5 错误模型 → 中文「【错误】…模型不可用」
- [~] C UI 完整流式文案：会话已创建并跳转 `/c/{id}`；截图 `screenshots/w1-chat.png`（响应时长视模型）

### D 账本/产物
- [x] D1 任务入账
- [x] D2 回复摘要
- [x] D3–D4 `hello.txt` file + inline `hi`
- [x] D5 rebind pending → real

### E 抽样
- [x] E4 alice/bob membership 隔离
- [ ] E1–E3 项目/自动化 UI 本轮未逐条点（非阻断；API 侧自动化鉴权此前已修）

### P 预览诚实
- [x] P1 8080 产品可用
- [x] P2 6014 403/0
- [x] P3 **不**宣称 Live Preview 已通
- [x] P4 与 PREVIEW-WHITE-SCREEN / CALIBRATION 一致

## 已知缺陷（≤5）

1. **Live Preview :6014** 无 preview-auth 时纯白（平台层）
2. UI 首条标题常「未命名任务」至异步生成
3. 默认路径为直连 Kimi，非默认多步 Agent（S2 叙事 W2）
4. 项目/自动化 UI 细测未纳入本轮硬门禁
5. 服务全停时若 `startup.sh` 未用 bash，无法自愈（**本轮已修**）

## 退出

- [x] A–D + 关键 E/P 无未解释 FAIL
- [x] 预览叙事诚实
- **W1 退出候选：YES** → 下一刀 **W2.1 S2 叙事**（文档）或 **W2.3 S7**

## 证据路径

- `screenshots/w1-login.png` / `w1-home.png` / `w1-chat.png`
- API 用例见执行日志（membership `w1-reg`）

## Production VPS S1 (2026-07-30 · owner paste · not full PASS)

```
health: ok pico-api phase=3-integrate
S1 http=200 reply: 演示OK
S1_SMOKE=PASS_LIKELY
entry: https://pico.aivia.asia/login
```

- Environment: Aliyun light server host-network stack (see CODEX-VPS-INVESTIGATION.md)
- Not a self-PASS of S2–S8 / CI / merge main

## Production UI (2026-07-30 · owner)

- login OK on https://pico.aivia.asia
- task UI chat **replies** (Kimi path)
- not full S2–S8 / merge PASS
