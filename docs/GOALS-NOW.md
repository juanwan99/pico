# Pico 当前目标（执行窗口径 · 2026-07-30）

```
REPO: juanwan99/pico ONLY
SHELL: apps/librechat (MIT)
PLAN: MVP-3DAY v1.2 FIXED（无授权不升 v1.3）
RESEARCH: workbuddy-research + followup（clean-room，禁止拆闭源）
```

## 产品是什么

**Pico = AI 任务工作台底座**

- 对话 + Agent 编排 + 产物 + AI 账本 + 模型 HTTPS API  
- 体验品类：Claude / Codex / **WorkBuddy 级任务台**（不是网盘、不是教务 SaaS、不是纯 Chat）  
- 模型：Kimi API 优先；编排：开源 Kimi Agent 钉版本  
- 默认壳：`apps/librechat` → Pico OpenAI 兼容 API（`:18765` loopback）  
- **禁止**：edu-cloud 双真源；恢复 apps/web / nextchat / workbench；拆 WorkBuddy；自 PASS main  

## 成功形态（用户可见）

1. 登录后是 **任务台首页**（Pico，我帮你 / 场景 / chips / 大输入 / 工作空间·权限）  
2. 发任务后是 **三栏**：任务列表 · 会话运行 · **结果区**（概览含产物 / 工作空间文件 / 浏览器）  
3. 侧栏：新建任务 · 助理 · 项目 · 专家·技能·连接器 · 自动化 · 更多  
4. 真流式 Kimi；失败中文可读；中文 + Pico 品牌  
5. 预览稳定（产品页 8080，不把 API JSON 当首页）  

## 本阶段实施（P0 → P1）

| 优先级 | 目标 |
|--------|------|
| **P0** | 侧栏路由正确；Composer 控件可用；任务中 **结果区骨架**；状态文案对齐调研 |
| **P1** | Task/Run 与会话投影；项目四 Tab；能力中心三分页真接 |
| **P2** | 自动化服务端调度；腾讯系授权墙内能力后置 |

## 浏览器边界（写死）

- 不做：本地全盘文件夹 Agent、桌面退出即停的自动化、微信遥控电脑  
- 做：服务端 Workspace 边界（先 managed）、结果下载/预览、scheduler 后置  

## 证据基线

- 调研包：WorkBuddy v5.3.5 clean-room 观察  
- 关键修正：产物在 **概览内**；右栏三视图；空态「暂无内容 / 空目录 / 暂无连接」  
