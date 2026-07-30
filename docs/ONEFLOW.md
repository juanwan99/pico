# Pico OneFlow（适配版 · 绑定）

```
DOC: docs/ONEFLOW.md
STATUS: BINDING v1.0
DATE: 2026-07-30
REPO: juanwan99/pico ONLY
SOURCE: edu-cloud docs/SYSTEM-REQUIREMENT.md §1–12 + AGENTS.md（内核）
ADAPT: 无 ECS/19081/mcu.asia/GHCR OneFlow 全链时，用 pico 实体替换并标明「已闭环 / 目标闭环」
LAW: docs/MVP-3DAY.md v1.2 FIXED · docs/MASTER-PLAN.md（导航）
RELATED: docs/WORKFLOW.md · docs/VERSIONING.md · AGENTS.md
```

> **目的：** 让 Pico **用上 OneFlow 同一套操作系统**（一条流、GitHub 唯一事实、角色分离、证据闭环），  
> **不是** 把 edu 的端口/ECS/生产域名抄进 pico。

---

## 0. 一句话

```text
提目标（= 授权同范围 merge + 发布意图）
  → 写入开分支/PR
  → CI + 独立审查（+ 需要时 UI/生产抽检）
  → 总管 merge → main
  → 唯一运行身份 = main 的 exact SHA（部署后 health/git_sha 自证）
  → 用户只看结果，不传技术信
```

**未 MERGED 不算做完。** `CANDIDATE` 与审查 `PASS` ≠ 合并。

---

## 1. 与 edu OneFlow 对照（适配表）

| edu 概念 | Pico 适配 | 闭环状态 |
|----------|-----------|----------|
| 网页 Codex 总管 | **总管**（网页 Codex 或业主指定的总管会话） | 流程闭环：规划/派发/验收/合并汇报 |
| ECS Grok 写入 | **写入**（`Grok-Pico写入` 或 Codex-VPS 写入窗） | 流程闭环：一分支一 PR |
| 独立审查 | `Grok-Pico审查` / 另一只读上下文 | 流程闭环：exact SHA PASS/REVISE |
| GPT-QA | 浏览器验收（Codex 控浏览器或 Playwright） | 有 UI 时闭环 |
| Preview `19081` | 开发：沙箱 `0.0.0.0:8080`；公网演示：`https://pico.aivia.asia` | **环境闭环**（预览≠生产证据） |
| UAT `19080` | **预发抽检** = 部署目标机上对 **候选 SHA** 的冒烟（可与生产同机分步） | 目标闭环；当前常用生产抽检代替独立 UAT |
| 生产 `mcu.asia` | **`https://pico.aivia.asia`**（及 `/opt/pico`） | 运行闭环 |
| GHCR digest 发布 | **阶段 A（现行）**：`main` SHA + `scripts/prod-update.sh` / compose 重建  
  **阶段 B（目标）**：GHCR 镜像 digest + Actions 发布（未建前不得假装已有） | A 已可用；B 后置 |
| Actions 唯一发布操作者 | **阶段 A**：总管授权后 **写入/运维窗** 执行热更新（须回写 PR/Issue SHA）  
  **阶段 B**：仅 Actions 推生产 | A 纪律闭环；B 工程后置 |
| 用户只提目标 | 同 edu：不传 Grok 结果当需求；不日常做技术门禁 | 纪律闭环 |

**禁止把 edu 的 ECS 台账、1908x、mcu 合同直接写进 pico 运行手册。**

---

## 2. 角色（最小职责分离 · 不是官僚体系）

| 角色 | 谁扮演 | 职责 | 禁止 |
|------|--------|------|------|
| **用户** | 业主 | 产品目标；仅红例外（见 §6） | 当信使转发执行结果；日常技术门禁 |
| **总管** | 网页 Codex（推荐）或业主点名会话 | 读 Issue/PR/SHA/CI；拆解；派发；跨切片决策；**门禁后 merge**；一句话结果 | 替写入自签审查 PASS；无依据合红 CI |
| **写入** | Grok-Pico写入 / Codex 工程窗 | 实现、窄测、PR、同范围 CI 修、CANDIDATE、部署回写 | 自 PASS；双写一分支；写 edu |
| **审查** | 未参与该 SHA 写入的只读窗 | exact SHA → PASS/REVISE/BLOCKED | 写业务代码；审移动 tip |
| **运维执行** | 常与写入同一窗（阶段 A） | 热更新、冒烟、端口自检 | 无 SHA 的「感觉上线了」 |

---

## 3. 主路径（强制闭环）

```text
[1 授权] 用户目标 = 同范围 gated merge + 发布意图（默认）
    ↓
[2 切片] 总管：路径不重叠 → 一写入 · 一分支 · 一 PR（可 Draft）
    ↓
[3 实现] 写入：预检 → 改 → 窄测 → push
    ↓
[4 CANDIDATE] PR 评论：40 字 SHA + 验收映射 + BLOCKED
    ↓
[5 门禁并行]
    · CI（Actions）必须绿
    · 黄/红：独立审查 PASS（绑同一完整 SHA）
    · 用户可见：UI/生产抽检 PASS（绑 SHA）
    ↓
[6 MERGE] 总管合 main（CI 红禁止合；写入不自合自己的黄/红）
    ↓
[7 发布] 阶段 A：对齐 main tip → prod-update / rebuild 所需镜像
         回写：生产 health.git_sha == main（或声明延迟）
    ↓
[8 验收] 登录/主路径烟测 + 端口安全；结果只写 GitHub
    ↓
[9 CLEAR] 写入窗关闭；用户只收总管一句话
```

### 闭环检查清单（每切片）

| # | 检查 | 失败则 |
|---|------|--------|
| L1 | PR 指向 `main` 且路径在声明范围 | 不开 CANDIDATE |
| L2 | `CANDIDATE` 含 40 字 SHA | 审查拒收 |
| L3 | 该 SHA 上 CI = success | **禁止 merge** |
| L4 | 黄/红有独立审查 PASS 同 SHA | **禁止 merge** |
| L5 | merge 后 GitHub `main` 含该变更 | 未完成 |
| L6 | 生产 `git_sha` 与意图 tip 一致（或 Issue 注明未部署） | 发布未闭环 |
| L7 | 冒烟证据在 PR/Issue | 不可声称上线成功 |

**脚本辅助（非第二事实源）：** `bash scripts/oneflow-status.sh [sha]`  
只打印 GitHub/本地可重算状态，**不**代替 PR 评论。

---

## 4. 状态词汇（与 edu 对齐 · 禁止发明）

| 词 | 含义 |
|----|------|
| `OPEN` / `KEEP` / `WAIT` / `CLEAR` | 窗态 |
| `CANDIDATE` | 连贯 push 后的合并候选声明 |
| CI `success` / `failure` | Actions |
| `PASS` / `REVISE` / `BLOCKED` | 审查或 UI QA |
| `MERGED` | PR 已合 main |
| `DEPLOYED` | 生产自证 SHA 已对齐（阶段 A 评论声明） |

禁止：自建进度库、百分比仪表盘、mailbox、常驻总控 daemon。

---

## 5. 环境合同（Pico 实体）

| 用途 | 约定 |
|------|------|
| 开发/沙箱预览 | 产品 UI `0.0.0.0:8080`（LibreChat）；API **loopback** |
| 公网演示/生产 | `https://pico.aivia.asia` · 服务器 `/opt/pico` · `docker-compose.host.yml` |
| 内部服务 | Mongo / Pico API / LibreChat **仅 127.0.0.1**；公网仅 443（及 80→443） |
| CI | GitHub Actions `ci.yml` = 合并前门禁 |
| 数据 | 开发用本地/compose seed；**禁止**用生产密钥进仓 |

**预览/演示抽检 ≠ 合并门禁替代 CI。**  
**合 main ≠ 自动生产**（阶段 A 须显式部署步）；阶段 B 建成后由 Actions 独占发布。

---

## 6. 用户与授权

### 用户只负责

| 做 | 不做 |
|----|------|
| 提目标与期望结果 | 日常登录服务器门禁 |
| 看最终结果 | 转发执行日志当需求 |
| 红例外点头 | 替审查写 PASS |

### 仅这些再找用户（红例外）

1. 明确删除生产业务/账本数据  
2. 破坏性恢复 / 数据库 downgrade  
3. 改 Secrets、服务器信任根、GitHub ruleset/CODEOWNERS/Environments  

其余「要不要授权 merge 技术步」：**默认不要**（目标授权已覆盖同范围 merge + 阶段 A 发布意图）。  
若总管判断属扩大 forbidden 或产品二选一 → 再问。

---

## 7. 技术上只保留这些（Pico）

| 用途 | 组件 |
|------|------|
| 代码与审核 | GitHub PR ·（建议）Rulesets |
| 检查 | GitHub Actions `ci.yml` |
| 工作流合同 | `ONEFLOW.md` + `WORKFLOW.md` + `AGENTS.md` |
| 运行自证 | `/health` 的 `git_sha`（及 meta 约定见 VERSIONING） |
| 阶段 A 发布 | `scripts/prod-update.sh` + compose · **结果回写 GitHub** |
| 产品壳 | `apps/librechat` only |

**成熟能力禁止平行自建**（与 edu 同）：不自建调度器、不自建版本台账、不自建第二发布入口。

---

## 8. 风险档与合并权

| 档 | 门禁 |
|----|------|
| 绿 | CI 绿 + 写入自检；总管可合 |
| 黄 | CI 绿 + **独立审查 PASS** + 总管合 |
| 红 | 同上 + 任务范围含红路径的明确目标授权 |

红路径见 `WORKFLOW.md` §5（auth、账本破坏性变更、工作流文件、危险工具等）。

**CI 红：任何角色禁止合 main。**  
（2026-07-30 PR #30：曾先修 ruff 再合 — 作为正面范例。）

---

## 9. 发布闭环（阶段 A 现行）

```bash
# 生产机（示例）
cd /opt/pico
git fetch origin
git checkout main
git pull --ff-only origin main
# 或: EXPECT_SHA_PREFIX=... bash scripts/prod-update.sh
# API 变更 → 重建 pico-api；前端变更 → 重建 librechat
curl -sS http://127.0.0.1:18765/health   # git_sha 应对齐
ss -lntp | grep -E '18765|8080|27017'      # 仅 127.0.0.1
```

PR/Issue 评论模板：

```markdown
## DEPLOYED
- main SHA: <40-char>
- health.git_sha: <40-char>
- smoke: login / chat / artifact / ports
- rebuild: api? librechat?
```

**health ≠ main → 发布未闭环**（除非评论写明延迟原因与计划）。

---

## 10. 与 MASTER / MVP 的关系

| 文档 | 关系 |
|------|------|
| MVP-3DAY v1.2 | 产品成功标准法；S8 = 本 OneFlow 合并门禁 |
| MASTER-PLAN | 阶段导航（M0–M5）；执行须走 OneFlow 主路径 |
| WORKFLOW | 窗/审查/风险细节 |
| ONEFLOW | **端到端操作系统 + 闭环清单** |

冲突时：HARD 范围与 v1.2 > ONEFLOW 细节 > 散文。

---

## 11. 明确不做（防假 OneFlow）

- 在 pico 假装已有 edu 级 GHCR→UAT→prod 全自动（未建前写「目标」即可）  
- 用聊天当唯一状态源  
- 写入自审 PASS 后直接合  
- 合 main 后不部署却声称用户已用上  
- 写 edu-cloud  

---

## 12. 启用声明

自本文件 BINDING v1.0 起：

1. 新切片默认走 §3 主路径。  
2. 总管/写入/审查会话提示词应引用本文件 + `WORKFLOW.md`。  
3. `scripts/oneflow-status.sh` 可作检查辅助，**权威仍在 GitHub**。
