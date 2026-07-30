# CANDIDATE — LibreChat 产品壳 + Pico 核接通



## 一句话

将默认产品壳切换为 **LibreChat（MIT）**，接通 Pico OpenAI 兼容 API / 账本 / Kimi，交付可演示的中文任务工作台；含安全硬化、主路径回归与 S7 最小人确认。

## 范围（做了）

| 域 | 内容 |
|----|------|
| 壳 |  为默认；移除 nextchat/workbench/web 默认路径 |
| 预览 | 产品 **:8080**；API **127.0.0.1:18765**；pin 8080；首屏「Pico 正在加载…」；SW self-destroy；Mongo 误 pin 症状文档 |
| 模型 | Kimi HTTPS 默认聊天（S1）； 为显式多步路径（S2 叙事，见 DEMO） |
| 账本 | Task/Run/Event/Artifact/Workspace/Automation；pending rebind |
| 安全 |  JWT；membership 隔离；产物 XSS 收敛；代理默认本机 |
| UI | 任务台 IA、结果区、项目四 Tab、自动化、S7 确认横幅 |
| 文档 | CORRECTED-GOALS、CALIBRATION、ORCHESTRATION、REGRESSION、PREVIEW-WHITE-SCREEN、CANDIDATE |

## 范围（明确不做 / 已知限制）

- **不**写 edu-cloud；**不**双 AI 真源  
- **不**拆 WorkBuddy；像素未 100% 对等  
- Live Preview **:6014** 无鉴权时常 **403 空 body**（平台层；本机 8080 绿 ≠ 面板绿）  
- 若代理误钉 **:27017** 会出现  — 须 pin **8080**  
- S7 为最小闭环（演示提案 + 审计）；非 edu 写回  
- S8 合入须 **CI + 独立审查 + 值守**；本文件 **不是 PASS**  
- 商业定价未 FIXED  

## 证据图

| 检查 | 结果 | 出处 |
|------|------|------|
| API health | ok | REGRESSION-MAINPATH-RUN |
| 8080 HTML | 200 + 加载文案 | 同左 |
| Kimi 回复 | 回归OK | 同左 |
| hello.txt 产物 | file + hi | 同左 |
| rebind | pending→real | 同左 |
| membership 隔离 | alice/bob | 同左 |
| 未登录 /api/pico | 401 | 同左 |
| S7 confirm/reject | confirmed / rejected | W2-S7-NOTES |
| 6014 | 403 body 0 | PREVIEW-WHITE-SCREEN |
| startup | bash run-product.sh | 5c9bd9a |

## 审查请重点看

1. 租户/membership 是否可串读  
2. 密钥是否只在服务端  
3. 合入后  / [pico] wrote self-destroying sw.js
[pico] LibreChat :3080  public :8080  API :18765 (loopback)  pin→8080 是否可 revive  
4. 是否误把 Mongo 会话当 AI 业务真源  
5. 预览叙事是否诚实（6014 / 误 pin 27017）  

## 合并要求



## 与旧 PR

- #29 同分支历史预览修复 PR — 以 **#30** 为合入载体（审查请对 **526635d9bd54695db71349565f19317154ea9fde**）
