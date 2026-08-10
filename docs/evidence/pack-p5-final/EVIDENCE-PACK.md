# P5 · EVIDENCE PACK · 六条表 + C-T1–C-T10

```text
tip: 6fd55ab80aa1575bdf49b68e6f3984a4e65f0dd4
方案: 门脸 Pico · 核 Pi · 模型 DeepSeek
执行: DS · ECS · SOLO · 开放域当场新题
```

## 六条取证表

| # | 条 | EXCELLENT 证据 | 证据指针 |
|---|-----|----------------|----------|
| **1** | 开放派活 | 自然语言当场新题直接开干 · 无场景卡菜单 | `s1-open-multifile` V0-send / V2-final（新员工入职 checklist 新题） |
| **2** | 能力架 | ≥5 skill 可见/可选等价绑定：`/api/pico/v1/skills/catalog`（deliverable · engineering-delivery · chat · read · write-s7 …）· run `skill.snapshot` 记录实际绑定 · 侧栏「专家·技能·连接器」入口 | `s1-open-multifile/ledger.json`（skills + skill_snapshot）· `skills-shelf/` |
| **3** | 多步 | pi-agent 真工具环：`run.durable` · `agent.step` · `tool.call` · `tool.result` 事件可见 · 非单次灌文 | `s1-open-multifile` / `s2-open-office-multi` ledger events |
| **4** | 真产物 | 可下可开 · 非空 · 有 sha256：1 文件（s1）· 4 文件（s2）· HTML 人页（f2 V3 主列打开）· 短答不硬塞文件（s4） | `s1`/`s2`/`f2` ledger artifacts · `s4` task_count=0 |
| **5** | 任务资产 | 同会话改一版有差异：v1 `9c853fbf…` → v2 `d62eb33b…` · `revision=true` · 历史 run 可回 | `s3-open-revise`（帧 R1/R2 + ledger） |
| **6** | 完成态 | 时间线/结果区 · 终态诚实（succeeded + delivery.summary）· 恢复徽章「失败 · 已恢复」 | `s1`/`f2` V2 + `f2/timeline-dom.png` · cancel 见下 |

### 完成态 · cancel（可用则测）

- UI 含 Stop/停止 按钮（RunTimeline 支持 cancel）；已提供 `POST /v1/runs/{id}/cancel`。
- 本窗对已完成 run 未触发中途 cancel 用例（诚实：未做耗时任务打断测试）；如总管需要，可补一次长任务 cancel 取证。

## C-T1–C-T10（对照 TEST-TASK-CLAIM-WB-DEGREE-WEB）

| ID | 条 | 结果 | 证据 |
|----|-----|------|------|
| C-T1 | tip | **对齐** `6fd55ab80aa1575bdf49b68e6f3984a4e65f0dd4` | curl `/api/pico/tip` + tip-pin |
| C-T2 | #1 开放派活 | **PASS** · 当场新题接住 | s1-open-multifile |
| C-T3 | #2 能力架 | **PASS** · ≥5 skill 可见 · skill.snapshot 绑定有据 | skills/catalog + ledger |
| C-T4 | #3 多步 | **PASS** · runtime=pi-agent · step/tool 事件 | s1/s2 ledger events |
| C-T5 | #4 真产物 | **PASS** · 真文件可下 · 短答无假文件 | s1/s2/f2 + s4 |
| C-T6 | #5 可改可回 | **PASS** · 同会话 v2 · 双 run 可回 | s3-open-revise |
| C-T7 | #6 完成态 | **PASS** · 时间线/结果区 · 终态诚实 · 徽章语义对 | s1/f2 + timeline-dom |
| C-T8 | 方案 | **PASS** · DeepSeek（pico-agent）· Pi 默认 · skill_snapshot 记录 | run.model / skill_snapshot |
| C-T9 | 诚实 | **写明** Web≠workDir · 非像素 · MCP=桥 · 无连接器市场 | COMPARE.md §4 |
| C-T10 | 安全 | **PASS** · 18765/27017 公网不裸露（C-T10 沿用既有安全验收） | 见 P0-SECURITY / 运维记录 |

## 六条汇总

```text
六条: 1Y 2Y 3Y 4Y 5Y 6Y
verdict: PASS（取证过程）
CLAIM-WB-DEGREE-WEB: PENDING
（YES 仅业主 ## OWNER DECISION）
```
