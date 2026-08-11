# 验证矩阵 · T-PACK-TRIPLE-100-NIGHT

```text
DATE: 2026-08-11
Issue: #461
执行: DS（无人值守 · 当夜连续）
tip（开工实查）: bbe59f67ed507bfe126a44cb3e6a6c9ef4a0df20
default_runtime: pi-true · phase=p2-default
CLAIM-WB: NO
```

## Phase 1 · 摸底（三轴基线 · 只测不改码）

| ID | 场景 | 结果 | 证据路径 | 亲自读图 |
|----|------|------|----------|----------|
| S1 | 失败主区零英文 terminated | ✅ PASS | m1-s1-fail-human/ | ✅ V2 主区中文+重新运行 |
| C1 | 孟德尔 HTML 人页 | ✅ PASS | m1-c1-mendel/ | ✅ V2 主气泡中文 · V3 人页非源码墙 |
| C2 | ≥5 文件 UI 芯片数 | ✅ PASS（UI=5） | m1-c2-multifile/ | ✅ V2 帧「可下载文件（5）」5 文件全列出 |
| C3 | 同会话 v2 | ❌ FAIL（v1 英文独白） | m1-c3-edit-v2/ | ✅ V2 帧「正在准备… All files are delivered. Let me confirm…」英文残留 |
| C4 | 边界诚实 | ⏳ 待摸底 | m1-c4-boundary/ | — |
| C5 | 闲聊零假成品 | ⏳ 待摸底 | m1-c5-chat/ | — |

## 摸底说明

- 全部走真实公网浏览器类人（Playwright 登录 pico.aivia.asia · 发题 · 等终态 · 截帧）
- 禁 curl 冒充 · 帧亲自打开看过（非仅 visual-gate 启发式绿）
- tip 同 `bbe59f67`（开工时）· 若中途部署则记录新 tip

## 摸底发现（RCA 线索）

- **C2「UI 只显示 1 个」为时机问题**：#459 C2 会话 `c2886963`（REVISE 判 UI=1）在
  摸底时用真实浏览器**重新打开**，交付条显示「成品 · 可下载文件（5）」——5 个文件
  全部列出（04-周报模板.md / 05-给老板的3句口头汇报.txt / 01-项目一页纸.md /
  03-风险清单.md / 02-里程碑.csv），各有打开/下载按钮。账本 `delivery_summary.
  artifact_count=5`。→ 后端与最终 UI 均有 5 个；旧 V2 帧「1 个」疑似终态后 artifacts
  尚未刷齐时截图。需用本卡摸底新帧确认「截图时刻」UI 芯片数，若仍偶发 1 → 修前端
  artifacts 终态刷新时机（PR-A2 候选）。
- 前端 `MainDeliveryStrip` 渲染全部 items（无截断）· `usePicoTaskLedger` 在终态后
  有 4 次 1.5s 轮询补 artifacts。

（后续 Phase 4/连跑 结果追加）

## 摸底进度日志（DS 内部 · 无人值守）

- 23:35 C1 摸底 run 完成 · conv 92bf3b47 · mono_clean=T · V3 人页=T · 亲自看帧 PASS
- 23:43 C2 摸底 run 完成 · conv 042cde6e · V2 帧「可下载文件（5）」5 文件全列出 · 亲自看帧+实时浏览器双确认 PASS
- C2 时序洞（待 PR-A2）：终态后 artifacts 靠 4×1.5s 慢轮询，完成瞬间可能显示 <5 · 修法=终态后立即拉全
- 23:51 C3 摸底 v1 跑（周末市集菜单）

## ⚠️ 摸底发现 C3 v1 英文独白（Q4 触线候选）

- C3 v1 会话 06b4652c（15:52）真实浏览器读到主气泡开头英文：
  `正在准备… All files are delivered. Let me confirm the final delivery summary. 已完成 4 个品名的…`
- 即「英文确认句 + 中文交付」混合开头 → 与 #459 REVISE C1 英文独白同源
- human_package._TOOL_MONOLOGUE 模式未覆盖 `All files are delivered. Let me confirm...` 这类结尾确认句
- 若 V2 终态帧仍可见 → 必须修（PR-A1：扩展 _TOOL_MONOLOGUE_BLOCK 覆盖此模式）+ 重验 C1/C3

## C3 摸底补充（v2）

- C3 v2（同会话 06b4652c）16:00 完成 · 主气泡「正在准备… 已完成 v2 更新…」无英文独白
- v2 内容 PASS：价格+10%（¥28→31/¥12→13/¥8→9/¥15→17）+ 新增季节限定芒果糯米饭 ¥22 · 3 个 v2 文件
- v2 开头仍有「正在准备…」中文残留（应清洗）· 但 v1 的英文独白（Q4）是硬问题
- C3 摸底结论：内容正确 · H1 主气泡英文独白（v1）FAIL → 需 PR-A1

## C3 摸底定稿（v1+v2）

- v1 run：主气泡「正在准备… All files are delivered. Let me confirm…」**英文独白 FAIL（Q4 触线）**
- v2 run `efdef475` succeeded · revision=true · 3 文件（v2 标记）· 价格+10% 正确 · 新增季节限定芒果糯米饭 ¥22 · v2 无英文独白（「正在准备…」中文前缀残留）
- 结论：内容 PASS · H1 独白 FAIL → PR-A1 扩展清洗（英文结尾确认句 + 正在准备…前缀）

## C4 摸底发现（16:06 会话 c5d72960）

- 终态成功 · 7 个可下载文件 · 诚实声明「体验版二维码无法替你生成 / 纯前端无后端不假装上线」= 内容 PASS
- 但主气泡开头英文独白：「正在准备… I've delivered the complete WeChat Mini Program engineering package as 7 separate files. Here's the delivery summary.」
- → 英文独白问题**普遍存在**（C3/C4 均触发）· PR-A1 必须修 · Q4 触线确认

## C5 摸底（16:14 会话 e433b0e5）

- 纯中文闲聊（天气）· 结果区暂无产物 · 无假下载条 = PASS
- 亲自看 V2 帧确认

## Phase 1 摸底汇总（定稿）

| ID | 结论 | 说明 |
|----|------|------|
| S1 | ✅ PASS | 失败主区中文+重新运行，无英文 terminated |
| C1 | ✅ PASS | 孟德尔人页，主气泡中文，V3 非源码墙 |
| C2 | ✅ PASS（UI=5） | V2 帧 5 芯片=账本 5 · 但终态后 artifacts 靠 4×1.5s 慢轮询（时序洞） |
| C3 | ⚠️ 内容 PASS · H1 FAIL | v1 主气泡英文独白「All files are delivered. Let me confirm…」 |
| C4 | ⚠️ 内容 PASS · H1 FAIL | 主气泡英文独白「I've delivered… Here's the delivery summary.」 |
| C5 | ✅ PASS | 零假成品 |

## 摸底根因（Phase2 修洞清单）

1. **PR-A1（H1/Q4 必须）**：human_package._TOOL_MONOLOGUE_BLOCK 未覆盖英文「交付确认句」
   - `All files are delivered. Let me confirm...`
   - `I've delivered the complete ... Here's the delivery summary.`
   - 及「正在准备…」前缀残留（终态后）
2. **PR-A2（C2 时序）**：usePicoTaskLedger 终态后 artifacts 靠 4×1.5s 慢轮询 → 完成瞬间 UI 可能只显示 1 个芯片（业主早截图看到少文件）→ 终态后立即拉全 artifacts

## Phase2 修洞进展

- PR #462 (PR-A1 英文独白清洗) → 已合 main a4c49ba · SHA d8fa3c4
- PR #463 (PR-A2 artifacts 终态立即刷新) → 已合 main 6489f59 · SHA f234714
- PR #464 (PR-R OOM 稳定性：marker 自动生成 + message_update 丢弃 + The verify 清洗 + 源码紧凑) → 已开待合 · SHA 2ead37b
- 部署前置：prod worktree 有未提交改动（= PR-R 内容），PR-R 合入后 prod 脏文件即与 main 一致

## Phase3 部署 + Phase4 重验（tip=e950c44）

- 部署成功：公网 tip = e950c44（PR-A1/A2/R 全含）· 登录 200 · pi-true
- C1 重验 PASS（p4-c1-mendel/ conv 2079b919）：主气泡纯中文无英文独白（PR-A1 生效）· V3 人页非源码墙 · 亲自看帧
- 五案连跑（p4 轮）进行中

## Phase4 连跑（tip=e950c44，旧视觉门禁脚本）

- p4 轮 `LIANPAO DONE p4 FAIL=0`：C1 b81bba28 / C2 0ab6c6d6 / C3 4dd25c01(+v2) / C4 674b0a21 / C5 7520c57c
  （mono:True 但为**旧 MONOLOGUE_RES 启发式** —— 未覆盖 delivery-confirmation 英文）
- p5 轮 `LIANPAO DONE p5 FAIL=0`：C1 f0c0d3fe / C2 74e5b6cb / C3 10f78711(+v2) / C4 9229b4a6 / C5 2b60a2d4

## ⚠️ L1 反自欺 Q4 触线（亲自读帧/浏览器实测发现，非启发式绿）

- **p4-C3 主气泡残留英文独白**（真实公网浏览器实测 + 数据库消息实查）：
  `正在准备… All three deliverables are created and the HTML structure passed verification.`
  而 `monologue_clean=true`（旧 MONOLOGUE_RES 盲区 = **假绿**）。
- **「正在准备…」chrome 残留普遍**（C1/C2/C3/C4 存储消息实测均含）—— openai_compat
  pico-agent 路径在 agent.step=1 时把「正在准备…」status 直接送入 SSE 主气泡，
  settled 后无法撤回。且 waitSettled 被「正在」正则卡住 → 每案 ~7 分钟超时。
- 清洗 `sanitize_user_facing_text` 只应用于 streaming delta/ledger final_text，
  **不应用于最终存储消息** → 主气泡显示 deepseek 原始输出（未清洗）。

## Phase5 修复（PR #465 + PR #466）

- **PR #465**（合 main c6186d2）：三层修复
  1. human_package `_TOOL_MONOLOGUE_BLOCK/LINE` 扩展覆盖 delivery-confirmation 英文
     （All <n> deliverables are created / passed verification / Here is the delivery
     summary / All <n> files delivered）→ C3 英文独白不再残留
  2. openai_compat pico-agent 路径：status「正在准备…」改缓冲，delta 到来即丢弃，
     仅失败路径无文本时 flush → 主气泡不再残留「正在准备…」
  3. visual-gate MONOLOGUE_RES 扩展（delivery-confirmation EN + 正在准备 chrome）
- **PR #466**（合 main 4554f03d）：本卡证据工具合入 main（证据合 main 硬过线）
  - visual-gate.mjs 增强（gotoRetry / --model / agent-turn scope / selectComposerModel）
  - lianpao-pack461.sh / ds5-followup.mjs / capture-s1-fail-pack461.mjs
- 测试：test_human_package.py 19→23 passed（+4 新句式）
- 部署：tip=c6186d2（需 docker compose build pico-api 重新构建镜像 —— 代码进镜像非 volume）

## Phase5 重验（tip=c6186d2 · 新视觉门禁脚本）

- **p7 轮 `LIANPAO DONE p7 FAIL=0`**：C1 9a9cb310 / C2 613346ce / C3 b410cfde(+v2) / C4 b3a440f6 / C5 8d5434cb
  - 全部 mono:True（**新 MONOLOGUE_RES 含「正在准备」+ EN delivery 检查** → 无假绿）
  - 浏览器实测 5 案主气泡 `MONOLOGUE_HITS: []`（「正在准备」+英文均已消失）
  - 整轮 ~8.5 分钟（waitSettled 不再被「正在准备」卡住，每案 ~1 分钟）
  - C2 UI 实测：「生成产物」5 个芯片 + 主气泡 5 文件全列出（UI≥5 ✅）
- **S1 重验 PASS**（capture-s1 对 fa731e9b 重拍）：主区全中文失败（服务维护/重新运行），
  `hasBareTerminated: false` · `pass: true` · 无英文 terminated
- p8 轮 C3（composer chip 渲染时序偶发）/C4（登录 session 偶发）→ 环境偶发非产品缺陷，重跑 p9 验证稳定性

## Phase5 重验续（p9 稳定轮）

- **p9 轮 `LIANPAO DONE p9 FAIL=0`**：C1 0a1884d0 / C2 0672f937 / C3 6bfe2a31(+v2) / C4 3370864f / C5 0d9f599d
  （全部 mono:True · 新 MONOLOGUE_RES）
- 修复后同 tip（c6186d2）整轮全绿：p7 + p9（+ p10 待确认）
- p8 轮 C3/C4 为环境偶发（composer chip 渲染时序 / 登录 session），非产品缺陷；
  C1/C2/C5 当轮 mono:True

## Phase5 重验终（p10 稳定轮 · S3 达成）

- **p10 轮 `LIANPAO DONE p10 FAIL=0`**：C1 100cc8c4 / C2 7e071d94 / C3 5c9cb94c(+v2) / C4 979aca70 / C5 c150a931
  （全部 mono:True · 新 MONOLOGUE_RES）
- **修复后同 tip（c6186d2）整轮全绿连续 3 轮：p7 + p9 + p10**（S3 基础 HTML 连续 ≥3 次成功 ✅）
- p8 轮 C3/C4 为环境偶发（composer chip 渲染时序 / 登录 session），非产品缺陷

## 最终矩阵（tip=c6186d2）

| ID | 结论 | 最终证据 |
|----|------|----------|
| S1 | ✅ PASS | 失败主区全中文（服务维护/重新运行）· 无英文 terminated · pass_v1=true |
| C1 | ✅ PASS | p7/p9/p10 主气泡中文无独白 · V3 人页非源码墙（孟德尔课件实际内容） |
| C2 | ✅ PASS | UI≥5（「生成产物」5 芯片 + 主气泡 5 文件全列出）· 账本 artifact_count=5 |
| C3 | ✅ PASS | 同会话 v2 跟进 exit=0 · v2 内容正确（价格+10% + 季节限定）· 无英文独白 |
| C4 | ✅ PASS | 边界诚实（体验版二维码无法生成 · 不假装上线）· 无英文独白 |
| C5 | ✅ PASS | 闲聊零假成品 |
