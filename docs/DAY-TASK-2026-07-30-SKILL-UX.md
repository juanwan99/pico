# 日间任务书 · Skill 扩容 + 体验债（并行双轨）

```
DOC: docs/DAY-TASK-2026-07-30-SKILL-UX.md
TYPE: DAY
STATUS: COMPLETED · #55 Skill expansion + #56 UX debt
DATE: 2026-07-30
TOTAL: Grok（总管/审查）
EXEC: Codex（写入）· 云端
BASE: 开跑时 git pull origin main（派工时 tip 约 ea5749b+）
RACI: docs/RACI-GROK-CODEX.md
TEMPLATE: docs/templates/DAY-TASK-ISSUE.md
PRIOR: N3 DEPLOYED @ db4c69f；RACI REVISE @ #53
```

## 背景（只读）

- N1/N2/N3 已合；三技能 thin + 能力中心快路径可用。
- 下一产品增量：**Skill ≥8** + **体验债**；不接 M5 真连。
- 交接只走 GitHub；完成 = PR + CI + 审查 + **总管合 main** +（动运行时）DEPLOYED。

## 总目标

1. Pico 受控技能从 3 扩到 **≥8**（policy + deployment SKILL.md + Hub 列表同步）。
2. 落地 **≥4** 项体验债（见轨 B）。
3. 防回归：smoke/selftest 覆盖新技能 id（策略层至少）。

## 非目标

- 写 edu-cloud · M5 live · PROXY=1 · 第二 Skill 商店 · 像素 100% · 升 v1.3

## HARD

- 仅 `juanwan99/pico`
- 工具 ⊆ 全局白名单求交；write 类 `requires_s7`
- SKILL.md **无** `displayTitle`
- ADR A：LC Skills 唯一产品目录；Hub = 快路径
- 写入 **默认不合** 自己的功能 PR；`## CANDIDATE` 后等总管审查/合 main
- 禁打印 key；禁公网 18765/27017/8080

## 并行轨（能并行则并行）

| 轨 | 窗建议 | LEASES 可写 | 禁止 |
|----|--------|-------------|------|
| **A · Skill 扩容** | Codex 窗 A | `services/orchestrator/pico_orchestrator/skill_policy.py` · `apps/librechat/skill/**` · `scripts/n3_skill_snapshot_smoke.py` · `scripts/agent-selftest.sh` · `tests/unit/test_skill_policy.py` · Hub 内 **仅** DEMO_SKILLS 列表/文案 | Workbench 大布局、Automation/Files 大改、矩阵全文重写 |
| **B · 体验债** | Codex 窗 B（可与 A 同时） | `apps/librechat/client/**` 除 CapabilityHub 的 **DEMO_SKILLS 数组**（Hub 其他 UI 可改）· `Landing`/`ProjectWorkspace`/`FilesHub`/`Automation`/`Nav` 等 | `skill_policy.py` · 新增 skill 目录 · orchestrator |

**共享冲突：** `CapabilityHubPage.tsx` — **轨 A 优先**改技能列表；轨 B 若需改同文件 → **WAIT A 合 main 后 rebase**，或只改非 DEMO_SKILLS 区块并沟通 PR 顺序。

**单 Codex 时：** 先 A 后 B（或一 PR 两轨但报告分节）；有两窗则同时开。

---

### 轨 A 验收

- [ ] ≥8 个 `skill-*`：policy + `apps/librechat/skill/<id>/SKILL.md`
- [ ] 建议新增示例（可调整命名，须稳定 id）：
  - `skill-summarize`（chat/low）
  - `skill-lesson-outline`（chat/low）
  - `skill-quiz-draft`（chat/low）
  - `skill-translate`（chat/low）
  - `skill-meeting-notes`（chat/low）
  - 保持原 chat/read/write-s7
- [ ] Hub DEMO_SKILLS 与 policy 同步；文案区分快路径 vs `/skills`
- [ ] `n3_skill_snapshot_smoke.py`（或继任脚本）覆盖全部 id；CI 仍绿
- [ ] unit test 更新

### 轨 B 验收（≥4 项）

从下列点餐，**至少 4 项**有代码 + 简述：

- e 侧栏折叠不丢当前任务  
- f 暗色模式主路径对比度  
- g 结果区执行中骨架/spinner 统一  
- h 登录失败/过期 token 不白屏  
- i 能力中心 390 可用  
- j 自动化绑定 skill 进可观察 payload/元数据（诚实边界）  
- k assistants 与 skill 预填不互相覆盖  
- l more/files 空态 CTA  

### 合并与部署

1. 每轨（或合并）PR → `## CANDIDATE` + 40 字 SHA  
2. CI 绿  
3. **总管审查 PASS 后合 main**（写入不自合黄/红）  
4. 写入部署：rebuild 所需镜像 → `## DEPLOYED` + health  

## 报告头（贴 PR）

```
## 日间执行结果
- track: A | B | A+B
- START_SHA / PR SHA:
- skills (ids):
- UX items (e–l):
- CI:
- 请总管审查合 main（未自合）
- 声明: 未写 edu · 未 M5 · 未第二目录
```

## 总管备注

- 审查模板：`docs/templates/REVIEW-COMMENT.md`  
- 交卷模板：`docs/templates/CANDIDATE-DEPLOYED.md`  
