# Pico agent rules (binding)

> **现况只认下面框。其余当索引不当现况。卡面四行。怎么跟业主说话不限。**

```text
最高: 禁止自搞一套体系。禁止做重体系 / 厚桥 / 第二能力核。
      只允许薄适配。桥变厚=违法。详见 docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md §0-supreme
真源: GitHub Issue/PR/SHA/CI + 公网 tip。聊天/磁盘/STATE-NOW 都不是账本。
人:   本窗合一。不设主管/执行者编制。业主抽检与 CLAIM-WB 不代签。
版本: 只有 origin/main 是生产线。旁支不准部。长分叉只移植、禁止整枝合。
      live = curl tip，必须是 origin/main 上的 SHA。GitHub 旁支头不是版本。
工位: 写码 /home/ops/pico · 生产 /opt/pico 只 prod-update（干净+detached）
环:   从 origin/main 开枝 → 改+测 → PR → CI绿 → squash 合 main
      → 必须 prod-update → curl tip = origin/main。业主靠现网看效果。
禁止: 主管/执行者两套编制 · mailbox · 在 /opt/pico 改业务 · docker compose 当发布
      旁支部 live · 整枝合长分叉 · 直推 main · 合了不部 · Closes部前关卡 · docs-only 不部
新窗: curl tip + GitHub 在飞最多 1。无在飞则讨论。
```


## HARD SCOPE — READ FIRST

```
REPO_OF_RECORD: juanwan99/pico ONLY
FORBIDDEN: any clone/edit/PR/CI/merge on juanwan99/edu-cloud (or any other repo)
OWNER_ORDER: 你只管 pico — permanent; not optional; not overridden by "Phase 3" wording
```

| Allowed | Forbidden |
|---------|-----------|
| Read/write **this** repo (`pico`) | Write/PR/CI/merge on **edu-cloud** |
| Docs, API, UI, orchestrator, tests **in pico** | Implementing edu issuer/modules/frontend |
| Phase 2/3 **Pico-side** adapters/hooks/docs | Dual AI ledger / dual-run with edu AI |
| **Read-only** reference to edu AGENTS for product patterns | Copying edu ECS/1908x/mcu.asia as if pico owned them; **`juanwan99/oneflow` archived · not BINDING** |
| Pico **OneFlow 适配版** (`docs/ONEFLOW.md`) | Pretending full GHCR→UAT auto-prod exists before stage B |

If work needs edu source changes → **stop and say so**; do not open edu.


## LAW — NO SELF-BUILD · THIN ADAPTER ONLY（BINDING）

**全文：** [`docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

```text
最高：禁止自搞一套体系。禁止做重体系。
Pico 禁止自研内核/协议栈/Agent OS/第二编排真源。
只允许对成熟上游做薄适配（接线·白名单·账本·门闩·人包·门脸）。
桥变厚 = 违法。真核 = 上游 Pi harness，不是 Pi-inspired 自写 loop 冒充。
```

| Allowed | Forbidden |
|---------|-----------|
| 真 Pi RPC/SDK 薄客户端 + gateway 回调 | 自研 agent loop 当长期主核加厚 |
| 事件映射进唯一 Pico 账本 | 第二套账本 / 第二默认核 |
| 门闩·人包·假绿防护·租户 | 自研 MCP 协议栈 / 向量库内核 |
| 白名单工具（无公网 bash） | 桥内再造 delivery 全家桶 / 私有 OS / 自搞一套重体系 |

PR 必须能回答：适配哪段？上游是谁？升级是否只改适配层？

---

---

## Execution workflow (binding) — **本窗合一 · GitHub 唯一真源**

形状指针：[`docs/ONEFLOW.md`](docs/ONEFLOW.md)（机械门留下；主管/执行者编制已废）。  
节奏：[`docs/FAST-PATH.md`](docs/FAST-PATH.md)。版本：[`docs/VERSIONING.md`](docs/VERSIONING.md)。  
Helper（非真源）：`bash scripts/oneflow-status.sh`

```text
从 origin/main 开枝 → 改+测 → PR → CI 绿 → squash 合 main
  → 必须 prod-update（/opt/pico）→ curl tip = origin/main
  → 公网看得见再关。业主靠现网看效果。小改可无卡，但合了仍必须部。
```

| 门 | |
|----|---|
| 真源 | GitHub Issue/PR/SHA/CI + `curl -fsS https://pico.aivia.asia/api/pico/tip` |
| 版本 | 只部 `origin/main` 上的 SHA。旁支不是 live。长分叉只移植 |
| 人 | 本窗合一：改、测、合、部同一窗 |
| 隔离 | 一件事一分支一 PR。翻车回原 PR |
| 绿档 | CI 绿即可合 |
| 黄/红 | 另一双眼睛、exact SHA；换核/密钥/租户业主抽检。CLAIM-WB 不代签 |
| 工位 | 写码 `/home/ops/pico`；生产 `/opt/pico` 只 `PICO_DEPLOY_SHA=<40> bash /opt/pico/scripts/prod-update.sh` |
| 过门 | 公网看得见结果句。CI/API 200 不算过门 |
| 卫生 | 开窗 curl tip；收工 tip = origin/main、写码树干净。不是第二人 |

Do **not** invent coordinators, mailboxes, leases, or auto-dispatchers.

**Tooling contract:** [`docs/TOOLING-CATALOG.md`](docs/TOOLING-CATALOG.md) · probe: `bash scripts/tool-status.sh --json` · card header: [`docs/templates/CARD-HEADER-TOOLING.md`](docs/templates/CARD-HEADER-TOOLING.md).  
Do **not** route Cool/Keel/supervisor/mailbox/relay/self-drive. Visual Ready still requires [#384](https://github.com/juanwan99/pico/issues/384) frames — catalog does not replace reading PNGs.

---

## Corrected goals snapshot

Owner-aligned goals: [`docs/CORRECTED-GOALS.md`](docs/CORRECTED-GOALS.md).

**Truth freeze:** [`docs/TRUTH-FREEZE.md`](docs/TRUTH-FREEZE.md)  
**What is Pico:** [`docs/WHAT-IS-PICO.md`](docs/WHAT-IS-PICO.md)  
**Current snapshot:** [`docs/STATE-NOW.md`](docs/STATE-NOW.md) — **开窗索引**（三行）。对不上以 GitHub 执行卡 + 公网 tip 为准。  
**Memory reset:** [`docs/MEMORY-RESET.md`](docs/MEMORY-RESET.md) — **本周 ≤3 坑**，禁止加长。  
**Stage package:** [`docs/STAGE-PACKAGE-MODE.md`](docs/STAGE-PACKAGE-MODE.md) — 单窗阶段包（废默认多窗碎卡）。  
**Task card format:** [`docs/ONEFLOW.md`](docs/ONEFLOW.md) + [`docs/TASK-CARD-STANDARD.md`](docs/TASK-CARD-STANDARD.md) — Issue 用标准任务卡。禁止 315。禁止用四行短卡当已派。  
**开工先读：** [`docs/EXPERIENCE.md`](docs/EXPERIENCE.md)。派发条点名编号，不抄全文。调查写进 Issue。  
**Doc index (truth order):** [`docs/README.md`](docs/README.md) — prefer GitHub over prose.

**Context policy:** [`docs/CONTEXT-POLICY.md`](docs/CONTEXT-POLICY.md)（默认不清理上下文）  
**Controller bot (7x24):** [`docs/CONTROLLER-BOT.md`](docs/CONTROLLER-BOT.md) — 考古/机制；**派工只认 GitHub 执行卡**  
**Controller poll:** [`docs/CONTROLLER-POLL.md`](docs/CONTROLLER-POLL.md) — 非真源  
**Execution queue:** [`docs/EXECUTION-QUEUE.md`](docs/EXECUTION-QUEUE.md) — **SUPERSEDED** 自动 E1/E2/E3；勿当现行派工  
**Validation queue:** [`docs/VALIDATION-QUEUE.md`](docs/VALIDATION-QUEUE.md)  
**FAST sprint:** [`docs/SPRINT-FAST.md`](docs/SPRINT-FAST.md)  
**P0 security:** [`docs/P0-SECURITY-HARDENING.md`](docs/P0-SECURITY-HARDENING.md)  
**Test window:** [`docs/TEST-WINDOW.md`](docs/TEST-WINDOW.md)  
**24h Standalone AI:** [`docs/STANDALONE-AI-24H.md`](docs/STANDALONE-AI-24H.md) (historical baseline)  
**Current dispatch:** GitHub 执行卡（最多 1）· [`docs/STATE-NOW.md`](docs/STATE-NOW.md) 三行只是索引。`DAY-TASK-*` / #310 / #627 / 已关 #646 **不当现况**。   
**Kimi legacy:** [`docs/KIMI-AGENT-GAP.md`](docs/KIMI-AGENT-GAP.md) 仅考古/回滚；**产品默认 = Pi**  
**KA-4:** soft historical [`docs/KA4-SOFT.md`](docs/KA4-SOFT.md) **superseded** · ops: [`docs/OPS-RUNBOOK-STABILIZE.md`](docs/OPS-RUNBOOK-STABILIZE.md)  
**Skill ADR:** [`docs/ADR-SKILL-CATALOG.md`](docs/ADR-SKILL-CATALOG.md).  
**Completed foundation sprint:** [`docs/SPRINT-3DAY-PUSH.md`](docs/SPRINT-3DAY-PUSH.md) (COMPLETED).  
**Completed day task (do not re-open):** [`docs/DAY-TASK-2026-07-30-SKILL-UX.md`](docs/DAY-TASK-2026-07-30-SKILL-UX.md)

Do **not** use `docs/archive/**`、新 HANDOFF markdown、或已 SUPERSEDED 的 `HANDOFF-NEW-WINDOW-2026-08-23.md` 当现况。

## Product rules
- **Org:** **本窗合一**（写/合/部/收尾同一窗）。旧窗1/2/4 与主管/执行者是历史别名，不是编制。见 [docs/MEMORY-RESET.md](docs/MEMORY-RESET.md)。
- **Ship steps:** [docs/FAST-PATH.md](docs/FAST-PATH.md) — change → merge → prod-update → chat/stop → 3-line report. **One window** runs the chain; no multi-issue process OS.
- **Product goal:** Web WorkBuddy degree — [docs/DIRECTION-NOW.md](docs/DIRECTION-NOW.md) §0-star。用法 = Grok。
- **Default runtime:** **Pi** + **DeepSeek**. Kimi Agent = **legacy rollback only**. Self-built `run_agent_loop` stays **deleted** (never the goal).
- **Prod flags:** `PICO_PI_AGENT_RUNTIME=1` default; legacy Kimi only if emergency. Do **not** claim `CLAIM-WB-DEGREE-WEB` until six bars + GitHub evidence.
- **KA-4 HARD:** `run_agent_loop` / `runner.py` **removed**. Rollback multi-step = redeploy prior tip or legacy flag — not revive loop.
- **Speed:** deploy + smoke beat new process docs; see `docs/VELOCITY-CLEAN.md`.
- Tenant fail-closed; **Pico owns the unique AI ledger**.
- Prefer smallest correct fix; no dual-run; no dual-kernel product truth.

## Speed vs safety

**Default org:** 本窗合一 + 阶段包 ([STAGE-PACKAGE-MODE](docs/STAGE-PACKAGE-MODE.md))。  
**Default tech rhythm:** [docs/FAST-PATH.md](docs/FAST-PATH.md) 同一窗串行。

**KEEP:** secrets out of git; allowlist tools; exact-SHA deploy; CI green; no fake global / WB CLAIM; no dual-run; **Pi + DeepSeek default**.

**CUT:** 主管/执行者编制、stamp-ok/派发条/收尾六步/CANDIDATE 总线、多窗日常派、碎卡、mailbox、旁支部 live、整枝合长分叉、把 ECS 当账本、Kimi-as-only-goal、Dify-as-product。

PRs stay (one writer / one branch / CI). Do **not** split one theme into many waiting rounds or many windows.

