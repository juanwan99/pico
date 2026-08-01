# Pico 版本管理（绑定）

```
DOC: docs/VERSIONING.md
STATUS: BINDING v1.0
SOURCE: edu-cloud AGENTS + SYSTEM-REQUIREMENT 中「版本/交付」内核
ADAPTED: docs/ONEFLOW.md（Pico OneFlow）；未抄 edu 19080/mcu/ECS
RELATED: docs/WORKFLOW.md · AGENTS.md · docs/MVP-3DAY.md
```

## 0. 先答：吸收了没有？

| 类别 | 是否已吸收 | 落点 |
|------|------------|------|
| **代码变更门禁**（分支/PR/全 SHA/CANDIDATE/审查/值守合） | **是** | `WORKFLOW.md` / `AGENTS.md` / MVP S8 |
| **GitHub = 唯一交付事实**（无平行台账） | **是** | WORKFLOW §4 |
| **Agent/依赖钉版本** | **是**（产品层） | D1 freeze + `check_agent_pin` |
| **计划/合同文档 FIXED 升版** | **是** | MVP-3DAY v1.2 等；禁静默改计划 |
| **运行体自证**（代码 SHA + 健康） | **部分** | `/health` 有；缺统一 `/v1/meta/version` 字段约定 → **本文补齐约定** |
| **OneFlow 工作流 + 阶段 A 发布闭环** | **是（适配）** | `ONEFLOW.md`；合 main 后 prod-update + health 自证 |
| **GHCR digest 全自动 UAT→prod（阶段 B）** | **否（后置）** | 未建前不得声称已有 |
| **edu 业务库 revision / 迁移链** | **否** | 业务真源在 edu；Pico 只管 AI 账本 |

**结论：** 与 edu **同一 OneFlow 工作模式**已吸收为 `docs/ONEFLOW.md`；发布为 **阶段 A 闭环**（SHA+热更新），阶段 B digest 轨后置。

---

## 1. 版本是什么（pico）

```text
代码版本   = Git 完整 40 字 commit SHA（及 main 上的 merge commit）
运行版本   = 进程实际加载的代码身份（应可查询）
依赖钉死   = kimi-agent-sdk / kimi-cli 等 pin（冻结表 + CI 检查）
计划版本   = 文档 STATUS: FIXED vx.y（改计划必须升版）
产品壳     = apps/librechat（禁止旧壳回归）
AI 账本    = Pico DB 内 Task/Run/Event（非 edu 业务真源）
```

**exact SHA 证明「跑的是谁」；测试证明「能不能用」——二者不能互换。**  
（与 edu SYSTEM-REQUIREMENT 同构。）

---

## 2. 代码变更版本轨（与 edu 同模式 · 已绑定）

| 规则 | 要求 |
|------|------|
| 一切片 | 一分支、一 PR、一写入 |
| 身份 | **完整 40 字 SHA**（小写 hex）；禁止只报 7 位当审查绑点 |
| CANDIDATE | push 后评论：SHA + 验收映射 + BLOCKED |
| CI | 绑该 SHA 的 required checks 绿 |
| 审查 | 独立上下文；`PASS` 绑**当前**全 SHA；写入不自签 |
| 合入 | **值守**合 main；禁无人值守 |
| 顺序 | 先对齐 main → CI → 再审当前 tip（禁先审后 sync） |
| 事实源 | **仅** GitHub Issue/PR/SHA/CI — **禁止** 人工 VERSION-MAP / 平行状态库 / 交接包当真理 |
| 预览 | 预览环境 **不是** 发布证据（同 edu：Preview ≠ release evidence） |

### 禁止

- 两写入同分支；审查移动 tip  
- 用标签/emoji/评论代替 SHA 身份  
- 自 PASS S1–S8 或「已上线」无 SHA  
- 为版本再建第二套台账文件并要求人肉维护  

---

## 3. 依赖与 Agent 钉版本（已有 · 重申）

| 项 | 规则 |
|----|------|
| Kimi Agent 栈 | **pin** 在 requirements / freeze 检查（**pin ≠ 已接入运行时**）；升 pin 单独 PR + 黄档审查；真接入见 TRUTH-FREEZE D8 |
| 模型 | 默认 API 名可配置；**不**把「随便改模型」当无门禁 |
| 危险工具 | `pico.yaml` + `PICO_DANGEROUS_TOOLS_ENABLED=false`；改安全默认 = **红** |

升 pin 检查：`make freeze-check` / CI `check_agent_pin`。

---

## 4. 计划与合同文档版本

| 文档类型 | 规则 |
|----------|------|
| `STATUS: FIXED` | 改内容必须 **升 VERSION**（如 v1.2 → v1.3），并在 PR 说明 |
| `STATUS: DRAFT` | 可迭代；**不得**冒充 FIXED 约束工程 |
| 商业定价 | **未 FIXED 前** 不锁死汇率/个人钱包自动付校务（业主 REVISE） |
| 工作流本文 | 变更须替换旧句，禁止堆叠冲突层（edu 同款） |

---

## 5. 运行版本自证（约定 · 逐步实现）

目标（对齐 edu「版本自证」精神，形状适合 pico）：

```http
GET /v1/meta/version
→ {
  "ok": true,
  "git_sha": "<40-char or unknown>",
  "service": "pico-api",
  "agent_pins": { "kimi-agent-sdk": "…", "kimi-cli": "…" },
  "dangerous_tools_enabled": false
}
```

| 阶段 | 要求 |
|------|------|
| 现在 | `/health` + `/v1/meta/agent-safety` + `/v1/meta/freeze` 已有碎片 |
| 近期 | 收敛到 `/v1/meta/version`（可一次 PR）；CI 可断言字段存在 |
| 有容器发布后 | 镜像 digest 与 git_sha 一并记录在 GitHub Release/部署记录 — **仍无** 强制 OneFlow |

**禁止** 手写 PRODUCTION_BASELINE 文件充当运行真理。

---

## 6. 明确不从 edu 照搬的

| edu 项 | pico |
|--------|------|
| Actions OneFlow 唯一发布 | 暂无；合 main 是集成默认分支，不是自动生产 |
| UAT 19080 / 生产 mcu.asia | 不适用 |
| candidate 必须是**当前生产运行版本**严格后代 | 有生产轨后再启用；现用 **main 快进 + CI** |
| 业务库 alembic revision 与代码锁步 | 业务库在 **edu**；Pico 账本迁移另册，不冒充教务库 |
| 删除迁移历史导致生产不识版本 | 引为教训：Pico 账本迁移 **禁** 无替代删史 |

---

## 7. 与产品壳版本

| 允许 | 禁止 |
|------|------|
| `apps/librechat` 为产品 UI | 恢复任一已删除旧壳当默认 |
| LibreChat 版本随上游 + 我方补丁 | 双壳并行「都算正式产品」 |

CI：`apps/web` 目录存在 → **失败**（见 workflow）。

---

## 8. 执行检查清单（每 PR）

- [ ] 完整 SHA 写在 CANDIDATE  
- [ ] CI 绿且对应 **该** SHA  
- [ ] 黄/红：独立审查 PASS 绑同一 SHA  
- [ ] 无平行版本台账提交  
- [ ] 计划 FIXED 未私自改字  
- [ ] 未引入 `apps/web`  
- [ ] pin 变更有 freeze-check  

---

## 9. 一句话

**版本管理 = 全 SHA 身份 + GitHub 唯一事实 + 钉依赖 + FIXED 文档纪律；发布轨按 pico 边界演进，不假装 edu OneFlow。**


---

## 10. 事故类：产品壳漂移（2026-07-29）

| 现象 | 预览出现已删除旧壳，不是 LibreChat |
|------|------------------------------------------|
| 根因 | 进程绑错：`apps/web` Vite 占 :8080；main 仍可能含双壳 |
| 修复 | 删除旧壳；只认 `apps/librechat`；CI + `assert-product-identity` |
| 防再发 | `/v1/meta/version` 含 `product_ui_ok`；启动脚本断言；预览前看 identity |

**版本不出问题 = 代码 SHA + 产品壳身份 + pin 三者同时正确。**
