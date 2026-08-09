# TOOLING-CATALOG · 批准 / 禁止工具合同

```text
STATUS: BINDING · pico 工具目录（#386 D1A · #387）
DATE: 2026-08-09
SCOPE: juanwan99/pico · ECS 执行窗
CLAIM-WB: NO · 本文件不签产品 Ready
PARENT: #386 原则 1–7 · #384 视觉门 · host 禁 Cool/Keel
```

## 0. 铁律

```text
GitHub = 批准/禁止合同（主管可读、可派工）
ECS    = 实装 + scripts/tool-status.sh（执行可证伪）
密钥永不进仓 / Issue
不造第二协调系统 · 不复活 Cool/Keel/mailbox/relay/self-drive
#384 读图真源不变 · 本目录不替代视觉验收
missing 非空或 blocked_for_visual_gate → 卡内 BLOCKED，禁止写场景视觉过/Ready
```

| # | 原则 |
|---|------|
| 1 | 合同进仓，状态可探，密钥永不进仓 |
| 2 | 目录 ≠ 已安装；回执必须带 tool-status（#386 D2A · 不定时刷 Issue） |
| 3 | 一仓一份批准表；项目只可收紧 |
| 4 | 批准表 + 禁止表；禁止愿望清单 |
| 5 | **证据工具** vs **调试工具** 分栏 |
| 6 | 退役机制磁盘级清零（archive 后断入口） |
| 7 | 耐久事实在 GitHub Issue/PR/SHA/CI |

---

## 1. 证据工具（#384 Ready 相关 · 主路径）

| id | 工具 | 入口 | 何时必须 | 何时禁止 | env 名（无值） |
|----|------|------|----------|----------|----------------|
| **visual-gate** | 公网 V0–V3 强制截图 | `scripts/visual-gate.mjs` · [VISUAL-GATE.md](./VISUAL-GATE.md) | UI/交付/Agent 场景验收 | 散文「我测了」无图；各窗另写截图脚本 | `DEMO_EMAIL` / `DEMO_PASSWORD` 或 `PICO_E2E_*` |
| **tip-pin** | 公网 tip 40 位 SHA | `scripts/tip-pin.sh` · [TIP-PROBE.md](./TIP-PROBE.md) | 每测前 / 回执 E0 | SPA `/health` 的 `OK` 冒充 tip | — |
| **remote-health** | SSH 权威 health | `scripts/remote-health.sh` | 与公网 tip 三行对齐 | Issue 贴 canary membership 列表 | SSH host 配置 |
| **gh-git** | PR / 证据进仓 | `gh` · `git` | 合入链 · 证据 PR | 密钥进 commit | `GH_TOKEN` 等（主机已配） |

**说明：** `visual-gate` / `tip-pin` 以仓内脚本为准（见 #385 合入状态）；`tool-status` 对缺失报 `ok:false`。

---

## 2. 调试 / 工程工具（辅助 · 不当 Ready 真源）

| id | 工具 | 入口 | 何时必须 | 何时禁止 |
|----|------|------|----------|----------|
| **playwright-mcp** | Playwright MCP（chromium） | Grok `mcp_servers.playwright` · `~/.mcp.json` | 对话复点 1 题、探索 | **单独**当 #384 Ready |
| **chrome-devtools-mcp** | Chrome DevTools MCP | Grok `mcp_servers.chrome-devtools` | 修主气泡独白 · Network/Console/SSE | 主 E2E · Ready 真源 |
| **pytest-ruff** | 单测 / 静态检查 | `pytest` · `ruff` | 逻辑回归 | **替代**视觉门写 Ready |

---

## 3. 禁止表（硬）

| 禁止 | 原因 |
|------|------|
| **Cool / Keel / mailbox / relay / self-drive / 常驻总控 daemon** | 已退役；host AGENTS 明文禁；磁盘须 archive 清零 |
| **coordinator / 自建进度库 / 与 GitHub 平行状态系统** | OneFlow 禁止 |
| **Selenium / Cypress 第二 E2E 栈** | 裂证据格式 |
| **Browser Use / Stagehand 当 #384 Ready 真源** | 可探索但不当 CI/Ready |
| **Percy / Applitools 替代主气泡读图** | 不对症独白/假成功 |
| **闭源 Computer Use 当验收真源** | 不贴双模 ECS + tip/证据仓 |
| **无图 Ready / 只读表审查** | #384 一票否决 |
| **密钥、DEMO 密码进 GitHub/Issue** | 安全 |

---

## 4. 卡头强制抄录（D4A · UI/交付/Agent 卡）

完整可复制块见：[`docs/templates/CARD-HEADER-TOOLING.md`](./templates/CARD-HEADER-TOOLING.md)

```text
【视觉门 · BINDING #384】
- 公网浏览器 · 像人点完
- 帧：V0 题面 · V1 过程主气泡 · V2 终态 · V3 产物打开
- 主气泡禁工具/机审独白
- 无图 = 不得请求 Ready
- 审查必须读图；只读表 = 审查无效

【工具合同 · TOOLING-CATALOG】
批准 id：visual-gate · tip-pin · playwright-mcp · chrome-devtools-mcp · gh-git · pytest-ruff · remote-health
回执：bash scripts/tool-status.sh --json（无密）；missing 非空 = BLOCKED
禁止：Cool/Keel/mailbox · 第二 E2E · 无图 Ready · 只读表审查
CLAIM-WB: NO
```

---

## 5. tool-status

```bash
bash scripts/tool-status.sh          # 人类可读
bash scripts/tool-status.sh --json   # 机器 JSON · 贴 PR/卡回执
```

关键字段：`tools.*.ok` · `tip.git_sha`（40 位）· `retired_mechanisms.clear` · `blocked_for_visual_gate` · `missing[]`。

**不含**任何密码/token。

---

## 6. 退役机制（archive 路径）

| 原路径 | 处理后 |
|--------|--------|
| `/home/ops/cool-blocks/` | `~/archive/retired-mechanisms-20260809/cool-blocks/` |
| `/home/ops/edu-supervisor-window/` | `~/archive/retired-mechanisms-20260809/edu-supervisor-window/` |

活跃入口必须为 **不存在或不可启动**。`tool-status` 的 `retired_mechanisms.clear=true` 当且仅当活跃路径已断。

---

## 7. 变更

改本表 → PR · 引用 #386/#387 · 任务卡写 `TOOLING: CATALOG@<本文件路径>`。

```text
════════════════════════════════════
BINDING · 工具合同 pico
批准进仓 · status 证伪 · Cool 清零
不替 #384 读图 · CLAIM-WB 仅业主
════════════════════════════════════
```
