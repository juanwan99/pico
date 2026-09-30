# LAW · 禁止自研 · 只做薄适配（BINDING）

```text
DOC: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
STATUS: BINDING · 项目最高法律 · 全体执行窗/总管强制
DATE: 2026-08-11
UPDATED: 2026-09-28 · 业主：高质量长任务第一；放开 A–F（#1090）
OWNER_ORDER: Pico 禁止自研，只做薄适配。禁止自搞一套。禁止做重体系。
OWNER_ORDER_2026-09-28: 第一需求 = 长任务高质量跑完。放开 A–F = 用更多上游 Pi 原生能力，适配层更薄。§0-supreme 不动。
REPO: juanwan99/pico ONLY
CLAIM-WB: NO
```

---

## 0-supreme. 最高要求（压过本文件其余条款、压过一切任务卡便利）

```text
Pico 绝对禁止自己搞一套体系。
绝对禁止做重体系 / 厚桥 / 第二能力核 / 第二编排真源。
只允许对成熟上游做薄适配：接线、白名单、账本、门闩、人包、门脸。
桥变厚 = 违法 = 必须拆。
上游缺口（例如 Pi 无文件口）≠ 许可证去自研补核。
```

本条压过：HANDOFF、TRUTH-FREEZE 其余条、EXPERIENCE 便利、任务卡「先能跑」。

业主 2026-09-28（[#1090](https://github.com/juanwan99/pico/issues/1090)）：第一需求 = 长任务 / 复杂任务高质量跑完。瓶颈 = agent harness。放开 A–F 是接更多上游 Pi 原生能力（内建工具、工作区、官方 compaction、`--session` 续跑），**适配层更薄**，不改本条。

---

## 0. 一句话（背下来）

```text
Pico 禁止自研内核 / 协议栈 / Agent OS / 第二编排真源。
只允许对成熟上游做「薄适配」：接线、白名单、账本、门闩、人包、门脸。
桥一旦变厚 = 违法 = 必须拆或 REVISE。
禁止自搞一套体系。禁止做重体系。
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
5. 公网默认 Host Shell / 宿主任意 bash 当能力卖点（生产机宿主 shell 仍禁。业主 2026-09-28 放开 A：隔离工作区容器内打开上游 Pi 内建 read/write/edit/bash，不算本条；业主 2026-09-30：专用执行机（无钥无库）普通 Docker / 裸机上的 shell 也不算本条）
6. 用自研补丁冒充「已经是上游生态」（名实造假）
7. 复制 edu-core 栈进 Pico 当第二产品
8. **定向工作流冒充用户**：读正文猜任务、force_agent 自动挂交付 Skill、把 skill/Landing requirement/「必须交 N 个文件」焊进 user prompt（北极星 DIRECTION-NOW §0-star v1.4；用法 = Grok）
9. **Pico 自研 PDF 阅读器当能力核**：进模型前用 pypdfium2/RapidOCR/渲页/抽文焊进 user 冒充「已经读了 PDF」。业主 2026-09-28 放开 B：附件进隔离工作区，模型自读、自渲、自检产物；「厚桥四层对检查的禁令」SUPERSEDED。原件走工作区；Pi 无文件口 ≠ 允许自研 PDF 核
10. **办公投影器当能力核**：把 Office 抽成摘录/spec 条目墙再喂模型，或把 spec 投影当天花板。生成走模型 + 隔离工作区成熟办公库；预览门脸不是阅读核。模型在工作区自渲自检 = B，不是本条
11. **交件监工**：min_artifacts / force_agent / 词表自动挂交付 Skill / 把「本轮必须交 N 个文件」焊进 user
12. **硬帽截窗**：用 Pico 自定 reserve/步数/字数把上游窗口截短（例如 256k 窗 64k 就压）。业主 2026-09-28 放开 D：历史交 Pi 会话 + 官方 compaction，撤 Pico 截断。只认上游窗与安全门（租户/SSRF/密钥/禁宿主 shell/假绿）
13. **Pico 自挂公网页冒充发布**：`pico.aivia.asia/p/{id}`、老师点确认、自研发布闸都不是发布能力。发布 = Edu 专用申请 + 校管批准。Pico 只产 HTML。任务卡「发布确认收口」压不过本条。
14. **第二套模型账 / 绕开网关计费**：聊天/出图等要统计计费的调用直连厂牌，或在 Pico/edu 另建点池、余额、第二账单核。现网上游 = New API。Pico 只记用量；钱在 edu 只认 Pico export。本仓不写 edu。
15. **解释器级沙箱当隔离核**（业主 2026-09-08c · #959）：AST 白名单、`__import__` 钩子、builtins 白名单、pathlib/io 桩、猴补 `save` 一类「在 pico-api 进程内限制 Python」冒充隔离。隔离交容器 / 成熟上游（全出网但禁内网/宿主/云元数据、无密钥、tmpfs、rlimit）；Pico 只做合同与门闩（OOXML 合法、空壳门、租户取件、账本写口）。Pico 替模型决定「能不能 import」= 适配层定义行为 = 违法。宿主 shell / 把密钥送进执行容器仍禁。隔离工作区容器内的完整 Python 与上游 Pi 内建 bash **不算**自制 jail。

---

## 3. 硬允许（唯一正道）

| 层 | 允许 |
|----|------|
| 编排 | 嵌入/旁路真 Pi；Pico 持账本与门闩。执行与 pico-api 进程分离；中断用 Pi `--session` 续跑（业主 2026-09-28 C） |
| 工具 | 隔离工作区 / 专用执行机打开上游 Pi 内建 read/write/edit/bash；Pico 侧 gateway 仍白名单（扩名单须 ADR）。禁生产机宿主 shell |
| 模型 | 现成网关 API（现网 **New API**）；禁止为厂牌再造直连核；禁止自研计费 OS |
| 产品 | 门脸适配、人包、假绿防护、租户隔离 |
| 接入 | MCP/KB 以后接现成组件（分期），不自写协议内核 |
| 加载 | 少常驻动词 + Skill 渐进披露；成熟文档 skill 可常驻（业主 2026-09-28 F）。见 [`ADR-CAPABILITY-LOADING.md`](./ADR-CAPABILITY-LOADING.md)。禁自研选工具核 |
| 工作环境 | 成熟上游隔离工作区：整个 Pi 跑在容器里；附件/产物挂载；**全出网**（仍禁内网 / 宿主 / 云元数据）。密钥不进执行机。以后搬专用执行机：普通 Docker 或裸机，不要虚拟沙箱（业主 2026-09-30）；搬机前同机留 gVisor。Pico 只接线、账本、门闩、租户。禁生产机宿主 shell、禁自研沙箱核 / 自制 jail（含进程内受限解释器）。墙钟熔断已撤，只留成本/用量帽（业主 2026-09-28 E） |

---

## 3b. 业主 2026-09-28 放开 A–F（BINDING · #1090）

旧句（「不要 bash」「宿主 Pi 永 `--no-builtin-tools`」「无公网 bash」「禁止跨进程恢复」「Skill 只能收窄」「厚桥四层对检查的禁令」「墙钟熔断」）**SUPERSEDED**。禁止两套说法并存。

| | 放开 | 仍留 |
|--|------|------|
| **A** | 真 Pi 打开内建工具（read/write/edit/bash）；整个 Pi 跑在隔离工作区容器 | 不碰宿主 shell |
| **B** | 附件直接进工作区；模型自读、自渲、自检产物 | Pico 不自研 PDF/办公阅读核；交件监工仍禁 |
| **C** | 执行与 pico-api 进程分离；部署不杀在飞任务；中断用 Pi `--session` 续跑 | 不自研第二套 worker OS / 任务队列核 |
| **D** | 历史交 Pi 会话 + 官方 compaction | 撤 Pico 截断；不自研压缩器 |
| **E** | 撤墙钟熔断 | 只留成本/用量帽 |
| **F** | Skill 可常驻成熟文档 skill；可用真实长任务做验收集 | Skill 不得当权限裁剪器藏已承诺能力 |
| 网络 | 工作区容器 **全出网** | 仍禁内网 / 宿主 / 云元数据地址 |
| 其余 | | 租户隔离 · 密钥不进执行容器 · Pico 唯一账本/计量 · 发布走 edu · 本仓不写 edu · §0-supreme |

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
最高句（禁止自搞一套 / 禁止重体系）
  ≥ 本 LAW 其余条款
  ≥ TRUTH-FREEZE / HANDOFF 架构条
  ≥ AGENTS 文首工作法（人合一 / GitHub 唯一真源 / 工位分开）
  ≥ EXPERIENCE 便利
  ≥ 任务卡「先能跑」
与业主当次书面指令冲突：书面指令 > 本文，但必须改本文或出豁免 Issue
工作法不另起文件。禁止为协作再造第二体系。
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
