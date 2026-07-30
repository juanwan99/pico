# Pico 3 日加速冲刺（底座收口）

```
DOC: docs/SPRINT-3DAY-PUSH.md
STATUS: BINDING 执行计划（导航）
DATE: 2026-07-30
REPO: juanwan99/pico ONLY
LAW: docs/MVP-3DAY.md v1.2 FIXED（不升 v1.3）
OS: docs/ONEFLOW.md
NAV: docs/MASTER-PLAN.md
HORIZON: 3 calendar days · 每晚 Codex ≈6h 长任务
```

## 0. 「做完」定义（3 天验收，不掺水）

```text
☑ M2 续 T1–T3（流式中断 / finalize 幂等 / Artifact 下载）在 main
☑ 生产 health.git_sha == main tip + ## DEPLOYED
☑ M2 收口：S7 最小真闭环（提案→确认/拒绝→审计，UI 同 change id）
☑ 隔离/自测含：中断终态、下载跨人拒绝、S7 confirm/reject
☑ M3 桩：JWT 同形开关、PICO_EDU_MODE fake|live 边界、change-handoff 形状（fake 默认；真联调后置）
☑ OneFlow：CANDIDATE → CI 绿 → 合 main → 部署回写
☑ 不写 edu · 不像素战役 · 不自 PASS 产品终局
```

**明确不在 3 天内：** edu 真联调（M5）、GHCR 阶段 B、像素 100%。

---

## 1. 角色

| 谁 | 职责 |
|----|------|
| 业主 | 早晚拍板；红例外；可选公网一眼 |
| 总管（Grok/网页 Codex） | 切窗、审查、出 6h 提示词、门禁后合 main |
| Codex（工程/VPS） | 主执行；白天短刀 + **每晚 ≈6h 连续交付** |

---

## 2. 三天日历

### D1 — Git 真相 + S7 起势

| 时段 | 动作 |
|------|------|
| 日间 ≤2h | 功能分支 **merge/rebase main** → PR → CI → **合 main** → 生产对齐 main + DEPLOYED |
| 日间 | 冒烟：登录/聊/产物/下载 |
| **晚 ≈6h** | **S7 最小闭环**实现+测+上线+CANDIDATE/DEPLOYED |

**D1 出门：** main 含 T1–T3；生产=main；S7 至少 CANDIDATE 或已部署。

### D2 — S7 收口 + 防回归 + M3 半壁

| 时段 | 动作 |
|------|------|
| 日间 | 审 D1 夜 tip；CI 红先修；合 PR；DEPLOYED |
| 日间 | selftest：中断终态、下载 200、S7 确认/拒绝 |
| **晚 ≈6h** | **M3 桩**（JWT/模式/change 形状/测/部署） |

**D2 出门：** S7 生产可点；自测加长；M3 大半落地。

### D3 — 桩收口 + 冻结验收

| 时段 | 动作 |
|------|------|
| 日间 | M3 合 main + 生产；全量 pytest + agent-selftest |
| 日间 | 端口/HTTPS/演示一条龙证据 |
| **晚 ≈6h** | **只修 P0 + 验收包**；禁止新需求；更新本文件/MASTER 现状 |

**D3 出门：** §0 清单全 Y；main=生产；书面「底座阶段完成（非 edu 联调）」。

---

## 3. 加速约束

1. **单分支**：从 main 前进；禁止再与 main 长期分叉。  
2. **CI 红禁止合**；push 后编码与 CI 重叠。  
3. **审查薄而频**：长跑结束后一刀 PASS/REVISE。  
4. **砍范围**：S7 最小闭环；M3 只桩不真连 edu。  
5. **每晚结束**必须：`health.git_sha` + 报告模板。

---

## 4. 第 3 天验收表

| # | 项 | Y/N |
|---|-----|-----|
| 1 | main tip == 生产 health.git_sha | Y |
| 2 | 登录 / 真聊 / 产物 / 下载打开 | Y |
| 3 | 流式中断 Run 终态有测 | Y |
| 4 | finalize 幂等有测 | Y |
| 5 | Artifact content 跨人 404 | Y |
| 6 | S7 确认+拒绝 UI+API | Y |
| 7 | M3 桩配置+测（fake 可） | Y |
| 8 | 端口 loopback；443 200 | Y |
| 9 | 未写 edu；未伪 PASS | Y |

---

## 5. D1 夜 Codex 6h 提示词（可直接复制）

见对话归档；权威副本：

**文件内嵌任务卡 → `docs/SPRINT-3DAY-PUSH-CODEX-D1.md`**

（若该文件存在则以其为准；总管可按日更新 D2/D3 卡。）

---

## 6. 风险

| 风险 | 缓解 |
|------|------|
| 分支与 main 分叉 | D1 白天必须先 Git 闭环 |
| CI 红空转 | 插队修；不攒批 |
| S7 与壳不同步 | 最小 UI；同 change id |
| 范围膨胀 | D3 禁新需求 |

---

## 7. 维护

- 每日结束在本文件底部追加一行：`DATE · main SHA · prod SHA · 出门 Y/N · 阻塞`  
- 不另起浪潮交接文；GitHub PR 为事实源。

### 进度日志

| 日期 | main SHA | prod SHA | 出门 | 注 |
|------|----------|----------|------|-----|
| 2026-07-30 | （计划落盘） | b736c6a 一带（M2 续，可能尚未=main） | 计划已 BINDING | 执行从 D1 Git 闭环开始 |
| 2026-07-30 | 3b1bef8506ecefefa25bf948e2d4af4eb6527675 | 3b1bef8506ecefefa25bf948e2d4af4eb6527675 | Y | D3 全量回归与生产十项验收完成；底座阶段收口，M5 后置 |
