# 快模式冲刺（BINDING · 7 日）

```
DOC: docs/SPRINT-FAST.md
STATUS: BINDING
START: 2026-07-31
END: 2026-08-07（到期自动降级：恢复「黄档须总管合」，除非业主续期）
OWNER: 总管 Grok · 业主拍板采纳 2026-07-31
TRUTH: GitHub only · 无回写 = 未交付
```

## 0. 目的

在 **不改产品路线**（LibreChat 壳 + 薄 Agent + 强模型 + 账本/S7 边界）前提下：

- **降等待**（少空等总管）
- **缩范围**（一周一北星）
- **保留可信**（CI、红档安全、真测、禁假 DEPLOYED）

**不是**取消门禁，而是 **按风险降闸**。

---

## 1. 本周唯一北星（冻结其它）

| 序 | 目标 | 完成定义 |
|----|------|----------|
| **N1** | P0 安全 **生产落地** | main 含 #67；生产 `## DEPLOYED`；`## TEST REPORT` 对 [TEST-TASK-P0-SECURITY](./TEST-TASK-P0-SECURITY.md) **PASS** |
| **N2** | 轨 C 自动化真跑 | [#64](https://github.com/juanwan99/pico/pull/64) 合 main → 部署 → 冒烟「运行一次」有 Run |
| **N3** | 未知 Skill fail-closed | [DAY-TASK-N3](./DAY-TASK-N3-SKILL-FAILCLOSED.md) 合+部署+TEST PASS |

### 本周冻结（禁止插队）

- M5 edu 真连 / 写 edu-cloud  
- 像素 / WorkBuddy 全面对标  
- 新体系长文、夜卡加厚、Skill 扩容战役  
- PG 迁移、队列、outbox、Kimi CLI 大重构、全量 CVE（记 [DEBT-BACKLOG](./DEBT-BACKLOG.md)）

发现新问题：默认进 DEBT-BACKLOG，**除非红安全线上事故**。

---

## 2. 风险门禁（快模式）

| 档 | 例 | 谁合 main | 仍必须 |
|----|-----|-----------|--------|
| **绿** | 文档、测、注释、清单 | **② 执行窗可自合**（CI 绿后） | CI 绿；回写评论 |
| **黄** | 轨 C、小功能、非鉴权 bugfix | **② 可代合**（本周授权） | CI 绿；PR 含验收；`DEBT:` 若有借债 |
| **红** | 鉴权、JWT、生产 env 语义、危险工具、限流模型策略再改 | **① 总管审后合**（或业主点头） | CI + REVIEW + 部署后验证 |

**永久禁止：** CI 红合 main；假 DEPLOYED；PROXY=1；打印密钥；无 TEST 宣称 P0 完成。

### 黄档代合 PR 模板句

```text
RISK: 黄
FAST: SPRINT-FAST 代合授权
DEBT: （无则写 none）
```

---

## 3. SLA（超时 = 事故，须 BLOCKED）

| 事件 | 时限 |
|------|------|
| 合 main 后 → `## DEPLOYED` 或 `## BLOCKED` | **2 小时内**（执行窗） |
| 生产 DEPLOYED 后 → P0/轨 C 相关 `## TEST REPORT` | **4 小时内**（验证窗） |
| 卡住无法推进 | **15 分钟内** `## BLOCKED` + 缺什么 |

总管每日至少扫一次 open PR / BLOCKED（集中窗口，不逐条即时打断）。

---

## 4. 角色（不变，节奏变）

| 窗 | 快模式下 |
|----|----------|
| ① 总管 | 红审；每日收口；不写长计划；BLOCKED 清障 |
| ② ECS 执行 | 写+CI+（绿/黄）合+跳板部署；强制回写 |
| ③ 本地验证 | 短表真测；TEST REPORT；不扩用例 |

---

## 5. 今日起立即动作

### 当前执行焦点

N1/N2 已完成。下一步：**N3** → `docs/DAY-TASK-N3-SKILL-FAILCLOSED.md`


### 【给：③ 验证窗 · 本地】

```text
读 docs/SPRINT-FAST.md。
#67 部署后 4h 内：docs/TEST-TASK-P0-SECURITY.md → ## TEST REPORT 贴 #67
#64 部署后：自动化「运行一次」+ 主路径抽检 → ## TEST REPORT 贴 #64
无报告=未交付。
```

### 【给：① 总管】

- 红 PR 才堵；黄已授权代合  
- 收 N1/N2 双 PASS 后宣布本周北星完成  

---

## 6. 防屎山

- 借债必须 `DEBT:` + [DEBT-BACKLOG](./DEBT-BACKLOG.md) 一行  
- 到期 2026-08-07 黄档代合 **自动收回**，除非业主评论续期  
- 账本 / membership / S7 / allowlist 工具 **不砍**  

---

## 7. 与旧文档关系

- OneFlow / RACI 仍有效；**冲突时本文件在 END 前优先（仅门禁节奏）**  
- TEST-WINDOW、强制回写、DEPLOY-TWO-HOST **不降级**  
