# 日间任务书（Issue / PR 正文模板）

```
TYPE: DAY
TOTAL: Grok（总管）
EXEC: Codex（写入）
```

## 指针
- 基线：`origin/main` @ （开跑时 pull）
- 相关计划/卡：

## 目标（单一主目标）
- 

## 非目标
- 

## HARD
- 仅 juanwan99/pico · 禁写 edu-cloud
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key
- 不合自己的黄/红 PR；CANDIDATE 后等审查/总管合 main

## 并行轨（若有）
| 轨 | 窗 | LEASES 可写 | 禁止 |
|----|-----|-------------|------|
| A | | | |
| B | | | |

## 验收
- [ ] 
- [ ] CI 绿 · ## CANDIDATE
- [ ] 总管合 main 后（若需）## DEPLOYED · health.git_sha

## 授权
- [ ] 写入 **无权** 自合本 PR（默认）
- [ ] 例外：总管授权写入代合（仅绿/文档）：____
