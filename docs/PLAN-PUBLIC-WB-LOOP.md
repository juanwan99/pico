# PLAN · PUBLIC-WB-LOOP（BINDING · 业主 2026-08-07 纠偏）

```text
STATUS: BINDING
DATE: 2026-08-07
SUPERSEDES:
  - 「loopback API 绿 = 产品可用」
  - 「工程门 P0–P2 CLOSED = 公网已对标 WorkBuddy」
  - CLAIM-WB-DEGREE-WEB YES 候选在公网 UI 未绿前
ALIGN: docs/HANDOFF-WB-PI.md 六条 + Pico+Pi+DeepSeek
MODE: 单窗 SOLO · 公网入口边测边修 · 边对标
```

## 0. 业主纠偏（人话）

| 旧错 | 新对 |
|------|------|
| 机内 health / JWT API 绿就宣称可用 | **只有公网浏览器入口**能完成任务才算 |
| 先签 CLAIM 再补 UI | **先公网绿 → 再谈 CLAIM** |
| 对标 = 像素 / 桌面 workDir | **对标 = Web 六条行为**（HANDOFF §1） |

```text
成功 = 用户打开 https://pico.aivia.asia
      → 登录 → 自然语言派多种活 → 多步/产物/改/停/找回
      体感达到 WorkBuddy 程度（六条），不是后台绿
```

## 1. 锁定句（不变）

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（测→修→装→再测 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派 · 像素 1:1
```

## 2. 工作法（边测边修边对标）

```text
LOOP:
  1. 公网入口实测（浏览器优先；失败点记 RED）
  2. 定根因（入口/TLS/反代/登录/模型/工具/UI 露出）
  3. 最小修复 PR → CI → exact tip 部署
  4. 同一用例再测；绿则下一条，红则回 2
  5. 每轮对照六条表打勾；缺口进下一刀
禁:
  - 只靠 loopback 写 PASS
  - 假绿 CLAIM
  - 拆多窗磨洋工
```

## 3. 阶段刀序

| 刀 | ID | 出口 |
|----|-----|------|
| **H0** | **T-PUBLIC-ENTRY-HOTFIX** | 公网 `/login` 稳定 200；登录进壳；短聊一轮有回复 |
| **H1** | **T-PUBLIC-SIX-BARS-UI** | 浏览器路径六条各 ≥1 开放域题 PASS（截图/录屏可复核） |
| **H2** | **T-PUBLIC-WB-GAP-POLISH** | 对标差距表：手感/失败人话/产物区/Skill 选用；修阻断项 |
| **H3** | **T-CLAIM-WB-DEGREE-WEB**（重开） | 公网证据包 + 业主 YES（**H0/H1 未绿禁止**） |

P3 自动化 / 真 MCP 协议 / 向量 KB：**H1 绿之前不插队**。

## 4. WorkBuddy 对标尺（本期）

| WB 行为 | Pico 必达 |
|---------|-----------|
| 打开就干活 | 公网登录即用 |
| 随便说任务 | 开放域，不先锁场景卡 |
| 会用工具做完 | Pi 多步 + 可见过程 |
| 交得出文件 | Artifact 可下 |
| 接着改 | 同会话 |
| 找得回 / 能停 | 历史 + cancel |
| 能力可见 | ≥3 Skill 前台 |

**不做：** 桌面 exe、本地 workDir 顶格、像素抄皮、拆闭源。

## 5. 当前已知红（2026-08-07）

| 观测 | 含义 |
|------|------|
| 外网 HTTPS → TLS `Connection reset by peer` | 公网入口不可用或路径性故障 |
| 机内 loopback 曾绿 | **不得**覆盖公网红 |
| #316 取证偏 API | 业主实测否决产品「可用」叙事 |

## 6. 执行窗权限与缺口

| 需要 | 说明 |
|------|------|
| SSH `pico-prod` | remote-health / prod-update / nginx 日志 |
| 演示账号（密码器，不进 Issue） | 浏览器登录测 |
| 公网域名可达 | 业主网络 + 执行网双测 |

无 SSH 时：只做代码/配置 PR + 文档；**不得**宣称公网已修。

## 7. CLAIM 纪律

```text
CLAIM-WB-DEGREE-WEB: NO 直至 H0+H1 公网绿
#316 建议 YES 候选 → 作废至公网 UI 重取证
```

```
════════════════════════════════════════════════════════
BINDING · PUBLIC-WB-LOOP · 2026-08-07
公网入口 = 真验收 · 边测边修边对标六条 · 禁 loopback 假绿
════════════════════════════════════════════════════════
```
