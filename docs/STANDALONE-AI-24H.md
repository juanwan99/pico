# 24h 夯实计划 · Standalone AI Complete（零 edu 也完整）

```
DOC: docs/STANDALONE-AI-24H.md
STATUS: BINDING · 总管派工
DATE: 2026-07-30
HORIZON: ~24 小时墙钟（可跨日间+夜间）
TOTAL: Grok（总管/审查/合 main）
EXEC: Codex（写入 · 可多窗并行）
RACI: docs/RACI-GROK-CODEX.md
DEPLOY: docs/DEPLOY-TWO-HOST.md（有跳板则部署；无则只合 main + 诚实未部署）
PRODUCT: 不接 edu 也具备完整 AI 工作台能力
```

## 0. 插队门禁（总管 2026-07-30）

Codex 体检后：**P0 安全收口优先于轨 C 加厚**。见 `docs/P0-SECURITY-HARDENING.md`。

## 0b. 目标句（本 24h 唯一北极星）

> **零 edu 配置下**，用户能：选技能 → Agent 多步执行 → 过程可见 → **本地工具真生效** → 产物进账本/右栏 → 项目可沉淀 → 危险动作走 S7。  
> edu 保持 fake/合同，**本 24h 不做 M5 真连**。

### 完成定义（24h 结束必须可勾）

| ID | 验收 | 证据 |
|----|------|------|
| D1 | 白名单工具 ≥ **6** 个非 edu 实用工具（见 §2） | 单测 + smoke |
| D2 | 默认 Agent（pico-agent / 多步）能 **真实调用** 其中 ≥3 个工具完成任务 | 集成测或生产/本地脚本 |
| D3 | ≥8 skills 中 **≥5** 个绑定真实 tool 子集（非空 tools 或明确 chat-only） | skill_policy + smoke |
| D4 | 工作区产物：生成 → 列表 → 打开/下载 **全 Y**（已有则加固回归） | selftest |
| D5 | 项目内任务产物可关联展示（最小：conversation/project 维度可见） | UI 或 API 证据 |
| D6 | 自动化：**至少一种** 真触发（手动 Run 一次 或 cron 最小）写 Run/产物；禁止纯假按钮 | API+UI |
| D7 | 主路径回归 + 8 skill snapshot 不回退 | CI + 报告 |
| D8 | 有跳板则 main 部署 + DEPLOYED；无则标注 BLOCKED-DEPLOY | PR 评论 |

### 非目标（24h 禁止冲）

- M5 live edu · 写 edu-cloud · 像素 100% · 升 v1.3 · 第二 Skill 商店 · PROXY=1

---

## 1. 时间盒总览（~24h 墙钟）

| 波次 | 墙钟（示意） | 模式 | 内容 |
|------|--------------|------|------|
| **W0** | 0–1h | 总管+写入准备 | 拉 main、确认跳板、开轨 A/B/C 分支 |
| **W1** | 1–8h | **日间并行三轨** | A 工具内核 · B 技能真绑定 · C 工作台/自动化最小真 |
| **W2** | 8–14h | 合流+加固 | 冲突单写、测全绿、主路径回归 |
| **W3** | 14–20h | **夜间加厚（~6h）** | 深 Agent 体验 + 更多工具/技能 + 可靠（见 §4） |
| **W4** | 20–24h | 门禁收口 | 总管审合、部署或诚实 BLOCKED、总验收表 |

可压缩：若 W1 三轨 4h 内合完，提前进 W3 加厚。

---

## 2. 工具清单（轨 A 必达 · 可扩）

在 `tools_builtin` / gateway **全局白名单** 增加（名称可微调，语义保留）：

| 工具 | 作用 | 风险 |
|------|------|------|
| `workspace_write_file` | 写文本产物（标题+内容）→ Artifact | 低·账本 |
| `workspace_read_file` | 按 artifact id 或 title 读已有产物 | 低 |
| `workspace_list_files` | 列当前 principal 产物 | 低 |
| `json_extract` 或 `structured_outline` | 从文本抽 JSON/大纲结构 | 低 |
| `calculator` | 安全四则/表达式 | 低 |
| `pico_propose_change` | **保留** S7 | 中 |
| `echo` | 可保留调试 | 低 |
| `fake_edu_*` | **保留但不作为完整 AI 依赖** | — |

约束：

- 一律 membership 隔离  
- 写文件必须走账本 Artifact，禁止随便写宿主机路径  
- 禁止任意 shell；若加 `safe_http_get` 必须域名白名单且默认关  

---

## 3. 并行轨（W1 · 能并行则并行）

| 轨 | 窗 | LEASES 可写 | 禁止 | 交付 |
|----|-----|-------------|------|------|
| **A 工具+Runner** | Codex-A | `services/orchestrator/**` · `services/api/**` 接线 · `tests/**` · `scripts/*smoke*` | 大改 LibreChat 页面 | D1 D2 测绿 PR |
| **B 技能真绑定** | Codex-B | `skill_policy.py` · `apps/librechat/skill/**` · Hub DEMO_SKILLS 列表/文案 · skill smoke | 改 gateway 注册表（等 A 合后 rebase） | D3 PR |
| **C 工作台真用** | Codex-C | `apps/librechat/client/**` Automation/Projects/Files · 相关 API 若仅 C 用 | `skill_policy` 大改；与 A 争 tools_builtin | D5 D6 PR |

**冲突规则：**

- `tools_builtin.py` / `gateway.py` / `runner.py` → **仅 A**  
- A 未合 main 前，B 用「预期工具名」写 skill tools，CI 可先 mock；A 合后 B rebase 实绑  
- `CapabilityHubPage` DEMO_SKILLS → **B 优先**；C 勿改该数组  
- 发布：各轨 PR 独立 → 总管审 → 合 main 顺序建议 **A → B → C**（或 A∥C 若零文件冲突）

### 轨 A 任务书（复制执行）

见 `docs/DAY-TASK-24H-TRACK-A-TOOLS.md`

### 轨 B / C

见同目录 `DAY-TASK-24H-TRACK-B-SKILLS.md` · `DAY-TASK-24H-TRACK-C-WORKBENCH.md`

---

## 4. 夜间加厚 W3（~6h · 多包 · 可控风险）

在 A/B/C 已合或大部合后，**单 Codex 长窗**（或再拆）：

| 强制包 | 内容 |
|--------|------|
| N1 | Agent 过程 UI：步骤/工具调用可见（最小 event 流展示） |
| N2 | 再 +2～3 工具 或 强化 write/read 体验 |
| N3 | 技能扩到 10+ 或 垂直模板（教案/纪要/翻译）真跑通 |
| N4 | 失败重试/取消与前端一致；selftest 扩工具步 |
| 储备 | 简易「重新运行」；导出多个 artifact；暗色/390 回归 |

规则：`docs/NIGHT-CARD-POLICY.md` + RACI §3（约 6h、≥3 强制包+储备）。

任务书：`docs/NIGHT-CARD-24H-W3-STANDALONE.md`

---

## 5. 总管门禁

```text
每 PR：CANDIDATE → CI 绿 → 总管 REVIEW PASS → 合 main →（跳板）DEPLOYED
禁止写入自合黄/红；禁止假 DEPLOYED
24h 末：勾 D1–D8 或书面 BLOCKED 原因
```

---

## 6. 与旧计划关系

- 取代「M5 优先」为本阶段北极星  
- N1–N3 / Skill×8 / UX 债 **保留为已交付基线**  
- M5 runbook 仍在，**24h 不执行真连**  
- 生产跳板：`DEPLOY-TWO-HOST.md`

---

## 7. 进度日志（执行中回写 PR，勿只改聊天）

| 时间 | 事件 | SHA/PR |
|------|------|--------|
| 派工 | 本文 BINDING | （合 main 后填） |
| | | |
