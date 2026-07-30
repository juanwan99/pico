# 中文改造说明（LibreChat 壳）

```
DOC: docs/I18N-CN.md
SHELL: apps/librechat
DEFAULT: zh-Hans（简体中文）
```

## 产品默认

| 项 | 值 |
|----|-----|
| 默认语言 | `zh-Hans` |
| 回退 | `zh-Hans` → `en` |
| 浏览器残留 `en` | 视为未设置，强制产品中文（沙箱 Playwright 常写 en） |
| 文案文件 | `apps/librechat/client/src/locales/zh-Hans/translation.json` |
| 初始化 | `locales/i18n.ts` + `store/language.ts` + `index.html` 早期 seed |

## 润色原则（不要机翻腔）

1. **短、像产品**：登录/导航/按钮用口语化短句（「欢迎回来」「新对话」「退出登录」）。  
2. **少「您必须/进行/相关」**：能删则删。  
3. **品牌**：用户可见处用 **Pico**，不写 LibreChat（配置文件名 `librechat.yaml` 可保留）。  
4. **术语统一**：对话 / 智能体 / 设置 / 主题 / 深色·浅色。  
5. 缺 key 时回退英文；高频界面优先补中文。

## 演示账号

- 邮箱：`teacher@example.com`  
- 密码：`pico-demo-123`  
- 登录页应显示：**欢迎回来**（不是 Welcome back）

## 历史说明

旧文档指向 `apps/nextchat` 的 `cn` locale —— **已废**；以本页与 LibreChat `zh-Hans` 为准。


## 覆盖面（2026-07-29 补齐）

- 补全 `zh-Hans` 相对 `en` 的缺失 key（高频 UI + 项目/MCP/快捷键/设置等）
- 硬编码英文 aria 改 i18n：添加文件选项 / 工具选项 / 调整侧栏 / 对话列表
- 页脚与关于页品牌：LibreChat → **Pico**
- 登录后主界面实测：`项目` / `对话` / `智能体市场` / 中文页脚，无 Welcome back / Projects 残留
