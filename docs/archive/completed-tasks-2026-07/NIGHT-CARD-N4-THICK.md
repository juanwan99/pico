# 任务卡 N4-THICK · 先收口 N3 债 · 再 Skill/体验加厚

```
CARD: docs/NIGHT-CARD-N4-THICK.md
POLICY: docs/NIGHT-CARD-POLICY.md
BASE: main tip at start (post #46/#47；开跑时 git pull)
PRIOR_REVIEW: N3 条件通过 — 截图路径空心 + 生产 DEPLOYED 未证
DEPLOY: YES（本卡前半必须）
RISK: medium
```

## 给 Codex（新窗 · 整段执行 · 禁止早停）

```text
# Codex 新窗 · N4-THICK（先还 N3 债，再加厚）

## 依据
- docs/NIGHT-CARD-N4-THICK.md（本卡）
- docs/NIGHT-CARD-POLICY.md
- docs/ONEFLOW.md · docs/README.md
- 总管审查：PR #46 代码可留，但 N3 未关门（截图假路径 + 无 DEPLOYED）

## HARD
- 仅 juanwan99/pico · 禁止写 edu-cloud
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key
- 不自 PASS 终局 · 不升 v1.3 · 不宣称像素 100%
- 证据只在 GitHub PR；禁止新 HANDOFF.md
- 生产默认 edu fake · 不真连 edu
- 演示 teacher@example.com / <redacted-demo-password> · https://pico.aivia.asia
- 强制包未完禁止收工；有效产出建议 ≥3h

## 阶段 0（必须先做 · 还 N3 债）— 目标 ≤90min
1. git fetch && checkout main && pull --ff-only；记录 START_SHA
2. 生产 /opt/pico 对齐 main tip：
   - rebuild **librechat**（#46 前端）+ 按需 pico-api
   - curl health → git_sha == main
   - 端口仅 127.0.0.1；HTTPS /login 200
3. 公网冒烟：登录、主路径任务、能力中心选 skill-chat/read/write-s7 预填、S7、下载
4. 矩阵诚实化（二选一，优先 A）：
   A) 补拍并 git add output/playwright/n3-thick/*（矩阵已引用的路径）
   B) 改 docs/WORKBUDDY-SCREEN-MATRIX.md 去掉不存在路径，标 NO_REF/未入库
5. PR 评论或 follow-up PR：`## DEPLOYED` + main SHA + health + smoke 表
6. **未完成阶段 0 不得宣称 N3 关闭，也不得只做文档交差**

## 阶段 1（主加厚 · N4）— 强制包

### Q1 Skill 加深（目录仍 ADR A）
- 预设从 3 扩到 **至少 8**（skill_policy + apps/librechat/skill/*/SKILL.md，无 displayTitle）
- 能力中心列表与策略表同步（可仍快路径；完整目录 LC）
- Hub 文案区分：「演示快路径三/多技能」vs「/skills 完整目录」
- selftest 或 n3_skill_snapshot_smoke 覆盖新 id（至少策略模式）
- write 类必须 requires_s7 / 提案工具

### Q2 体验债再清（P4 剩余 + 新债）≥4 项落地
从下列点餐（N3 已做 a–d 可跳过已验证项，改做新的）：
- e 侧栏折叠不丢任务
- f 暗色主路径可读
- g 结果区执行中骨架统一
- h 登录失败/过期不白屏
- i 能力中心 mobile 390
- j 自动化绑定 skill_id 真进 payload（若仍仅文案则推进一截）
- k assistants 召唤与 skill marker 不互相覆盖丢状态
- l more/files 空态插画或清晰 CTA

### Q3 防回归
- Playwright 或 node 脚本：能力中心 → /c/new 含 Pico-Skill marker（可 headless）
- CI 能挂则挂；不能则 scripts/ + 文档一行
- agent-selftest 保持绿（生产 API_ONLY）

### Q4 文档
- PARALLEL-SPRINT-PLAN 进度日志：N3 债清 + N4 状态
- 矩阵更新新屏证据路径（真实存在）

## 阶段 2（有余力 · 储备加码）
- R-A 主路径 1280+390 全套截图入库
- R-B openai_compat 小拆分 + 单测（行为不变）
- R-C M5 checklist 对照代码勾一批（仍不 live）
- **禁止** R-M5 真连除非业主本窗另授

## 时间盒建议
H0–H1.5  阶段 0 部署+矩阵诚实+DEPLOYED
H1.5–H3.5  Q1 Skill×8
H3.5–H5   Q2 体验 ≥4 + Q3 脚本
H5–H6+    PR/CI/合/再部署/报告；余力进阶段 2

## LEASES
- 可写：CapabilityHub、Landing、Workbench、skill_policy、librechat/skill、scripts、CI、矩阵
- 慎改：run_service/openai 大逻辑（仅 Q 储备时小拆）
- 禁止：edu-cloud

## 验收清单
- [ ] 生产 health == main · ## DEPLOYED
- [ ] 矩阵无「指向不存在文件」的假路径
- [ ] ≥8 skills 策略+deployment 文件一致
- [ ] Q2 ≥4 项有代码+简述证据
- [ ] Q3 有可重复脚本
- [ ] 三技能+S7+下载回归 Y
- [ ] 未写 edu · 未第二目录 · 未自 PASS

## 结束报告（贴 PR）
```
## N4-THICK 结果
- hours used:
- START_SHA / END main SHA:
- 阶段0 DEPLOYED: Y/N · health:
- 矩阵诚实: A补图 / B改表:
- skills count + ids:
- Q2 items:
- Q3 script/CI:
- smoke:
- PRs:
- blockers:
- 声明: 未写 edu · 未自 PASS · 未像素100%
```

立即 git pull main 开始。阶段 0 未完成前不要跳到只写新功能。
```

## 业主派发一句话

> 新窗执行 main 上 docs/NIGHT-CARD-N4-THICK.md 全文。
