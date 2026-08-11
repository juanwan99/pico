# 交接文档 · 新窗口总管/执行必读（2026-08-11）

```text
STATUS: BINDING 交接 · 接替上一总管窗
DATE: 2026-08-11
仓: juanwan99/pico ONLY · 禁止 edu-core 混线
公网: https://pico.aivia.asia
生产: SSH pico-prod · 文档 IP 139.196.147.40 · /opt/pico
写卷时 tip 抽样: 须 curl 实查 · 抽样曾见 c6186d2dcf5c5ec27a4589112a0cb0ff2cc3409c
CLAIM-WB: NO · 工程禁止代签
卫生: #471 已完成关闭 · 见 docs/HYGIENE-BOARD-2026-08-11.md
```

> **宏观目标错了 = 整窗作废。**  
> 先读本文 → HANDOFF-WB-PI → TRUTH-FREEZE v1.1 → DIRECTION-NOW → LAW → STATE-NOW → 活动 Issue。

---

## 0. 三句话

1. **做谁：** 公网 AI 工作台 **Pico**（LibreChat + 账本 + **真 Pi 薄桥** + **DeepSeek**），对标 **WorkBuddy 级能办事**。  
2. **做到哪：** 阶段一工程多包 READY + CLAIM **材料齐**；**CLAIM-WB 未签**；**双档 fast/deep 真核未通**（当前 P0）。  
3. **怎么干：** 单窗 SOLO · 先测/RCA 再修 · 类人读图 · 薄适配法律 · DS 主执行 · 总管 L2。

---

## 1. 宏观目标（业主锁定 · 勿漂）

### 1.1 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条硬标准）
方案：Pico 整车 + 默认编排核 Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验）
不做：Dify 门脸 · 场景卷对标 · 双核并列真源
本阶段（DIRECTION-NOW）：不铺 连接器 / MCP / Skill 市场
```

### 1.2 六条（HANDOFF-WB-PI）

开放派活 · 能力架可见（本阶段 Skill 不阻塞）· 多步工具 · 真产物 · 任务资产/改一版 · 完成态诚实。

### 1.3 成功与印章

| 层 | 含义 |
|----|------|
| 工程 PACKAGE READY | 大包出口 · **≠** 产品 100% |
| **CLAIM-WB-DEGREE-WEB** | **仅业主** 在材料上签 YES/NO/REVISE |
| 材料根 | `docs/CLAIM-MATERIALS-2026-08/` · 路径见 `CLAIM-WB-PATH.md` · Issue **#449** |

### 1.4 法律

`docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md`：

```text
禁止自研核 / 厚桥 / 第二编排真源
只允许薄适配：接线 · 白名单 7 工具 · 账本 · 门闩 · 人包 · 门脸
真核 = 上游 Pi harness（true_pi）· 不是 Pi-inspired 自写 loop 冒充
```

### 1.5 架构四层

```text
门脸 LibreChat → 控制面/账本 Pico API → 编排 true_pi 默认 → 模型 DeepSeek
回滚: 仅 PICO_HOSTED_LOOP=1 → hosted pi_runtime
钉版: @mariozechner/pi-coding-agent@0.73.1
```

---

## 2. 当前真相（剔除错误记忆）

| 正确 | 错误（禁止再信） |
|------|------------------|
| 默认 multi-step = **pi-true** | 唯一核=Kimi / 禁 Pi |
| DeepSeek 为主 | 默认 Kimi 聊天当产品 |
| CLAIM-WB = **NO** | 工程可代签 YES |
| 只写 pico 仓 | 本窗写 edu-core |
| 卫生 #471 完 | 仍有 60+ 活动卡 |
| 双档 **未 READY** | #469 CI 绿=完成 |
| 冻结 tip 502e1f6 = 材料基线 | 冻结 tip 永远=线上 tip |
| 线上 tip | **curl** `https://pico.aivia.asia/api/pico/tip` |

`DEMO.md` / `CORRECTED-GOALS.md` 已标 **SUPERSEDED**（Kimi 默认句过期）。

---

## 3. 看板（卫生后 · 合法 open）

| Issue | 角色 |
|-------|------|
| **#470** | **P0 执行卡** · 双档 true_pi 按档 thinking/熔断 + 列表两档 + 类人 |
| **#468** | 双档大包父 · L2 **REVISE** |
| **#469** | PR 半成品 · **勿当完成合入** |
| **#449 / #316** | CLAIM 材料 · **等业主** |
| **#170 / #159** | HOLD · 须业主授权（Kimi 切核 / zombie 清库） |

```text
主线唯一: #470 收口 #468/#469
并行勿抢: CLAIM 只等业主 · HOLD 不动
```

---

## 4. 双档问题（P0 · 新窗必懂）

### 业主要

```text
UI 仅两档: Pico 快速(pico-fast) / Pico 深度(pico-deep)
底层: deepseek-v4-flash（有官方 Thinking）
快速 = thinking off · 交件稳
深度 = thinking on + 熔断防空转 OOM
+ 效率/质量可测（PERF 真 tip/run）
```

### #469 已有 / 没有

| 有 | 没有（L2 REVISE 阻断） |
|----|------------------------|
| 策略层 runtime_policy · hosted 熔断 · env 示例两档 | **true_pi/client.py 仍写死 --thinking off** |
| 单测 pi_runtime 路径 | **true_pi 无按档 thinking / 无熔断** |
| PERF 文档样例 | **无类人帧 · 墙钟无 run_id（假绿风险）** |
| list_models 插入两档 | **未强制过滤旧 SKU**（allow 脏则列表脏） |

### 修法指向

```text
true_pi/client.py · true_pi/runtime.py
  --thinking on|off 来自 caps.thinking_on
  --model = deepseek-v4-flash (policy)
list_models 仅输出 pico-fast,pico-deep
部署 env + visual-gate 类人 + PERF 真数据
法律: 不改 Pi 上游包源码
```

L2 原文：#468 comment REVISE · PR #469 同步。

---

## 5. 任务卡形态（业主指定 · 必守）

执行卡外形：

```text
# 执行卡 · T-…
| 字段 | 类型/T-ID/执行窗/审查窗/风险/tip/关联/地图/合入/PASS禁自签 |
## B · 合同
  目标 F*（做什么 + 验收可证伪）· 非目标 · 实测 · DoD · 部署 · 完成定义
## C · 作业提示（tip→实现→证据→PR CI 绿请审）+ 工具表
## D · 回执骨架（CLAIM · PR/tip 表 · 验收表 · 门禁七条 · Ready/REVISE · PASS 未签）
```

仓内：`docs/TASK-CARD-STANDARD.md`（长体例）· 业主短模板以 Issue 为准。  
空壳大纲 ≠ 合格卡。

### 工具（Ready 证据路径）

`docs/TOOLING-CATALOG.md` · `bash scripts/tool-status.sh --json`  

| id | 用途 |
|----|------|
| tip-pin / remote-health | tip 对齐 |
| visual-gate | 类人 V0–V3 · **无图不 Ready** |
| prod-update | 部署 |
| gh-git · pytest | PR/测 |

禁止 Cool/Keel · 密钥进仓 · curl 冒充类人。

---

## 6. 新窗开场清单（复制执行）

```text
1) 读本交接 + HANDOFF-WB-PI + STATE-NOW + #470 正文
2) curl https://pico.aivia.asia/api/pico/tip → 记 40 位
3) bash scripts/tool-status.sh --json
4) 若执行 #470: CLAIM → RCA（true_pi 写死 off 的文件:行）→ 修 → 测 → PR
   可续 #469 分支或新 PR · L2 过后再合部署
5) 类人帧 + PERF 真 run 后再请 PACKAGE READY
6) 任何 Ready 不得暗示 CLAIM-WB YES
7) 勿开卫生大扫除（#471 已完）· 勿动 #170/#159
```

---

## 7. 业主近期设想（未全部冻结 · 勿丢）

| 项 | 状态 |
|----|------|
| 双档 快速/深度 | **进行中 #470** |
| 多模型优势 | 方向 · 先双档 |
| edu 打通 · HTML **临时挂载 URL**（多老师分发） | **仅讨论** · 未派卡 · **勿塞进 #470** |
| 效率第一性优化 | 并进双档卡意图 · 真核未通前不算完成 |

---

## 8. 角色

| 角色 | 职责 |
|------|------|
| 业主 | 方向 · CLAIM-WB · HOLD 授权 |
| 总管 Grok | 出卡 · L2 读码读图 · 禁自签产品 PASS |
| DS | 主执行 · L1 自审 · 边测边修 |

---

## 9. 一句话交给新窗

```text
Pico = 真 Pi + DeepSeek 公网整车，冲 WorkBuddy 能办事；CLAIM-WB 未签。
卫生已清。当前唯一工程主线 = #470 把双档 thinking/熔断打进 true_pi + 列表两档 + 类人真证据。
#469 勿当完成。材料 #449 等业主。禁自研厚桥 · 禁 edu 混线 · 禁代签 CLAIM-WB。
```

---

**冲突时：Issue 正文 + 最新 tip 实查 + HANDOFF/TRUTH-FREEZE/LAW > 聊天摘要。**
