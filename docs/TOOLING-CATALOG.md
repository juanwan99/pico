# TOOLING-CATALOG · 批准 / 禁止工具合同

```text
STATUS: BINDING · pico 工具目录（唯一派发 ID 表）
DATE: 2026-08-29
SCOPE: juanwan99/pico · ECS 执行窗 · Cloud Agent
CLAIM-WB: 本文件不签 · 以 STATE-NOW 为准
PARENT: #386 原则 1–7 · #384 视觉门 · host 禁 Cool/Keel
派发: 只勾本表 id；用法在本表；密钥永不进仓
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
| **tip-pin** | 公网 tip 40 位 SHA | `scripts/tip-pin.sh` · [TIP-PROBE.md](./TIP-PROBE.md) | 每测前 / 回执 E0 / DONE | SPA `/health` 的 `OK` 冒充 tip | — |
| **remote-health** | SSH 权威 health | `scripts/remote-health.sh` | 与公网 tip 三行对齐 | Issue 贴 canary membership 列表 | 经 **ssh-ecs** |
| **gh-git** | PR / 证据进仓 | `gh` · `git` | 合入链 | 密钥进 commit；证据截图进 docs PR | `GH_TOKEN` 等（主机已配） |
| **subscribe-pr** | 订 PR 事件唤醒总管 | Cursor `subscribe_github_pr`（repo/pr） | 总管环 OPEN 后 | 当第二账本；代替 Issue 回执 | — |
| **subscribe-ci** | 订分支 CI 终态 | Cursor `subscribe_github_ci` | 执行窗已推分支 | 未知名分支空订 | — |
| **subscribe-timer** | 兜底读合同评论 | Cursor `subscribe_timer` | Issue 评论无原生订约时 | ECS cron 自驱 agent | — |
| **spawn-executor** | 总管起/唤醒执行窗 | `scripts/spawn-executor.sh` → SSH `ecs` → 机上 grok CLI（`scripts/ecs-grok-exec.sh`）；隔离 worktree `/home/ops/pico-wt/issue-N` | `## 派发` 已贴、要起执行窗；黄审过要续派合部 | 总管自己合/部；mailbox；Cursor Cloud Agent / `@cursor` 当执行者；密钥进仓；写 `/opt/pico` 当开发树 | `PICO_EXECUTOR_SSH_HOST`（默认 `ecs`）· 机上 grok 登录 + `~/.grok/env.sh` |

**说明：** `visual-gate` / `tip-pin` 以仓内脚本为准；`tool-status` 对缺失报 `ok:false`。

---

## 2. 部署 / 现网通道（执行窗 · Cloud Agent）

| id | 工具 | 入口 | 何时必须 | 何时禁止 | env 名（无值） |
|----|------|------|----------|----------|----------------|
| **ssh-ecs** | Tailscale → 生产机 | `ssh ecs`（`~/.ssh/config`：`ecs`/`pico-prod`→`aliyun-hy`，User `ops`）· EXPERIENCE §17–19 | 一切 ECS 探活 / prod-update / remote-health | 公网 IP:22；安全组追 Cloud Agent egress | `TS_AUTHKEY` · `PICO_PROD_SSH_PRIVATE_KEY` ·（建议）`PICO_PROD_SSH_USER` · `PICO_PROD_SSH_HOST` |
| **cloud-agent-ts** | Cloud Agent 入网 | `scripts/cloud-agent-install.sh` + `scripts/cloud-agent-start.sh`（或 `~/.local/bin` 同名） | 总管 Cloud Agent 要 SSH 叫醒 ECS grok / 碰机 | 把密钥写进 environment.json；无 draft 验就 Save；把 Cloud Agent 当执行者 | 同上 |
| **prod-update** | exact-SHA 部署 | `PICO_DEPLOY_SHA=<40> bash /opt/pico/scripts/prod-update.sh` | 卡面「有差才部」 | 无 SHA；未 tip 对齐报 DONE | 机上已有 |

---

## 3. 调试 / 工程工具（辅助 · 不当 Ready 真源）

| id | 工具 | 入口 | 何时必须 | 何时禁止 |
|----|------|------|----------|----------|
| **playwright-mcp** | Playwright MCP（chromium） | Grok `mcp_servers.playwright` · `~/.mcp.json` | 对话复点 1 题、探索 | **单独**当 #384 Ready |
| **chrome-devtools-mcp** | Chrome DevTools MCP | Grok `mcp_servers.chrome-devtools` | 修主气泡独白 · Network/Console/SSE | 主 E2E · Ready 真源 |
| **pytest-ruff** | 单测 / 静态检查 | `pytest` · `ruff` | 逻辑回归 | **替代**视觉门写 Ready |

---

## 4. 禁止表（硬）

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
| **Cloud Agent 靠公网 22 / 漂移 egress 白名单当部署通道** | 假通路；真源 = Tailscale MagicDNS（**ssh-ecs**） |
| **Cursor Cloud Agent / `@cursor` / `POST /v1/agents` 当执行者** | 业主令：执行者 = ECS grok CLI；总管 Cloud Agent 只负责派发/订约 |

---

## 5. 卡头强制抄录（D4A · UI/交付/Agent 卡）

完整可复制块见：[`docs/templates/CARD-HEADER-TOOLING.md`](./templates/CARD-HEADER-TOOLING.md)

```text
【视觉门 · BINDING #384】
- 公网浏览器 · 像人点完
- 帧：V0 题面 · V1 过程主气泡 · V2 终态 · V3 产物打开
- 主气泡禁工具/机审独白
- 无图 = 不得请求 Ready
- 审查必须读图；只读表 = 审查无效

【工具合同 · TOOLING-CATALOG】
批准 id：visual-gate · tip-pin · remote-health · gh-git · subscribe-pr · subscribe-ci · subscribe-timer · spawn-executor · ssh-ecs · cloud-agent-ts · prod-update · playwright-mcp · chrome-devtools-mcp · pytest-ruff
回执：bash scripts/tool-status.sh --json（无密）；missing 非空 = BLOCKED（视觉卡）
禁止：Cool/Keel/mailbox · 第二 E2E · 无图 Ready · 公网22当 Cloud Agent 通道 · Cursor Agent 当执行者
CLAIM-WB: 不代签 · 以 STATE-NOW 为准
```

---

## 6. tool-status

```bash
bash scripts/tool-status.sh          # 人类可读
bash scripts/tool-status.sh --json   # 机器 JSON · 贴卡回执（无密）
```

关键字段：`tools.*.ok` · `tip.git_sha`（40 位）· `retired_mechanisms.clear` · `blocked_for_visual_gate` · `missing[]`。

**不含**任何密码/token。`ssh-ecs` / `cloud-agent-ts` 以本机 `ssh ecs` / Tailscale 证伪，不强制写入 tool-status 旧 schema。

---

## 7. 退役机制（archive 路径）

| 原路径 | 处理后 |
|--------|--------|
| `/home/ops/cool-blocks/` | `~/archive/retired-mechanisms-20260809/cool-blocks/` |
| `/home/ops/edu-supervisor-window/` | `~/archive/retired-mechanisms-20260809/edu-supervisor-window/` |

活跃入口必须为 **不存在或不可启动**。`tool-status` 的 `retired_mechanisms.clear=true` 当且仅当活跃路径已断。

---

## 8. 变更

改本表 → PR。任务卡/派发条写 `TOOLING: <id>…`（≤N）。不另建第二工具真源文件。

```text
════════════════════════════════════
BINDING · 工具合同 pico · 唯一 ID 表
批准进仓 · status 证伪 · Cool 清零
ssh-ecs = Tailscale · CLAIM-WB 仅业主
════════════════════════════════════
```
