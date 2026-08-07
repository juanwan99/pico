# PLAN · T-E2E-DEFAULT-CHAT（端到端默认路径 · BINDING）

```text
STATUS: BINDING
DATE: 2026-08-07
TRIGGER: 业主公网截图 — 默认 kimi-k2.6 · 气泡 Kimi · 「你是什么模型」服务出错
SUPERSEDES_FOR_ACCEPTANCE:
  - 仅 Agent/交件管线绿、默认闲聊未测仍可 STAGE PASS
  - CLAIM-WB 建议 YES（在 E2E-DEFAULT 红时）
PRIOR: #322 STAGE2 · #320 STAGE1
MODE: SOLO 无人值守 · 仅 EXCELLENT 晋级
```

## 0. 业主铁律（本卡最高）

```text
端到端 = 用户打开公网 → 不改设置/不选手动「好模型」
       → 直接打字能用 → 再办真任务

默认路径失败 = 产品失败 = 整卡 FAIL
禁止：只测 pi-agent 交件、只测 API、只测已改成 DeepSeek 后的路径冒充默认
```

## 1. 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO · 公网端到端
不做：Dify 门脸 · 场景卷 · 双核真源 · 多窗 · 假绿 CLAIM
```

## 2. E2E-DEFAULT 一票否决（每条小任务前后可跑，包末必须）

```text
E2E-DEFAULT（必须全 PASS，任一红整包不得 EXCELLENT）:
  D1 无痕或清站点数据后打开 https://pico.aivia.asia/login
  D2 登录（演示账号）
  D3 新建任务/新会话 — **不**手动改顶栏模型
  D4 记录顶栏默认模型名（截图/文字）— 必须是 DeepSeek 或已声明的可用默认
      禁止默认 kimi-k2.x / 坏 Kimi
  D5 发送：「你是什么模型」— 必须成功回复（非「服务暂时出错」）
  D6 回复不得空白；失败则中文可读
  D7 助手品牌/模型名不得误导为「唯一 Kimi 产品」（若显示模型名须与真实路由一致）
  D8 同一默认路径再发：「用一句话介绍你能做什么」— 成功
```

## 3. 小任务序

| ID | 内容 |
|----|------|
| **E0** | 复现业主红（kimi 默认+闲聊失败）· 机内日志根因 |
| **E1** | 默认模型/endpoint → DeepSeek（或统一可用 pico-agent）；禁坏 Kimi 默认 |
| **E2** | 密钥/路由/代理：默认路径 200 流式可用 |
| **E3** | UI 品牌/模型展示与真实路由一致 |
| **E4** | **E2E-DEFAULT D1–D8 全绿**（硬门禁） |
| **E5** | 默认路径上交件一题（真 Word/文件） |
| **E6** | 默认路径短答 17+25→42 |
| **E7** | 默认路径失败诚实 + 再试 |
| **E8** | 回归：pi-agent health + 不回退 S2 交件纪律 |
| **E9** | 证据包 + 请业主同路径复测 |

## 4. 与 CLAIM

```text
本卡未 E4 EXCELLENT 前：CLAIM-WB-DEGREE-WEB = NO（强制）
#322 建议 YES 作废至本卡 E9 业主复测 PASS
```

```
════════════════════════════════════════════════════════
BINDING · E2E-DEFAULT-CHAT
默认路径端到端 · 一票否决 · 禁交件管线冒充默认闲聊
════════════════════════════════════════════════════════
```
