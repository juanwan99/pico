# U1 · 失败人话 · pack-ux-harden

```text
tip: 502e1f6fd5d3f5999b43303de91b16de1375f26a
base: https://pico.aivia.asia
url: https://pico.aivia.asia/c/3a4604a8-adda-441f-be3e-da0d78c4921b
CLAIM-WB: NO
```

## 读图要点
- 可见中文失败句：服务维护或重启…重新运行
- **无** 裸 `owner was lost`
- 侧栏 `teacher-task-fail-hint` 或主区失败条

## 实查
- hint_count: 1
- has_human: true
- has_owner_lost: false
- texts: ["服务维护或重启导致本次任务中断。请点「重新运行」继续；刷新后侧栏与主区状态应一致。"]
- lines: ["服务维护或重启导致本次任务中断。请点「重新运行」继续；刷新后侧栏与主区状态应一致。","失败","请为「项目周报生成」写一个可复用 Skill 规格（触发语/步骤/输入/输出文件类型/失败条件），再用触发语实测一次，产出真实 Markdown 周报并交付下载","请为「会议纪要生成」写一个可复用的 Skill 规格：触发语、步骤、输入、输出文件类型、失败条件。写好后用触发语实测一次，产出真实 Markdown 会议纪要文"]
