# M2 · 诚实限制（一页）

```text
DOC: docs/CLAIM-MATERIALS-2026-08/02-LIMITS-HONEST.md
DATE: 2026-08-11
终验 tip: 502e1f6fd5d3f5999b43303de91b16de1375f26a
来源: #447 UX-HARDEN · #448 TRUE-PI-FINAL-MATRIX 主管 L2 黄债
CLAIM-WB: NO
```

> 本页必须写清 **不能做什么** 与 **已知黄债**。  
> 藏限制 = 一票否决材料包。

---

## 1. 产品边界（本期明确不做）

| 项 | 说明 |
|----|------|
| **非桌面 workDir** | Pico 是 **Web 登录即用** 工作台，不是 WorkBuddy 桌面 exe / 本机目录顶格 |
| **非微信连接器** | 不做微信/企业 IM 连接器生态；边界题须诚实说明，不得假称已导入开发者工具 |
| **非 Remotion 成片** | 不做视频成片管线当默认能力 |
| **非 MCP / Skill 市场铺开** | DIRECTION-NOW：本阶段只打牢 Agent + UI/UX；MCP/Skill 摊子后置 |
| **非 Host Shell 卖点** | 法律禁止公网默认任意 bash / 任意文件系统当能力卖点 |
| **非 edu-core 混仓** | 教育仅领域之一；禁止复制 edu 栈进 Pico 当第二产品 |

真源：[`docs/HANDOFF-WB-PI.md`](../HANDOFF-WB-PI.md) · [`docs/DIRECTION-NOW.md`](../DIRECTION-NOW.md) · [`docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md`](../LAW-NO-SELF-BUILD-THIN-ADAPTER.md)

---

## 2. 工具白名单有限（薄桥 · 7 工具）

真 Pi 桥注册工具（v0/v1 · 不可随意放大）：

```text
workspace_list_files
workspace_read_file
workspace_write_file
generate_html_document
generate_docx_document
generate_pptx_document
verify_html_document
```

| 允许 | 禁止（桥内） |
|------|----------------|
| 白名单回调 + 账本/门闩/人包 | 自研 agent OS、第二账本、自研 MCP 协议栈 |
| 薄适配上游 Pi | 桥内 delivery_policy 全家桶 / 私有压缩当主能力 |

真源：[`docs/TRUE-PI-BRIDGE-DUTIES.md`](../TRUE-PI-BRIDGE-DUTIES.md)

**含义：** 开放域「办事」在 7 工具 + 人交付通道内已证明可过 W1–W5；**不等于**桌面全工具面或连接器宇宙。

---

## 3. Drain 降伤 ≠ 零中断

| 项 | 值 |
|----|-----|
| 进程内 await inflight | **45s** |
| Docker stop grace | **60s** |
| 失败呈现 | 中文「服务维护或重启…重新运行」· 非常态裸 `owner was lost` |

```text
drain 降低部署中断概率，不是零中断 SLA。
长任务仍可能在 grace 用尽后失败。
禁止宣称「永不失败 / 永不中断」。
```

真源：[`docs/RUN-DRAIN-AND-STOP.md`](../RUN-DRAIN-AND-STOP.md)  
帧：[`docs/evidence/pack-ux-harden/u1-fail-human/`](../evidence/pack-ux-harden/u1-fail-human/) · [`u2-dual-stop/`](../evidence/pack-ux-harden/u2-dual-stop/)

---

## 4. #448 黄债（不挡工程 READY · 必须写入限制）

主管 L2（#448）与 MATRIX 合并清单：

| ID | 内容 | 影响 |
|----|------|------|
| **Y-w4-src** | 边界题主气泡贴了 wxml 等 **源码块**；未假部署，但不够「人页优先」 | 人交付未满分（边界轨仍诚实） |
| **Y-w5-dense** | 多文件题主气泡 **路径 / skill 标识 / 清单偏密** | 交付成功·芯片齐；气泡体验偏工程 |
| **Y-mono** | visual-gate monologue 启发式「系统侧」等 **假阳** | 人读为准 · 机器启发式不单独否决 |
| **Y-summary** | 闲聊侧栏偶发「回复摘要」步骤 | 交付区仍「暂无产物」· 未假成品条 |

帧指针：

| 黄债 | 读图 |
|------|------|
| Y-w4-src | `pack-final-matrix/w4/V2-final.png` |
| Y-w5-dense | `pack-final-matrix/w5/V2-final.png` |
| Y-mono | 多场景 manifest `monologue_clean: false` · 人读主气泡 |
| Y-summary | `pack-final-matrix/human/A3-chat/` · `pack-ux-harden/u5-chat/` |

MATRIX 黄债节：[`docs/evidence/pack-final-matrix/MATRIX.md`](../evidence/pack-final-matrix/MATRIX.md) §黄债

---

## 5. 真核 tip · 回滚开关存在

| 项 | 值 |
|----|-----|
| 终验 / 公网 tip（装订日） | `502e1f6fd5d3f5999b43303de91b16de1375f26a` |
| 默认 multi-step | **pi-true**（`PICO_TRUE_PI_DEFAULT=1`） |
| 事故回滚 | **仅** `PICO_HOSTED_LOOP=1` → 旧 hosted loop（pi-agent） |
| binary | `true_pi_binary_available=true`（见 T0-env） |

```text
hosted loop 回滚开关存在 = 运维保险丝，不是第二产品真源并列。
默认路径仍是真 Pi 薄桥。
```

真源：[`docs/OPS-TRUE-PI-ROLLBACK.md`](../OPS-TRUE-PI-ROLLBACK.md) · `pack-final-matrix/T0-env/health-safe.json`

---

## 6. CLAIM-WB 仅业主

| 角色 | 可否写 `CLAIM-WB: YES` |
|------|------------------------|
| **业主** | 可以（在 `## OWNER DECISION`） |
| 工程 / 主管 / 装订 / CI | **禁止** |

```text
PACKAGE READY · CLAIM-MATERIALS ≠ CLAIM-WB YES
工程只允许: RECOMMENDATION: YES候选 | NO
```

纪律：[`docs/CLAIM-WB-PATH.md`](../CLAIM-WB-PATH.md)

---

## 7. 一句话诚实摘要

```text
Pico Web @ 502e1f6…：开放域派活 / 多步 / 真文件 / 改一版 / HTML 可玩 / 多文件包 / 失败人话
已有帧证明「不弱」于教程级 Web 行为。

仍非：桌面 workDir、连接器、全工具宇宙、零中断 SLA、零黄债人气泡。
CLAIM-WB 必须由业主在限制知情下亲签。
CLAIM-WB: NO
```
