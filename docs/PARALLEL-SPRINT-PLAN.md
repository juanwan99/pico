# Pico 并行推进计划（体验主路径 · Skill 薄层 · M5 筹备）

```
DOC: docs/PARALLEL-SPRINT-PLAN.md
STATUS: DRAFT → 待业主拍板 + Codex 审查后升 BINDING
DATE: 2026-07-30
REPO: juanwan99/pico ONLY
LAW: docs/MVP-3DAY.md v1.2 FIXED（无授权不升 v1.3）
OS: docs/ONEFLOW.md
BASE: main tip 于落盘时以 origin/main 为准（冲刺后约 2fecb66+）
PRIOR: docs/SPRINT-3DAY-PUSH.md（底座冲刺已收口）
SYNTHESIS: 吸收 Codex「A 体验 / B edu」+ 总管「Skill L1+L2 薄层」+ 最大并行 + 夜间 6h
```

## 0. 目标与非目标

### 目标（本计划窗口 · 约 7～10 个自然日）

1. **工作台主路径**体验可演示、无假按钮/闪黑/主路径断线（有界 WorkBuddy 对标，非 100% 像素终局）。
2. **Skill L1+L2 薄层**：受控预设目录 + 任务/会话绑定 + Run 记 `skill_id` + 高风险→S7。
3. **M5 筹备闭环**：联调方案 + 接口清单 + staging 检查表；**真连须业主另授**。
4. **证据矩阵**可并行产出；发布候选可随时拉起。

### 非目标

- 用户任意代码 Skill / 技能市场  
- 未授权 edu 真 HTTP / 改 edu-cloud  
- 自动化引擎大扩建、新壳、升 v1.3  
- 宣称 ±2px 全站完成（缺参考图必须标「缺参考」）

### 共用底座（禁止再造）

```text
principal (school_id + membership_id + scopes)
  → Task / Run / Event / Artifact / Change
  → 唯一 AI 账本在 Pico；业务最终态在 edu（联调后）
```

**三合流点（唯一允许的硬汇合）：** `principal` · `Task` · `Change(S7)`  
其余轨尽量不互相锁文件。

---

## 1. 并行轨道（最大化并行）

```text
        ┌───────────── Track W：工作台主路径 / 矩阵 ─────────────┐
        │                                                      │
Owner ──┼───────────── Track S：Skill 薄层 ─────────────────────┼──► 合流演示
        │                                                      │
        └───────────── Track E：M5 方案 /（授权后）先读 ─────────┘
                              │
                    Track Q：验收证据（只读+回归）常开
```

| 轨 | 代号 | 写代码？ | 主产物 | 默认并行 |
|----|------|----------|--------|----------|
| **W** | Workbench 主路径 | 是（LibreChat 偏多） | 矩阵 + 主路径修复 | 与 S/E **文件不重叠则并行** |
| **S** | Skill L1+L2 | 是（api+少量 UI） | schema/预设/绑定/skill_id | 与 W 分区并行 |
| **E** | edu 筹备→联调 | 先文档；授权后 api | 方案+清单；（后）只读工具 | 文档期与 W/S **全并行**；真连单独闸 |
| **Q** | QA / 证据 | 否或极小 fix | 截图矩阵、冒烟、SELFTEST | **始终并行**（不抢写路径） |

### 1.1 路径隔离规则（保证真并行）

| 轨 | 优先写入路径 | 禁止踩 |
|----|--------------|--------|
| W | `apps/librechat/client/**`（壳、路由、空态、主路径） | `services/orchestrator/**` Skill 核、大改 api 合同 |
| S | `packages/contracts/**` 或 `docs/skills/**`、`services/api/**` skill 路由、`services/orchestrator/**` 注入 | 大面积视觉重构 |
| E | `docs/M5-*.md`、`docs/PHASE3*`；（授权后）`edu_adapter.py` live 配置测 | 未授权改 live 默认开 |
| Q | `docs/*MATRIX*`、`docs/PIXEL-DIFF.md`、`screenshots/**`、PR 评论 | 业务逻辑大改 |

**冲突文件（必须串行）：** `run_service.py` 核心 finalize、`auth.py` 大改、`ChangeConfirmBanner` 行为、全局 `openai_compat` 流式主路径。  
→ 由总管指定 **唯一写入窗**；另一轨 `WAIT`。

### 1.2 角色（单 Codex 时的「逻辑并行」）

实际常只有 **一个 Codex 执行器**。并行 =：

1. **夜间 6h** 深挖一轨主交付；  
2. **日间** 另一轨短刀或 Q 证据；  
3. **总管** 审查 + 合 main + 出次日/夜卡；  
4. **业主** 授权 M5、看公网、缺图时补参考。

若未来多执行器：W 与 S 分人；E 文档可第三人；Q 独立。

---

## 2. 日历总览（可并行）

| 日 | 日间（≤3h 有效） | 夜间 6h 长任务 | 可并行 Q |
|----|------------------|----------------|----------|
| **N0** | 计划审查（本文件）· 业主拍板 | — | — |
| **N1** | W：矩阵脚手架 + 闪黑/假按钮速扫 | **W-6h：主路径 P0 收口** | 截图桌面 1280 |
| **N2** | S：schema 草案 PR；E：M5 方案大纲 | **S-6h：Skill L1+L2 可演示** | 移动 390 主路径 |
| **N3** | W/S 合流接线；修 CI | **W-6h：二三级入口诚实 + 空态** | 矩阵填缺口 |
| **N4** | E：接口清单终稿；业主看是否授 M5 | **若已授权：E-6h 只读联调**；**否则 S-6h 加固/用户组装草稿** | 全冒烟 |
| **N5** | 发布候选彩排 | **Q+Fix-6h：三门禁 + 只修 P0** | 证据包 |
| **N6** 缓冲 | 扫尾 / 你验收 | 可选补跑 | — |

**尽量并行：** N1 夜 W 时，日间可写 E 文档；N2 夜 S 时，日间 W 只读测矩阵。  
**不可并行：** 未授权时禁止 E 真连；同文件双写。

---

## 3. Track W — 工作台主路径（有界对标）

### 3.1 先矩阵（1 日量级 · 可与修 bug 重叠）

交付：

- `docs/WORKBUDDY-SCREEN-MATRIX.md`  
- `docs/WORKBUDDY-INTERACTION-MATRIX.md`  
- 更新 `docs/PIXEL-DIFF.md`（主路径优先）

每行：`入口 | 路由 | 参考图有/缺 | Pico 截图 | 像素差 | 交互差 | 状态(空/载/跑/S7/成/败/无权限) | 完成度`

尺寸：1440 / 1280 / 390（主路径必须；其余尽力）。

### 3.2 主路径 P0（优先于「全面三级」）

```text
1 首页发起任务
2 执行中状态
3 右栏产物 / 预览
4 S7 待确认横幅
5 文件打开、下载、历史
6 项目内发起任务并见资产沉淀
```

验收：

- 一/二/三级 **主路径相关** 无 404、白屏、假按钮  
- 刷新不闪黑、不丢当前任务（已知问题优先）  
- 桌面无横滚；移动核心按钮可用  
- 空态/错误/执行态可截图  
- **不** 要求全站 ±2px  

### 3.3 二期（N3 夜 · 不挡 Skill）

列表/详情/创建/配置诚实空态；缺参考标 `NO_REF`。

---

## 4. Track S — Skill 薄层（L1+L2）

### 4.1 合同（最小）

```text
Skill = id + title + description + system_prompt_fragment
      + allowed_tools[]（⊆ 全局白名单）
      + model_pref? + risk(read|write) + requires_s7?
```

- 预设包：仓内 YAML/JSON + schema 校验  
- API：`GET /v1/skills`（启用列表）；任务/会话绑定 skill  
- Run 元数据：`skill_id`（+ 名称快照）  
- `risk=write` 或 `requires_s7` → 变更类必须走现有 Change/S7  
- **禁止** 扩大工具面超过全局白名单  

### 4.2 预设起步（6～10 个）

例：纯聊、写教案提纲、出练习、会议纪要、班级一览(fake 只读)、备注变更提案(S7)、总结产物、翻译润色…  

### 4.3 验收

- 能力中心或任务台可选 Skill  
- 切换后工具/提示有可测差异  
- 账本可查 skill_id  
- 高风险走 S7  
- 无任意代码 Skill  

---

## 5. Track E — M5 筹备与（授权后）先读后写

### 5.1 未授权（默认）

只交付文档：

- `docs/M5-INTEGRATION-RUNBOOK.md`（staging、密钥、开关、回滚）  
- `docs/M5-API-CHECKLIST.md`（JWT claims、只读工具、Change handoff、错误码）  
- 生产保持 `PICO_EDU_MODE=fake`、handoff off  

### 5.2 授权后第一刀（只读）

- edu JWT 验签（关或收紧 test issuer 的 runbook）  
- school/membership/角色映射  
- 过期/跨校拒绝测  
- **两个只读工具** 真数  
- edu 不可用 → **明确降级**，禁止静默假数据  

### 5.3 授权后第二刀（S7 写）

- 仅 Change Proposal → 确认 → edu 原子提交  
- change_id 一致；幂等/超时/冲突  
- Pico 账本 + edu 业务态分离  
- **禁止** 绕过 S7 写成绩/班级等  

### 5.4 嵌工作台（非新壳）

助理 / 项目 / 能力中心 / 任务区 / 右栏 / S7 / 历史 — 只接线，不造 edu 独立站。

---

## 6. Track Q — 验收与证据（常开并行）

| 门禁 | 内容 |
|------|------|
| 视觉 | 主路径矩阵截图 1280+390；缺参考不装完成 |
| 功能 | 登录、真聊、产物、下载、S7、Skill 切换、隔离 |
| 生产 | CI、main=prod、端口、fake/live、SELFTEST |

每夜长任务结束：`## CANDIDATE` + 可选 `## DEPLOYED`。

---

## 7. 夜间 6 小时长任务卡（给 Codex）

> 用法：业主说「跑 Nx 夜」→ 复制对应小节全文 → Codex 连续执行约 6h → 交报告。  
> 日间任务由总管另发短卡；**夜卡默认一条主轨，禁止一夜开三轨写爆。**

### 7.1 通用 HARD（所有夜卡）

```text
- 仅 juanwan99/pico · 不写 edu-cloud（除非夜卡写明且业主已授 M5）
- OneFlow：CANDIDATE → CI 绿 → 合 main（有权）→ 生产对齐 → DEPLOYED
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key
- 不自 PASS 产品终局 · 不升 v1.3
- 生产 /opt/pico · https://pico.aivia.asia · 演示账号沿用
- 6h 结束必须：报告模板 + push；尽量 main=prod
- 冲突路径：先 git pull --rebase/merge main；保留他轨已合入工作
```

### 7.2 夜卡 N1 · Track W 主路径 P0（6h）

```text
# 夜卡 N1 · 6h · Workbench 主路径 P0

使命：主路径 6 步可演示 + 闪黑/假按钮/404 清零（主路径范围）+ 矩阵初版。

H0–H1  对齐 main；建枝 grok/pico-w-mainpath；扫一级入口点通表
H1–H4  修：刷新闪黑、假按钮、主路径断线、右栏/S7/下载回归
H4–H5  写/补 WORKBUDDY-SCREEN-MATRIX 主路径行 + 截图目录
H5–H6  测相关 UI 无构建红；PR；CI；合；生产；冒烟；报告

禁止：全面像素、自动化引擎、Skill 大改、edu 真连。

报告：main SHA / 主路径 1–6 Y/N / 矩阵路径 / 截图 / blockers
```

### 7.3 夜卡 N2 · Track S Skill L1+L2（6h）

```text
# 夜卡 N2 · 6h · Skill 薄层可演示

使命：schema + ≥6 预设 + list/bind API + Run.skill_id + UI 可选 + 高风险 S7。

H0–H1  对齐 main；枝 grok/pico-skill-l1；合同/schema 入库
H1–H3  API + orchestrator 注入 allowed_tools 求交；测
H3–H5  能力中心或任务台接线；浏览器切换 Skill 可察
H5–H6  PR；CI；合；rebuild api（+前端若改）；冒烟含 Skill；报告

禁止：任意代码 Skill、扩大白名单、edu 真连、大视觉改版。

报告：skill 列表 / skill_id 账本证据 / S7 链 / SHA
```

### 7.4 夜卡 N3 · Track W 二三级诚实（6h）

```text
# 夜卡 N3 · 6h · 二三级入口诚实 + 空态

使命：矩阵覆盖二三级；无 404/白屏/纯假按钮；空态/错误态可截图；缺参考标 NO_REF。

禁止：宣称像素完成、新模块概念、edu。

可与已合 Skill 共存；冲突 UI 文件先 merge main。
```

### 7.5 夜卡 N4a · Track E 只读联调（6h · 仅业主授权后）

```text
# 夜卡 N4a · 6h · M5 只读 · 需书面授权

前置：业主确认 staging 与密钥；生产/staging 开关明确。
使命：JWT 真验签路径 + 2 只读工具真数 + 降级明确 + 测；禁止写业务。

未授权：禁止执行本卡；改跑 N4b。
```

### 7.6 夜卡 N4b · Track S 加固（6h · 默认无 M5 授权时）

```text
# 夜卡 N4b · 6h · Skill 加固

使命：预设补到 8–10；隔离测；失败态；可选「组装草稿」仅私有提示词+工具子集（无代码）。
禁止：市场、任意脚本、edu 真连。
```

### 7.7 夜卡 N5 · 三门禁收口（6h）

```text
# 夜卡 N5 · 6h · 发布候选

使命：视觉/功能/生产三门禁全跑；只修 P0；更新矩阵完成度；验收包；main=prod。
禁止：新功能。
```

---

## 8. 日间短任务原则（与夜卡配合）

| 日间适合 | 夜间适合 |
|----------|----------|
| 合 PR、CI 红修、文档大纲、审查响应 | 主路径大修、Skill 整层、联调第一刀 |
| Q 截图补洞、矩阵填表 | 长浏览器回归 |
| 业主演示走查 | 重建镜像 + 全冒烟 |

**并行公式：** `日间(轨X 短) ∥ 夜(轨Y 6h) ∥ Q`，且 **X≠Y 或 X 只读**。

---

## 9. 合流与验收包

### 9.1 中间合流演示（N3 末建议）

- 选 Skill → 跑任务 → 产物 →（若 write）S7 → 矩阵有截图  

### 9.2 计划完成定义（未授 M5）

```text
☑ 主路径 6 步全 Y
☑ 矩阵主路径行齐全（缺参考已标记）
☑ Skill ≥6 预设可切换且 skill_id 入账
☑ M5 方案+清单在 main
☑ main=prod · SELFTEST_OK · 端口安全
☑ 未假称像素 100% · 未未授权真连 edu
```

### 9.3 授 M5 后追加

```text
☑ 2 只读真工具 + 降级测
☑ S7 handoff 真提交（staging）+ change_id 一致
```

---

## 10. 风险与减速带

| 风险 | 减速 |
|------|------|
| 单 Codex 假并行 | 一夜一主轨硬约束 |
| 像素范围膨胀 | P0 主路径优先；NO_REF |
| M5 等 edu | E 文档与 W/S 并行；真连闸 |
| 文件冲突 | §1.1 隔离表 |
| 破坏底座 | 回归必跑 S7/下载/聊天 |

---

## 11. 请 Codex 审查时关注的问题（业主转发）

1. 路径隔离是否够真并行？何处必串行？  
2. 夜卡粒度是否 6h 可完成？建议拆/并？  
3. Skill 与 W 轨 UI 文件冲突如何约定？  
4. M5 授权门是否足够硬？  
5. 是否应升格 BINDING 或改日历？  

审查意见请回写本文件 §12 或 PR 评论。

---

## 12. 审查记录（空）

| 日期 | 审查方 | 结论 | 变更 |
|------|--------|------|------|
| | Codex | PENDING | |
| | 业主 | PENDING | |

---

## 13. 进度日志

| 日期 | 事件 | SHA | 注 |
|------|------|-----|-----|
| 2026-07-30 | 计划草稿落盘 | （本 PR） | 待审查 |
