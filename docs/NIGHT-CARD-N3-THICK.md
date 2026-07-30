# 夜卡 N3-THICK · 合流 + 二三级 + 加厚包 · 目标填满 4～6h+

```
CARD: docs/NIGHT-CARD-N3-THICK.md
POLICY: docs/NIGHT-CARD-POLICY.md
PLAN: docs/PARALLEL-SPRINT-PLAN.md
BASE: main ≈ 972c426（N2 后）
DEPLOY: YES 夜末
RISK: medium — 大面积 UI + 矩阵 + 可选 CI e2e；不写 edu-cloud
```

## 给 Codex（整段执行 · 禁止 1h 内「没事做了」停）

```text
# Codex 加厚夜卡 N3-THICK · 目标 4～6h+ 有效产出

## 依据
- docs/NIGHT-CARD-N3-THICK.md
- docs/NIGHT-CARD-POLICY.md（最短工时 / 强制加厚包）
- docs/PARALLEL-SPRINT-PLAN.md N3 语义
- docs/ONEFLOW.md · docs/README.md
- 已完成：N1 主路径 · N2 Skill ADR-A + 三技能（972c426 一带）

## 硬规则 HARD
- 仅 juanwan99/pico · **禁止写 edu-cloud**
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key
- 不自 PASS 终局 · 不升 v1.3 · 不宣称像素 100%
- 证据只在 GitHub PR；禁止新 HANDOFF.md
- 默认 edu_mode=fake；不真连 edu
- 演示 teacher@example.com / pico-demo-123 · https://pico.aivia.asia
- **停工条件**：下列「强制包」全部 完成或 书面 BLOCKED+原因，且有效工作建议 ≥3h；禁止主路径已绿就收工

## RISK（本卡允许）
- 改大量 LibreChat 客户端路由/空态/二三级页
- 扩矩阵到「全站路由覆盖率」取向 100%（实现可 NO_REF/backlog）
- 给主路径加 Playwright 冒烟脚本并尽量挂 CI（允许 flake 时先 allowlist 但须说明）
- 小幅 api 整理（不破坏 skill 快照/S7）

## 使命 = 主目标 + 强制加厚包

### 主目标 M（N3 合流）
1. merge/rebase 最新 main；共享文件单写合流（CapabilityHub / ChatView / api.ts / banner 若冲突）
2. 二三级入口：助理/项目/能力中心/自动化/更多/空间 及常见详情/创建 — **无 404、白屏、纯假按钮**
3. 空态/加载/错误态可截图；刷新不闪黑回归
4. 更新 WORKBUDDY-SCREEN-MATRIX 覆盖率（全站路由表尽量 100% 有行；实现率主路径 100%，其余 backlog/NO_REF）
5. 回归：登录/真聊/产物/下载/S7/三技能 snapshot
6. 合 main + 夜末部署 + DEPLOYED

### 强制加厚包（必须做完或 BLOCKED）
**P1 能力中心 × Skill**
- 能力中心/Skills 入口能稳定选到 skill-chat / skill-read / skill-write-s7
- 无「点了没进 Pico 快照」；补 UI 或 payload 直至生产或本地可证
- 截图或 API 证据进 PR

**P2 矩阵诚实扩张**
- SCREEN + INTERACTION 矩阵：一级入口全覆盖；二级尽量全列
- 每行：路由、状态、截图路径或 NO_REF、完成度
- Q 式截图可自己拍；**你负责回填矩阵正文**（本卡你是合流人）

**P3 自动化防回归**
- 新增或扩展 scripts/ 或 tests：主路径或 skill 选择至少 1 条可重复脚本
- 能进 CI 则进；不能则 `scripts/` + README 一行如何跑
- selftest 不回退

**P4 体验债清扫（选够 3 项以上落地）**
从下列点餐，**至少完成 3 项**（多做加分）：
- a. 移动 390 主路径+项目任务无横滚、主按钮可点
- b. 项目列表/创建/详情空态与错误文案中文一致
- c. 自动化页：去掉假「运行」或接到真实最小行为/明确 disabled+说明
- d. 文件库：下载/打开与权限错误可见
- e. 侧栏折叠/展开不丢当前任务
- f. 暗色模式主路径无不可读对比（若已有 dark）
- g. 结果区执行中骨架屏/spinner 统一
- h. 登录失败/过期 token 提示不白屏

**P5（可选高收益 · 有余力必做）**
- Skill 预设 +2～3 个（仍目录 A、求交白名单、高风险 S7）
- 或：agent-selftest 增加 skill-read / write_s7 步骤（生产可跑）

## 时间盒（建议填满）
H0–H0.5  fetch main；枝 grok/pico-n3-thick；列 LEASES 与 RISK
H0.5–H2  二三级点通 + 修 404/假按钮/闪黑
H2–H3.5  P1 Skill 入口打通 + 回归三技能
H3.5–H4.5 矩阵全站覆盖率 + 截图
H4.5–H5.5 P3 脚本/CI + P4 点餐 ≥3
H5.5–H6+ PR（可多个）· CI · 合 · 生产 rebuild 所需 · 全量冒烟 · DEPLOYED
若提前：继续 P4 剩余项与 P5，**不要空停**

## LEASES
- 本卡 = 合流单写：可动 ChatView、CapabilityHub、ChangeConfirmBanner、Workbench/**、data-provider、style 全局
- orchestrator skill_policy 可扩预设；勿拆掉求交
- 禁止 edu-cloud

## 验收清单
- [ ] 二三级无阻断 404/白屏/假按钮（主入口）
- [ ] 矩阵覆盖率显著提升（一级 100% 有行）
- [ ] P1 三技能可选且 snapshot 仍 Y
- [ ] P3 有可重复脚本
- [ ] P4 ≥3 项有 PR 证据
- [ ] main=prod · SELFTEST_OK · 端口
- [ ] PR 含 RISK: 与加厚包结果表

## 结束报告（贴 PR + 聊天）
```
## N3-THICK 结果
- hours used:（须如实；建议 ≥3）
- main SHA:
- PRs:
- M 合流/二三级:
- P1 Skill UI:
- P2 矩阵覆盖:
- P3 脚本/CI:
- P4 完成项 (a–h):
- P5:
- production health:
- smoke: login/chat/artifact/S7/skills/ports
- RISK notes / rollback:
- blockers:
- 声明: 未写 edu · 未第二目录 · 未自 PASS · 未像素100%
```

立即开始。未完成强制包前禁止收工。
```

## 储备（本卡仍提前耗尽时 · 继续加码）

| ID | 内容 | 风险 |
|----|------|------|
| R-A | Playwright 全主路径 1280+390 套件 + CI | med |
| R-B | Skill 到 10 个 + 能力中心文案/分组 | med |
| R-C | openai_compat 拆模块 + 单测补强 | med |
| R-D | 生产 compose/健康检查脚本硬化 | low |
| R-E | M5 runbook 写到可执行（仍不真连） | low |
| R-F | **禁止**除非业主另授：staging edu 只读真连 | high · 另卡 |

默认下一张正式卡仍跟 PARALLEL：N4 扩充或授权 M5；本卡用 R-A..E 填满时间。
