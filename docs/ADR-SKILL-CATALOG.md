# ADR：Skill 产品目录唯一来源

```
DOC: docs/ADR-SKILL-CATALOG.md
STATUS: ACCEPTED · A：唯一产品目录 = LibreChat Skills；Pico 只写 Run 受控快照
DATE: 2026-07-30
DECIDERS: 业主 · 总管 · 实现窗（Codex）
```

## 上下文

- LibreChat 上游已有 **Skills** 面：`/api/skills`、客户端 Skills UI、数据层与手动调用链。  
- 并行计划曾拟新增 Pico **`/v1/skills`**，有 **两套目录** 风险。  
- Pico 需要：受控工具子集、Run 审计快照、`skill_id`、与 S7 联动——不必再造第二套「技能商店 UI」。

## 决策驱动

1. 用户只看到 **一套** 技能/能力入口。  
2. 执行仍受 **全局工具白名单** 约束（Skill 只能收窄）。  
3. 账本 Run 必须能存 **受控快照**（与上游可变配置解耦）。  
4. 60–90 分钟只读调查可验证现状后再写代码。

## 选项

| 选项 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **A** | **以 LibreChat Skills 为唯一产品目录**；Pico API 只提供执行快照/校验/绑定，不暴露第二列表 UI | 复用 UI；少分裂 | 需理清 LC 数据与 Pico 快照映射 |
| **B** | **以 Pico `/v1/skills` 为唯一目录**；隐藏/停用 LC Skills UI 与入口 | 合同清晰、审计简单 | 丢上游能力；UI 重做成本 |
| **C** | 双目录并存 | 无 | **拒绝** |

## 决策（N2 只读调查后确认）

**选 A：**

1. **产品目录 = LibreChat Skills**（能力中心入口指到现有 Skills 体验，或包装同一数据源）。  
2. **Pico** 增加最小能力：  
   - 校验 Skill 引用的工具 ⊆ 白名单；  
   - 启动 Run 时写入 **immutable snapshot**（id、名、工具列表、risk、prompt hash）；  
   - 可选 `GET /v1/skills/snapshots/{run_id}` 供审计，**不是**第二套浏览目录。  
3. 若 LC Skills 无法承载「risk→S7」元数据：在 **同一对象** 上扩 metadata 或旁路 `docs/skills/overlays/*.yaml` **按 id 附着**，仍不出现第二浏览 UI。  
4. 仅当 N0 只读调查证明 LC Skills 无法复用时，**书面改选 B** 并隐藏 LC 入口。

## N0 只读调查清单（60–90 min · 不写功能）

```text
☑ 定位 LC /api/skills 与 DB/模型
☑ 定位客户端 Skills UI 路由与能力中心关系
☑ 手动调用链如何进 agent/tools
☑ 能否附加 metadata（risk、requires_s7）
☑ 映射表：LC skill id → Pico snapshot 字段
☑ 结论：A 或 B + 一句话理由
```

调查结果写入本 ADR「调查记录」节后，**STATUS → ACCEPTED**。

## 后果

- Track S **禁止**在 ACCEPTED 前合并「新公共技能商店」。  
- N2 只做 **chat / read / write_s7** 三条纵向，挂在唯一目录上。  

## 调查记录

| 日期 | 结论 A/B | 证据 | 签名 |
|------|----------|------|------|
| 2026-07-30 | A | 后端 `apps/librechat/api/server/routes/skills.js` 已挂 `/api/skills`，含 list/get/create/patch/delete/import/files、JWT、RBAC 与 deployment skill 合并；`apps/librechat/api/server/index.js` 启动 `initializeDeploymentSkills` 并挂 `/api/skills`。前端 `apps/librechat/client/src/components/Skills/**`、`src/routes/__tests__/skillsRoutes.spec.tsx`、`src/hooks/Nav/useSideNavLinks.ts` 已有 Skills 页面与导航；输入框 `src/components/Chat/Input/SkillsCommand.tsx` 通过 `$` popover 写 `pendingManualSkills`，`src/hooks/Chat/useChatFunctions.ts` 与 `packages/data-provider/src/createPayload.ts` 把 `manualSkills` 送入 agent 请求；后端 `packages/api/src/agents/initialize.ts`/`skills.ts` 解析并注入 SKILL.md、按 agent scope/ACL/active state 收敛。Pico 现有 `RunRow.token_usage_json`、`run_service.py`、`openai_compat.py` 足够存不可变快照；`pico_orchestrator.tools_builtin` 的全局白名单可做工具交集；`ChangeProposalRow` 与 `/v1/changes`/`ChangeConfirmBanner` 已承载 S7。 | Codex N2 |

## 快照映射

| LibreChat 来源字段 | Pico Run 快照字段 | 说明 |
|--------------------|-------------------|------|
| `skill.name` / deployment folder | `skill.id` | N2 只接三条稳定演示 id：`skill-chat`、`skill-read`、`skill-write-s7`；LibreChat 仍为唯一浏览目录 |
| `displayTitle` / `name` | `skill.name` | 面向审计报告的人类可读名 |
| `tools` frontmatter / Pico overlay | `skill.tools` | 与 `build_default_gateway()` 全局白名单求交；Skill 只能收窄 |
| `risk` / `requires_s7` overlay | `skill.risk`、`skill.requires_s7` | `write_s7` 只产生 S7 提案，不直接写业务 |
| `SKILL.md` body / policy prompt | `skill.prompt_hash` | 记录策略提示 hash，避免目录后续变更影响既有 Run |

## 实施约束

- 禁止新增 Pico 公共 `/v1/skills` 浏览目录或第二套技能商店 UI。
- 可新增 deployment skills 到 `apps/librechat/skill/**`，因为它们进入同一个 LibreChat Skills 目录。
- Pico 只做执行侧受控快照、工具交集和 S7 触发；快照可放在 Run 既有审计 JSON 中，避免破坏性迁移。
- 后续若扩展 metadata，仍以 LC skill id/name 附着，不形成可浏览的第二目录。

## 修订

| 日期 | 变更 |
|------|------|
| 2026-07-30 | 初版 PROPOSED |
| 2026-07-30 | N2 只读调查完成，ACCEPTED A |
