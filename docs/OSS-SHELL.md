> **STATUS: LibreChat is the product shell.** `apps/web` / `nextchat` / `workbench` removed. See also `CORRECTED-GOALS.md`.

# Pico 产品壳：开源选型（WorkBuddy 品类）

> 原则：**找开源壳魔改，不从零画工作台；不拆闭源 WorkBuddy。**  
> 状态：DRAFT · 2026-07-29 · 仅限 pico

## 目标品类（对照你截图）

WorkBuddy 类 **任务工作台**：

- 左栏：新建任务 / 助理 / 项目 / 专家·技能·连接器 / 自动化  
- 中区：模式切换 + 能力 chip + 大输入卡  
- 不是纯 ChatGPT 气泡列表  

## 候选对照

| 方案 | 形态 | 像 WorkBuddy？ | 接 Pico API | 许可 | 本环境 | 结论 |
|------|------|----------------|-------------|------|--------|------|
| **LibreChat** | Web 产品 + Agent/MCP | 中高（Agent Builder，需改首页成任务台） | **OpenAI 兼容最好** | **MIT** | 需 Mongo（无 Docker 时重） | **主选：长期产品壳** |
| **AionUi** | 桌面 Cowork / 多 Agent | **高**（品类最近） | 可配模型/CLI | Apache-2.0 | Electron，预览难 | **桌面轨参考 / 可选二期** |
| **OpenHands** | Web Agent + 终端/文件 | 高（偏工程 Agent） | 可接模型 | MIT | 通常要 Docker 沙盒 | 工程向备选 |
| **LobeChat** | Web 好看 Chat | 中 | 好 | **社区证限制二次商用分发** | 重 monorepo | **不选（许可风险）** |
| **Open WebUI** | Web + 知识库 | 低～中 | 好 | BSD 系 | 中 | 知识库轨，非任务台 |
| **NextChat / workbench** | — | — | — | — | **已删除** | 勿恢复为默认 |
| WorkBuddy 本体 | 闭源桌面 | 目标参考 | 可配 API | 闭源 | 不可拆 | **禁止 fork 源码** |

## 拍板建议

```text
终局壳 = LibreChat（MIT）魔改
  1) 默认 endpoint → Pico /v1/chat/completions
  2) 中文 + 去 LibreChat 品牌 → Pico
  3) 首页 IA 改成 WorkBuddy 类：任务/模式/chip/大输入（可复用 workbench 布局进 LibreChat 主题）
  4) Agent/MCP 面板保留，对接 Pico 工具环（后置）

并行参考 = AionUi（桌面 Cowork 信息架构）
禁止     = LobeChat 商用分发风险；拆 WorkBuddy 安装包
```

## 接入分期

| 期 | 内容 | 成功标准 |
|----|------|----------|
| **S0** | 选型文档（本文）+ workbench 过渡 | 预览可聊 |
| **S1** | 引入 LibreChat（submodule 或 vendor）+ 最小配置指到 Pico | 浏览器打开 LibreChat，走 Pico 流式 |
| **S2** | 中文 / 去品牌 / 登录对齐 school JWT | 教师演示账号可用 |
| **S3** | 首页改任务台 IA（移植 workbench 布局） | 截图像 WorkBuddy 品类 |
| **S4** | 助理 / 技能面板接 Pico 工具白名单 | 非空壳 |

## 依赖说明（S1）

- LibreChat 常规依赖 **MongoDB**（及可选 Meilisearch）。  
- 本沙箱若无 Docker，S1 需：嵌入式 Mongo 或远程 Mongo，或本地 `mongodb-memory-server` 仅开发。  
- 生产学校部署：compose 一键（API + LibreChat + Mongo）。

## 与后端边界

- **唯一 AI 账本 / 租户 / 工具环** = Pico API  
- LibreChat = **壳 + 会话 UI**，禁止变成第二账本  
- 禁止 edu-cloud 双 AI  

