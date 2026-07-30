# 工作台点击地图（全面对齐 · 进行中）

```
DOC: docs/WORKBENCH-CLICK-MAP.md
STATUS: LIVING
```

业主要求：**像素 + 业务逻辑 + 图标点进后的界面** 全面对齐，非仅首页壳。

## 左栏点击 → 二级界面

| 入口 | 路由 | 打开后 | 业务 |
|------|------|--------|------|
| 新建任务 | `/c/new` | 首页「Pico，我帮你」 | 提交 → 会话 + 账本 Task |
| 助理 | `/assistants` | 列表+详情双栏 | 选助理 → 新建任务（可带专家） |
| 项目 | `/projects` | LibreChat Projects | 项目工作区 |
| 专家·技能·连接器 | `/capability` | Tab：专家/技能/连接器 | 专家详情→召唤；技能→灌 prompt；连接器→详情页 |
| 连接器项 | `/capability/connectors/:id` | 权限/后置说明 | 可用则回任务 |
| 自动化 | `/automation` | 列表+创建表单 | Pico `/v1/automations` 真调度 |
| 更多 | `/more` | 资料库网格 | 就绪项可点 |
| 我的文件 | `/more/files` | 账本产物列表 | list tasks + artifacts |
| 灵感 | `/capability?tab=skills` | 技能 tab | 同上 |
| 任务列表项 | `/c/:id` | 中栏对话+右结果区 | 账本 rebind/产物 |
| 空间 | `/workspaces` | 创建/列表/删除 | Pico `/v1/workspaces` |
| 结果区底部 | `/more/files` | 全局产物 | 与右栏同源 |

## 后置（点开有壳、能力未做满）

微信遥控、腾讯文档、ima/乐享知识库、邮箱、自定义连接器配置。

## 下一刀

- 项目工作区与结果区文件树更贴
- 自动化九字段更满（若 v1.2 允许）
- 有业主截图则按图校二级页间距
