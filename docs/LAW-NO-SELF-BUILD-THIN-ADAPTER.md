# LAW · 禁止自研 · 只做薄适配（BINDING）

```text
DOC: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
STATUS: BINDING · 项目法律 · 全体执行窗/总管强制
DATE: 2026-08-11
OWNER_ORDER: Pico 禁止自研，只做薄适配
REPO: juanwan99/pico ONLY
CLAIM-WB: NO
```

---

## 0. 一句话（背下来）

```text
Pico 禁止自研内核 / 协议栈 / Agent OS / 第二编排真源。
只允许对成熟上游做「薄适配」：接线、白名单、账本、门闩、人包、门脸。
桥一旦变厚 = 违法 = 必须拆或 REVISE。
```

---

## 1. 定义

| 词 | 定义 |
|----|------|
| **自研（禁止）** | 在仓内重新实现可用上游已有的：agent 循环内核、会话/压缩引擎、MCP 协议栈、向量库内核、工作流引擎、第二套工具运行时 |
| **薄适配（允许）** | 进程/RPC/SDK 客户端、工具回调到已有 gateway、事件映射进 Pico 账本、租户/权限/门闩/人包/UI、白名单与失败人话 |
| **真核** | 上游真 Pi harness（RPC/SDK）；不是「Pi-inspired 自写 loop 冒充原版」 |
| **桥** | `true_pi/*` 与 extension 等；职责白名单见 `docs/TRUE-PI-BRIDGE-DUTIES.md` |

---

## 2. 硬禁止（违法）

1. 自研 / 加厚 agent 内核（含把 hosted loop 再发展成完整 OS 当长期主路径）
2. 桥内再造 delivery_policy 全家桶、第二账本、私有会话树、私有压缩当产品主能力
3. 自研 MCP 协议栈 / 自研向量库内核
4. 双核并列真源
5. 公网默认 Host Shell / 任意 bash 当能力卖点
6. 用自研补丁冒充「已经是上游生态」（名实造假）
7. 复制 edu-core 栈进 Pico 当第二产品
8. **定向工作流冒充用户**：读正文猜任务、force_agent 自动挂交付 Skill、把 skill/Landing requirement/「必须交 N 个文件」焊进 user prompt（北极星 DIRECTION-NOW §0-star；用法 = Grok）
9. **本地 PDF 阅读器当能力核**：进模型前用 pypdfium2/RapidOCR/渲页/抽文冒充「已经读了 PDF」。原件走账本；Pi 无文件口 ≠ 允许自研 PDF 核
10. **办公投影器当能力核**：把 Office 抽成摘录/spec 条目墙再喂模型，或把 spec 投影当天花板。生成走模型+沙箱库；预览门脸不是阅读核
11. **交件监工**：min_artifacts / force_agent / 词表自动挂交付 Skill / 把「本轮必须交 N 个文件」焊进 user
12. **硬帽截窗**：用 Pico 自定 reserve/步数/字数把上游窗口截短（例如 256k 窗 64k 就压）。只认上游窗与安全门（租户/SSRF/密钥/禁 bash/假绿）

---

## 3. 硬允许（唯一正道）

| 层 | 允许 |
|----|------|
| 编排 | 嵌入/旁路真 Pi；Pico 持账本与门闩 |
| 工具 | 仅白名单回调现有 gateway（扩名单须 ADR，仍禁 shell） |
| 模型 | DeepSeek 等现成 API |
| 产品 | 门脸适配、人包、假绿防护、租户隔离 |
| 接入 | MCP/KB 以后接现成组件（分期），不自写协议内核 |
| 加载 | 少常驻动词 + Skill 渐进披露；见 [`ADR-CAPABILITY-LOADING.md`](./ADR-CAPABILITY-LOADING.md)。禁自研选工具核 |

---

## 4. 审查红线

PR 出现下列信号 → 默认 REVISE：

- 新增通用 agent loop 与真核并行且无退役计划
- true_pi 职责越过 DUTIES 白名单
- 第二套 Event/Artifact 真源
- 「先自研 compaction/MCP 再换」无业主书面批准

合入必须能回答：*这是薄适配哪一段？上游是谁？上游升级是否只改适配层？*

---

## 5. 冲突优先级

```text
本 LAW ≥ HANDOFF / TRUTH-FREEZE 架构条 ≥ 任务卡便利
与业主当次书面指令冲突：书面指令 > 本文，但必须改本文或出豁免 Issue
```

---

## 6. 违规处理

```text
发现自研加厚 → 停工 → RCA → 拆回薄适配或真核上游
不得用「长测绿了」为自研洗白
不得自签 CLAIM-WB 抵消架构违法
```

```text
════════════════════════════════════
BINDING · NO SELF-BUILD · THIN ADAPTER ONLY
════════════════════════════════════
```
