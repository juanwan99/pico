# 夜卡 N2 · Skill 薄层三类闭环 · ≈6 小时

```
CARD: docs/NIGHT-CARD-N2-SKILL-THIN.md
PLAN: docs/PARALLEL-SPRINT-PLAN.md BINDING-v2
TRACK: S（前 60–90min 只读 ADR）
DEPLOY: 默认否；仅 API 急修可部署；完整生产对齐可放到 N3
AFTER: N1 main 54595fe…
RESERVE: 见文末 §储备
```

## 给 Codex：整段执行

```text
# Codex 夜卡 N2 · 6h · Skill 三类纵向闭环

## 依据
- docs/PARALLEL-SPRINT-PLAN.md §4 · §7.2
- docs/ADR-SKILL-CATALOG.md（PROPOSED → 本卡前段必须 ACCEPTED 或书面改选 B）
- docs/README.md · docs/ONEFLOW.md
- 上窗 N1 已完成（PR #41）；勿重做主路径矩阵大改

## 使命
1) 60–90min 只读结束 ADR：唯一 Skill 产品目录（推荐 A=复用 LibreChat Skills）
2) 仅三条纵向可演示：
   - skill.chat（或 LC 等价 id）— 少/无工具
   - skill.read — 只读工具子集
   - skill.write_s7 — 变更提案 → 现有 S7 横幅
3) Run 写入受控 Skill 快照（id/名/工具子集/risk/prompt hash）
4) 工具 ⊆ 全局白名单求交；禁止扩大白名单
5) 无第二套「技能商店」浏览 UI
6) 测绿 · PR · CI · 合 main；生产部署非必须（报告写明）

## HARD
- 仅 juanwan99/pico · 禁止写 edu-cloud
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key
- 不自 PASS 终局 · 不升 v1.3 · 不全面像素 · 不做 M5 真连
- 一夜主轨 = S；W 矩阵正文勿大改（LEASES）
- 完成证据在 GitHub PR（CANDIDATE）；禁止新 HANDOFF.md
- 演示 teacher@example.com / pico-demo-123 · https://pico.aivia.asia

## LEASES
可写：
- docs/ADR-SKILL-CATALOG.md（调查记录 + STATUS→ACCEPTED）
- docs/skills/** 或 overlays（若 ADR 需要）
- services/api/** skill 快照/校验相关
- services/orchestrator/** 注入 allowed_tools 求交
- packages/contracts/** 若需 skill snapshot schema
- apps/librechat：CapabilityHub / Skills 入口的最小接线；data-provider/pico skill 相关
禁止：
- 大改 Workbench 二三级页、PIXEL 全站、edu_adapter live 默认开
- 新建并行公共 /v1/skills 浏览目录（除非 ADR 明确改选 B 并隐藏 LC Skills）

## 时间盒
### H0–H1.5  ADR 只读 + 结论入库
```bash
git fetch origin && git checkout main && git pull --ff-only
git checkout -B grok/pico-skill-thin origin/main
```
按 ADR N0 清单：定位 LC /api/skills、UI、调用链、metadata 扩展点。
更新 docs/ADR-SKILL-CATALOG.md：调查记录表 + STATUS ACCEPTED + A 或 B。
若无法结论：BLOCKED 停写功能，只 PR ADR 调查。

### H1.5–H3.5  快照 + 三技能接线
- Run/Task 元数据：skill 快照字段
- 三技能定义（chat/read/write_s7）挂唯一目录
- write → 现有 Change/S7（不重造横幅）
- pytest：快照、工具求交、跨 membership 若触及

### H3.5–H5  UI 最小可选 + 浏览器
- 用户能选到三技能之一并开跑
- 账本/API 可查 snapshot
- write_s7 可见 S7 横幅路径

### H5–H6  PR · CI · 合 · 报告
- CANDIDATE + 40 字 SHA
- CI 绿后合 main
- 生产：默认不强制 rebuild；若 api 必部署则 health 对齐并 ## DEPLOYED
- 报告模板见下

## 强制验收
- [ ] ADR ACCEPTED（A 或 B）写在仓内
- [ ] 仅一套产品目录
- [ ] 三技能纵向 Y
- [ ] Run 含 skill 快照
- [ ] write → S7
- [ ] 未扩白名单 · 未写 edu · 未像素战役

## 停止条件
- 三技能 + ADR + PR 合 main → 停
- 或 6h：CANDIDATE 清晰接手；禁止半套无测

## 结束报告
```
## N2 夜 6h 结果
- hours:
- ADR: A/B · SHA of ADR commit
- main SHA after:
- PR / CI / merged:
- three skills demo: chat/read/write_s7
- snapshot evidence:
- S7 path:
- production deployed? Y/N · health:
- LEASES Y/N
- blockers:
- 声明: 无第二目录 · 未写 edu · 未自 PASS
```

立即开始。
```

## 储备夜卡（N2 提前完成或 BLOCKED 时）

| 优先 | 卡 | 何时用 |
|------|-----|--------|
| R1 | **N2 补时**：预设扩到 5–6 个仍同目录 | N2 三技能提前完 |
| R2 | **N3 提前**：共享文件合流 + 二三级诚实空态 | N2 已合且仍有整夜 |
| R3 | **Q 只读**：主路径 390/1440 补截图，PR 评论贴路径，**不改**矩阵正文 | 不宜写代码时 |
| R4 | **N4b 草稿**：组装型 skill（提示词+工具子集）设计-only PR | 无 M5 授权 |
| — | **N4a M5 只读** | **仅业主书面授权后** · 仍禁止写 edu-cloud |

默认下一正式夜：N2 →（完）N3。不跳 N4a。
