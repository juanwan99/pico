# 日间 · 轨 C · 工作台与自动化「真用」

```
TYPE: DAY
TRACK: C
PLAN: docs/STANDALONE-AI-24H.md
LEASES: apps/librechat/client Workbench/Projects/Automation/Files · 必要 api automation
FORBID: skill_policy 大改 · tools_builtin · DEMO_SKILLS 数组（B 的）
```

## 给 Codex-C

```text
git fetch && pull main
读 STANDALONE-AI-24H D5 D6。
1) 项目维度：任务/产物在项目上下文可见（最小可用，不求像素）。
2) 自动化：提供「运行一次」真调用（创建 Run 或等价 API），去掉纯假 Run；失败可见。
3) 文件库与主路径产物一致。
PR → CANDIDATE → 等总管。
可与 A 并行（零文件冲突时）。
```

## 验收

- [ ] 自动化至少 1 次真执行证据
- [ ] 项目内可见任务或产物入口
