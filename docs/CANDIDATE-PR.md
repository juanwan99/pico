# CANDIDATE — LibreChat 产品壳 + Pico 核接通

```
STATUS: CANDIDATE（写入窗 · VERDICT_AUTHORITY NONE · 不自 PASS）
REPO: juanwan99/pico
BRANCH: grok/pico-preview-librechat-p0
BASE: main
PR: https://github.com/juanwan99/pico/pull/30
FULL_SHA: 3160c8c7da1ac250d27a0954d9760a67b4da8bbd
SHORT: 3160c8c
DATE: 2026-07-30
PLAN: docs/MVP-3DAY.md v1.2 FIXED（本 PR 不升 v1.3）
COMMITS_AHEAD_MAIN: ~42
```

## 一句话

将默认产品壳切换为 **LibreChat（MIT）**，接通 Pico OpenAI 兼容 API / 账本 / Kimi，交付可演示的中文任务工作台；含安全硬化、主路径回归与 S7 最小人确认。

## 范围（做了）

| 域 | 内容 |
|----|------|
| 壳 | `apps/librechat` 为默认；移除 nextchat/workbench/web 默认路径 |
| 预览 | 产品 **:8080**；API **127.0.0.1:18765**；pin 8080；首屏加载文案；SW self-destroy；Mongo 误 pin 症状文档 |
| 模型 | Kimi HTTPS 默认聊天（S1）；`pico-agent` 为显式多步路径（S2 叙事，见 DEMO） |
| 账本 | Task/Run/Event/Artifact/Workspace/Automation；pending rebind |
| 安全 | `/api/pico` JWT；membership 隔离；产物 XSS 收敛；代理默认本机 |
| UI | 任务台 IA、结果区、项目四 Tab、自动化、S7 确认横幅 |
| 文档 | CORRECTED-GOALS、CALIBRATION、ORCHESTRATION、REGRESSION、PREVIEW、CANDIDATE |

## 范围（明确不做 / 已知限制）

- 不写 edu-cloud；不双 AI 真源
- 不拆 WorkBuddy；像素未 100% 对等
- Live Preview :6014 无鉴权时常 403 空 body（平台层）
- 若代理误钉 :27017 会出现 Mongo HTTP 文案 — 须 pin 8080
- S7 为最小闭环（演示提案 + 审计）；非 edu 写回
- S8 须 CI + 独立审查 + 值守；**本文件不是 PASS**
- 商业定价未 FIXED

## 证据图

| 检查 | 结果 | 出处 |
|------|------|------|
| API health | ok | REGRESSION-MAINPATH-RUN |
| 8080 HTML | 200 + 加载文案 | 同左 |
| Kimi 回复 | 回归OK | 同左 |
| hello.txt | file + hi | 同左 |
| rebind | pending→real | 同左 |
| membership | alice/bob 隔离 | 同左 |
| 未登录 /api/pico | 401 | 同左 |
| S7 | confirm/reject | W2-S7-NOTES |
| 6014 | 403 body 0 | PREVIEW-WHITE-SCREEN |

## 审查重点

1. 租户/membership 是否可串读
2. 密钥是否只在服务端
3. startup.sh / run-product.sh 是否可 revive
4. Mongo 会话 vs Pico 账本边界
5. 预览叙事是否诚实

## 合并要求

CANDIDATE → CI → 独立审查 exact SHA → **有人值守**合 main → 写入窗不点 Merge

## 旧 PR

#29 同分支历史 — 合入审查以 **#30** + 本 tip SHA 为准。
