# 交接 · Pico 总管新窗（2026-08-23）

```text
STATUS: BINDING 交接 · 接替本窗 · #573 作废
DATE: 2026-08-23
入口: https://github.com/juanwan99/pico/issues/634
仓: juanwan99/pico ONLY · 禁止 edu-core 混线
公网: https://pico.aivia.asia
生产: SSH pico-prod / ecs · /opt/pico
现网 tip（写窗 curl）: b713464ca05cb54fc2c30309cf05dc8f3710a825
origin/main（写窗）: ff2c6bca407d8be8549bd43c761d77885cfb2d1c（只多文档 #632/#633，故意不部）
CLAIM-WB-DEGREE-WEB: NO · 工程禁止代签
```

你接的是 **[juanwan99/pico](https://github.com/juanwan99/pico) 总管**：调查、跟业主对齐、派四行卡、核 SHA、放行合/装。默认不写业务码。执行丢给无记忆窗。

**不管 edu-core。** 不派、不改、不赶那个仓的卡。

> **宏观目标错了 = 整窗作废。**  
> 先读本文 → [DIRECTION-NOW](./DIRECTION-NOW.md) → [ONEFLOW](./ONEFLOW.md) → [STATE-NOW](./STATE-NOW.md) → [LAW](./LAW-NO-SELF-BUILD-THIN-ADAPTER.md) → 活动 Issue。

---

## 0. 三句话

1. **做谁：** 公网 AI 工作台 **Pico**（LibreChat + 账本 + **真 Pi 薄桥** + **DeepSeek**），对标 **WorkBuddy 级能办事**。
2. **做到哪：** 阶段 1.5「AI 本体 + 知识库」两包未开；#623 已合已部，差业主侧人路径复验；**CLAIM-WB 未签**。
3. **怎么干：** 单窗 SOLO · 先测/RCA 再修 · OneFlow v2 四行卡 · DS 主执行 · 总管 L2 · 禁自签 PASS · 禁 315。

---

## 1. 整个项目在干什么

给老师用的两套东西：

- **edu-core**（别人负责）：学校业务网站。班课、表格、填报。
- **Pico**（你负责）：AI 工作台。长对话、改文档、出文件。核是 **真 Pi + DeepSeek**，禁止自研 Agent 内核。

老师怎么用：侧栏帮填教务网页（偏文本）；要生成 Word/PPT/图，进 Pico 工作台。侧栏不要挂工作区重工具。

北极星：网上用起来接近 WorkBuddy 那种程度（对话稳、长任务跑完、文件找得到）。**只有业主能签** `CLAIM-WB-DEGREE-WEB`。工程禁止代签。

锁定句：

```text
目标：Web 上 WorkBuddy 程度（六条硬标准）
方案：Pico 整车 + 默认编排核 Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验）
不做：Dify 门脸 · 场景卷对标 · 双核并列真源
本阶段（DIRECTION-NOW）：不铺 连接器 / MCP / Skill 市场
```

法律：`docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md` — 禁止自研核 / 厚桥 / 第二编排真源。只允许薄适配。

```text
门脸 LibreChat → 控制面/账本 Pico API → 编排 true_pi 默认 → 模型 DeepSeek
回滚: 仅 PICO_HOSTED_LOOP=1 → hosted pi_runtime
钉版: @mariozechner/pi-coding-agent@0.73.1
```

---

## 2. 这个仓库在干什么

Pico = AI **过程**真源（会话、工具、产物、双档）。不是第二套教务系统。Agent 不直写成绩库。

公网：https://pico.aivia.asia  
机器：ECS `/opt/pico`（`ssh ecs` / `pico-prod`）。发布：`PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh`  
生产只认：`curl -fsS https://pico.aivia.asia/api/pico/tip`

[#573](https://github.com/juanwan99/pico/issues/573) 是 8-15 旧交接（还在说 315、#572/#570），**作废，不要当现况。** 现行入口：[Issue #634](https://github.com/juanwan99/pico/issues/634)。

---

## 3. 你当总管要守的

- 一张结果一张卡。残债同卡续，禁 `T-*-DEBT`。
- 卡面四行：结果 / 不准 / 过门 / 部署。模板在 `main`，不是某张开着的 PR：`.github/ISSUE_TEMPLATE/execute.yml`、`docs/templates/card-build.md`、`docs/TASK-CARD-STANDARD.md`（#632+#633 已合）。
- 经验、工具写在手册，卡顶只写「开工先读」：`ONEFLOW.md` · `MEMORY-RESET.md` · `TOOLING-CATALOG.md`。
- 无 `stamp-ok` 拒领。写入不自签 PASS。CI 红不合。合了没装 = 老师没看见。
- 不信回执里的 SHA，自己 curl tip。

---

## 4. 现在实际状态（2026-08-23 写窗 curl）

| | |
|--|--|
| 现网 tip | `b713464ca05cb54fc2c30309cf05dc8f3710a825`（#629 SSO 聊天 403 那刀） |
| origin/main | `ff2c6bca407d8be8549bd43c761d77885cfb2d1c`（只多文档 #632/#633，**故意不部**） |
| 老师侧 | 学校登录能聊、PDF 能开、能生成 HTML（**执行回执**；总管未亲自登录复点） |

刚收口：#623 产物/登录（已关）；#615 多轮对话；#613 跑时人话；#631 任务卡瘦身（已关 · #632+#633 已合）。

**下一张：** [#627](https://github.com/juanwan99/pico/issues/627) 给 CI 装前端 jest。现无 `stamp-ok`，业主点头再打再派。（#627 上「下一张是 #631」旧注已过期 — #631 已关。）

**再下一张：** [#628](https://github.com/juanwan99/pico/issues/628) 材料检索上 Meili。必须 627 关了再开。**写窗已摘掉误挂的 `stamp-ok`。**

出图（P4）HOLD。不要把旧规划 #530/#505/#498/#316 当本周执行。

卡序（DIRECTION-NOW §0b）：`T-CI-UI-GATE` → A1 → A2 → B1 → A3 → B2 → B3。SOLO 一张在飞。

```text
主线唯一: 等业主点头 → #627 → #628
并行勿抢: CLAIM 只等业主 · HOLD 不动
禁卫生大扫除
```

---

## 5. 新窗第一件事（复制执行）

```text
1) curl -fsS https://pico.aivia.asia/api/pico/tip
2) 读 docs/ONEFLOW.md、本交接、docs/DIRECTION-NOW.md、docs/STATE-NOW.md
3) 对业主只报：现网 b713464…；下一张是不是 627
4) 确认 #628 已无 stamp-ok（写窗已摘；若还在就再摘）
5) 不写业务代码，除非业主点头给 #627 打 stamp-ok
6) #623 不开第四波，除非业主侧人路径复验失败
7) Ready 不暗示 CLAIM-WB-DEGREE-WEB: YES
8) 勿卫生大扫除、勿动 HOLD（#170）
```

`CLAIM-WB-DEGREE-WEB: NO`

---

## 6. 角色

| 角色 | 职责 |
|------|------|
| 业主 | 方向 · CLAIM-WB · HOLD 授权 · 给 #627 打 stamp-ok |
| 总管 Grok | 出卡 · L2 核 SHA · 禁自签产品 PASS |
| DS | 主执行 · L1 自审 · 边测边修 |

---

## 7. 一句话交给新窗

```text
Pico = 真 Pi + DeepSeek；CLAIM-WB 未签。
下一张工程主线 = #627 给 CI 装前端 jest 门（无章，业主点头再派）。
#628 误章已摘，须 627 关卡。#623 已部差人眼。
禁自研厚桥 · 禁 edu 混线 · 禁代签 · 禁 315 · 禁无章开工。
```

---

**冲突时：Issue 正文 + 最新 tip 实查 + DIRECTION-NOW / 本交接 / TRUTH-FREEZE / LAW > 聊天摘要。**
