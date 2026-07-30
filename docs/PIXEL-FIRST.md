# 产品优先级：先像，再个性化

```
DOC: docs/PIXEL-FIRST.md
STATUS: OWNER DIRECTION (2026-07-30)
```

## 业主口径（HARD）

> **先做出来像（WorkBuddy 级任务工作台观感），才能保证功能正常验收；后期再个性化。**

| 顺序 | 含义 |
|------|------|
| 1 | **布局/IA 像素对齐**（左导航 · 中任务 · 右结果区 · 首页 chips） |
| 2 | **功能挂到像的壳上**（账本/产物/确认进结果区与状态条） |
| 3 | 品牌色、文案、场景个性化 |

**禁止**用「功能通了所以像素不急」压过业主优先级。  
**仍禁止**拆闭源；对齐 = clean-room 参考公开 IA + 业主截图。

## 当前壳已有

- 左：`UnifiedSidebar` WorkBuddy 导航
- 中：`Landing`「Pico，我帮你」+ chips + composer
- 右：`ResultPanel` 概览/文件/浏览器
- 顶：`TaskRunBar` + `ChangeConfirmBanner`

## 差距（诚实）

- 密度、空态、动效、结果区默认常显、任务列表状态色 — 仍未到「一眼就是」
- 继续以 **右栏 + 首页 + 侧栏** 三刀加深像素，再挂功能

## 开发门禁

本地：改 UI → build client（若环境允许）→ selftest API 不回归  
生产：视觉验收以业主浏览器为准
