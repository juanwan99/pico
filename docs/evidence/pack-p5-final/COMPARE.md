# P5 · 对比表 · Pico Web vs WorkBuddy 教程级「做出东西」主路径

```text
BINDING: T-PACK-P5-FINAL-CLAIM-MATERIALS (#426) · 当前公网 tip 实查为准
日期: 2026-08-10
WB 侧口径: WorkBuddy 为桌面产品，本表 WB 行为以「教程/公开演示推断」为主（未实测 WB 本体）；
Pico 侧: 全部为本窗公网实测（visual-gate 帧 + L2 账本 + DOM）。
禁止空口「全面碾压」——每格写证据指针。
CLAIM-WB: NO（仅业主）
```

## 1. 不弱（对 WB 教程级「做出东西」主路径 · 逐项公网证据）

| 维度 | WB 侧（教程推断） | Pico 侧（本窗实测） | 证据指针 |
|------|-------------------|---------------------|----------|
| 自然语言开干（不锁场景卡） | 教程主路径为对话里直接派活 | 任意自然语言新题直接开干，无场景卡菜单 | `s1-open-multifile` V0/V2（新员工入职 checklist 当场新题） |
| 真产物落盘 / 可下可开 | 教程：生成文件到本地 workDir | 真文件落账本、可下载、sha256 可核 | `s1-open-multifile` ledger：`新员工入职第一周-checklist.md`（2656B · sha256 `d23b62c7…`）· `s2-open-office-multi`：4 文件（634–784B · 各自 sha256） |
| 多文件 / 打包 | 教程：一次交付多文件 | 多文件链实测通过 | `s2-open-office-multi`：`任务清单/时间安排表/休息提醒/今日小结模板` 4 个 .md · delivery.summary `artifact_count=4, ok=true` |
| 同会话修订（改一版） | 教程：同会话续聊改版 | 同会话 v1→v2 修订成功 | `s3-open-revise`：v1 `9c853fbf…` → v2 `d62eb33b…` · delivery.summary `revision=true` · 帧 R1/R2 |
| 短答不硬塞文件 | 教程：短答直接回话 | 纯闲聊无任务、无假文件条 | `s4-open-chat`：无 task（`task_count=0`）、无 artifact · 干净短答 |
| 边界诚实（不冒充桌面/像素） | — | 诚实限制全文见 `README` §6 | 见下「诚实限制」 |

## 2. 更强（Pico 差异化 · 各 ≥1 硬证据）

| 更强 | 含义 | 硬证据（帧 / run / 摘录） |
|------|------|---------------------------|
| **A · 状态同真相** | 有件不假失败 · 恢复徽章语义 · UI=账本 | ① 恢复链：`f2-open-html-page` 时间线 `workspace_write_file` 失败 → `generate_html_document` 成功 → 运行成功，DOM 徽章为「失败 · 已恢复」（非裸失败）· 帧 `timeline-dom.png`；② L2 事件流 `tool.result` 逐条可对账 |
| **B · 成品主列主权** | 主列成品条 · 人页打开 | `f2-open-html-page` V3：`main-delivery-open` 点击 → `main-delivery-iframe` 打开人页（标题「桌面植物浇水记录板」· 4 盆植物 · 重置按钮）· `scene_visual_pass_eligible=true` |
| **C · tip/账本可审计** | 40 位 tip · run_id · delivery.summary | tip 实查 `6fd55ab80aa1575bdf49b68e6f3984a4e65f0dd4`（curl `/api/pico/tip`）；每个场景 `run_id` + `delivery.summary`（`artifact_count / min_required / ok`）+ 事件流可回放；skill_snapshot 记录 skill 绑定（`skill-engineering-delivery`） |

## 3. 能力架（六条 #2 · Web 诚实边界）

- `/api/pico/v1/skills/catalog` 实测 ≥5 skill：`skill.deliverable` · `skill.engineering_delivery` · `skill.chat` · `skill.read` · `skill.write-s7` …
- 每次 run 的 `skill.snapshot` 记录实际绑定 skill 及其工具集（等价绑定有据）。
- UI 可见入口：侧栏「专家·技能·连接器」（帧内可见）。
- **Web 诚实边界**：本 build 以「skill 自动绑定 + 目录可见」为主；前台逐 skill 手动点选的完整市场 UI 未在本 build 验证（如实标注）。

## 4. 诚实限制（方案自证 · 写明不做/不能）

```text
门脸 Pico · 核 Pi · 模型 DeepSeek（health/事件字段为真源）
Web ≠ 桌面 workDir（不声称 1:1 WorkBuddy）
非像素级克隆 · 未拆闭源
MCP = 桥接非自研协议栈 · 无连接器市场
产品级自动压缩等高级能力未具备
```

## 5. 已知缺口 / 黄债（诚实 · 无假绿）

- ~~F5（W5 类裸「多文件交付」）初测 0 文件假绿~~ → **已修复 #427（tip `27954b2a`）· 复测 PASS（5 真文件 · `min_required=2` · `multi_deliverable=true`）**
- 其余见 `README.md` §黄债。

## 6. 结论（供总管）

- 不弱：**成立**（六项逐条公网证据）
- 更强 A/B/C：**各有 ≥1 硬证据**
- 复测 F1–F6 **均无 P0**（F5 复测 tip `27954b2a` 已关闭）
- `RECOMMENDATION: YES 候选`
- `CLAIM-WB-DEGREE-WEB: PENDING`（仅业主）
