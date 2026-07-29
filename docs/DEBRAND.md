# 产品去品牌化（Pico）

```
STATUS: BINDING practice
UI: apps/nextchat
```

## 做

- 用户可见：标题、侧栏、设置、导出署名 → **Pico**
- 去掉 NextChat SaaS / 上游 GitHub 入口（产品面）
- 本地存储键 `pico-ai-workspace`（与上游默认隔离）

## 不做 / 禁止

- 删除 `apps/nextchat/THIRD_PARTY_NOTICES.md` 或上游 LICENSE 义务
- 声称 UI 为 100% 自研无开源基础

## 检查

```bash
grep -RIn 'NextChat' apps/nextchat/app --include='*.ts' --include='*.tsx' | grep -v node_modules | head
# 期望：仅 mcp 内部名 / 注释 / notices 可接受残留
```
