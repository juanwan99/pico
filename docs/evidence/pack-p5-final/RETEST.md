# P5 · 复测包 · F1–F6（当前公网 tip · 开放域新表述）

```text
tip: 6fd55ab80aa1575bdf49b68e6f3984a4e65f0dd4
方法: L1 帧（visual-gate）+ L2 账本（/api/pico/v1）+ L3（有异常必写）
禁止题词 if · 有 P0 → RCA→FIX→复测
```

## 复测结果表

| ID | 场景 | 现 tip 结果 | P0？ | 证据 |
|----|------|-------------|------|------|
| **F1** | 多文件办公包 ≥3 | **PASS** · 4 真文件 · `artifact_count=4, ok=true` | 无 | `s2-open-office-multi`（ledger + 帧） |
| **F2** | 单 HTML「可下载的」人页 | **PASS** · `main-delivery-open` → `main-delivery-iframe` 打开人页 · `runnable_html=true` · `scene_visual_pass_eligible=true` | 无 | `f2-open-html-page`（V3 + manifest） |
| **F3** | 恢复链（工具失败→成功） | **PASS** · `workspace_write_file` 失败 → `generate_html_document` 成功 → `verify_html_document` 成功 → 运行成功 | 无 | `f2-open-html-page`（tool.result 事件 + timeline-dom.png） |
| **F4** | 闲聊 | **PASS** · 短答 · `task_count=0` · 无假成品条 | 无 | `s4-open-chat`（ledger + 帧） |
| **F5** | W5 脏活链 / W2 多件交付 | **FAIL（P0）→ 修复 #427 → 复测待部署** | **是（已修）** | `f5-open-w5-chain`（初测 0 文件假绿 · 见下） |
| **F6** | 徽章「失败 · 已恢复」 | **PASS** · DOM 时间线 `工具结果 · workspace_write_file` = **「失败 · 已恢复」**（非裸失败）→ 运行成功 | 无 | `f2-open-html-page/timeline-dom.png` |

## F5 详情（P0 · 诚实记录）

```text
初测（tip 6fd55ab · 开放域新表述）:
  提示词: 请帮我完成一条任务链（就"是否把公司周五下午设为自由工作时段"）：
          ①调研备忘 ②决策一页纸 ③待办表 ④给团队和领导的短消息各一条。多文件交付、跨文件数字一致。
  现象:   主气泡输出全链内容 · 0 真文件 · delivery.summary {artifact_count:0, min_required:0, ok:true}
          事件流仅 artifact.created + delivery.summary · 无 agent.step / tool 调用
  P0:     0 文件装成功（假绿）

RCA:
  - _MULTI_PHRASE / _EXPLICIT_MULTI_FILE 仅匹配「多个/多份」，裸「多文件交付」未命中
  - 行内 ①②③（非行首）不计入 structure_n → min_required=0 → 假绿

FIX（通用 · 非题词）:
  PR #427 · SHA 743aa22 · 量词 个/份 可选 → 裸「多文件/多产物/多交付」→ multi → min≥2 + fail-closed
  +3 单测 · tests/unit 260 passed · ruff clean · CI 绿

复测（待合并部署后）:
  - 同一提示词重跑 → 预期：fail-closed（0 文件诚实失败）或真文件交付
```

## 附：P4 黄债承接

| P4 黄债 | P5 处置 |
|---------|---------|
| 成功旁裸「失败」徽标（d2/R3） | **F6 现 tip DOM 已为「失败 · 已恢复」** → 黄债关闭 |
| 欠交付 live 难触发 | 未复现为 P0 · 承 P4 说明（高负载 token cap） |
| F5 裸「多文件交付」缺口 | **新发现 P0 → 修复 #427 → 复测** |
