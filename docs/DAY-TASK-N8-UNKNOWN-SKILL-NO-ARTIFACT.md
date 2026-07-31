# 日间任务 · N8 未知 skill 禁止旁路产物

```
TYPE: DAY
STATUS: OPEN
RISK: 黄 · FAST
context_reset: false
PRIOR: DEBT D11 / N3 回归
```

## 目标

未知 skill（`skill.unknown` / tools=[]）路径下：

- **不得** 因回复文本抽取器自动 `workspace_write` / 落 Artifact
- **不得** 生成 S7 proposal
- 单测：skill-reead 类 → 0 tool、0 新 artifact、0 change

## 非目标

M5、改 skill 目录结构。
