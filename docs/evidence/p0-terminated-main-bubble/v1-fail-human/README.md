# V1 · 主区失败中文（#458）

```text
tip: bbe59f67ed507bfe126a44cb3e6a6c9ef4a0df20
conversation: https://pico.aivia.asia/c/b3317da9-5711-49d9-b416-96c9fb21436e
CLAIM-WB: NO
```

## 读图

- 主区错误气泡：**中文**「服务维护或重启导致本次任务中断。请点「重新运行」继续；侧栏失败说明与主区应一致。」（#457 `humanizeChatErrorText`）
- **无** `Something went wrong` · **无** 裸 `terminated` · **无** `owner was lost`
- 侧栏同任务：失败 + 中文维护说明
- 顶栏：失败摘要 + **重新运行**
- 右栏：运行失败中文 + 本次未产出文件

## 机器摘要

见 [report-main.json](./report-main.json) · [report.json](./report.json)

## 结论

执行者自读图: **PASS**（主区中文失败 + 侧栏一致）
