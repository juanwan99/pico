# 日间任务 · N3 Skill 未知 fail-closed + 主路径加固

```
TYPE: DAY
SPRINT: docs/SPRINT-FAST.md（仍在 7 日窗内）
STATUS: OPEN · 总管派工
PRIOR: N1 P0 + N2 轨 C 已 DEPLOYED（业主确认继续推进）
RISK: 黄（行为安全 · 非改 JWT 语义）→ FAST 代合可
```

## 背景

Codex 体检：拼错/未知 skill 标记被剥掉后 `snapshot=None`，可能 **开放全部工具（fail-open）**。  
N1/N2 已完成；本刀修这个洞，并做一轮生产回归。

## 目标

1. **未知 / 拼错 skill → fail-closed**  
   - 有 skill 标记但解析不到 policy：不得 `allowed_tools=None` 放开全家桶  
   - 行为二选一（实现选更安全清晰的）：  
     a) 降级为 **chat-only**（tools=[]）并 event/日志标明 `skill.unknown`  
     b) 直接 400 + 明确错误  
   - **推荐 a）**，避免前端整段失败；单测必须覆盖 `skill-reead` 一类拼写  
2. 已知 skill 行为不变（read/write_s7/summarize 等）  
3. 单测 + 可选 smoke  
4. 部署生产 + 验证窗回归  

## 非目标

M5、像素、PG/队列、扩 Skill 数量、大改 UI。

## 【给：② 执行窗 · ECS】

```text
读 docs/DAY-TASK-N3-SKILL-FAILCLOSED.md。
实现未知 skill fail-closed（推荐 chat-only + skill.unknown 事件/日志）。
单测：拼错 skill 不得拿到 workspace_write 等全工具集。
PR → CI 绿 → RISK:黄 FAST 代合 → 跳板部署 → ## DEPLOYED（2h）。
强制 GitHub 回写。禁 edu-cloud / PROXY=1。
```

## 【给：③ 验证窗 · 本地】

```text
部署后 4h：
1) 正常 skill.summarize / pico-agent 仍能用工具（不回归）
2) 故意拼错 skill 标记：不应出现全工具乱写；应为无工具或明确拒绝
3) P0 抽检：pico-dev 401 仍在
## TEST REPORT 贴实现 PR。无报告=未交付。
```

## 完成定义

- [ ] 代码合 main  
- [ ] ## DEPLOYED health 对齐  
- [ ] ## TEST REPORT PASS  
