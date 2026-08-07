# 标准任务卡 · 格式与派卡铁律（Pico · BINDING）

```
DOC: docs/TASK-CARD-STANDARD.md
STATUS: BINDING · 格式真源 · 总管派卡
DATE: 2026-08-06
UPDATED: 2026-08-06 · 整合 edu-core CLAIM/BASE/PRODUCT + Pico 锁定句 + 单窗 SOLO
SOURCE: edu-core docs/TASK-CARD-STANDARD.md 体例 + HANDOFF-WB-PI + STAGE-PACKAGE-MODE
EXAMPLE: docs/DAY-TASK-P0-PI-CUTOVER.md · Issue #310 · T-P0-PI-CUTOVER
SUPERSEDES: docs/templates/DAY-TASK-ISSUE.md 旧多窗分轨体例（该文件改为指针）
```

> **口头摘要 ≠ 任务卡。** 聊天三行不能代替 Issue 正文。  
> **认领：Issue 正文 > 任何聊天摘要。**  
> **本文件 = 任务卡格式唯一真源。** 改格式只改本文件 + 示例卡。

---

## 0. 一句话

```text
Issue 正文包在 ```text 框里：
头字段 + 锁定句 + IN/OUT/验收 + CLAIM/BASE/PRODUCT 认领块 + 回写模板。
执行 = 单窗 SOLO。标题：标准任务卡 · T-<NAME>
```

---

## 1. 唯一合法体例（字段不可缺）

任务卡必须是 **专用 Issue 正文**，标题以 **`标准任务卡 · T-`** 开头，主体用 ` ```text ` 包裹：

```text
════════════════════════════════════
标准任务卡 · T-<NAME>
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：CLEAR | KEEP
角色：执行窗端到端 · 总管仅黄/红合与阶段核真源
RISK: 绿|黄|红
FAST: YES|NO
仓：https://github.com/juanwan99/pico
载体回写：https://github.com/juanwan99/pico/issues/<N>
BASE：  <main tip 40-char · 开跑前 gh 校准>
PRODUCT：<线上 health.git_sha 40-char · 开跑前校准；未知写 UNKNOWN+原因>
关联：PR #… · docs/… · 相关 Issue

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
【真源】
【目标】
【IN】
【OUT】
【验收】
【禁止】
【CLAIM】
【回写模板】
【合入】
════════════════════════════════════
```

### 1.1 字段词典

| 字段 | 含义 | 规则 |
|------|------|------|
| `T-<NAME>` | 卡 ID | 大写短名；全仓唯一；Issue 标题同号 |
| 执行窗 | 谁干 | **默认 SOLO（唯一）**；禁止日常「窗1+2+4」并行编制 |
| 上下文 | CLEAR / KEEP | 新开 CLEAR；续跑 KEEP；见 CONTEXT-POLICY |
| RISK | 绿/黄/红 | 红：鉴权/runtime 切流/密钥语义 → 总管审合 |
| FAST | YES/NO | YES = 一主题一闭环，禁拆五张卡 |
| 载体回写 | Issue URL | **必须**等于本卡 Issue |
| BASE | 开跑代码基线 | `git fetch` 后 `origin/main` **40-char** |
| PRODUCT | 线上 tip | loopback `health.git_sha`；未知 `UNKNOWN`+原因；装后改实值 |
| 锁定句 | 产品钉 | **默认四行**见 §1.2；本阶段卡不得改目标/方案/执行/不做 |
| IN | 只做 | 可勾选步骤；含合/装/验若 SOLO |
| OUT | 严禁 | 比「非目标」更硬 |
| 验收 | 出口 | 可证伪；禁自签产品终局 |
| CLAIM | 认领块 | 见 §2 · **唯一**可复制入口 |

### 1.2 锁定句（默认钉死 · 2026-08-06）

除非业主书面改目标，卡内【锁定句】固定为：

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派
```

---

## 2. CLAIM 块（卡尾必有 · 可复制）

```text
CLAIM T-<NAME>（SOLO）
BASE <40-char-sha>
PRODUCT <40-char-sha|UNKNOWN>
<一句人话目标>
```

### 规则

- `CLAIM` 行：卡 ID + `（SOLO）`（不用「窗口1」当编制，除非考古兼容）
- `BASE` / `PRODUCT`：**full 40-char**；禁止 7 字短 SHA 当真源
- 第四行：一句人话，≤40 字
- 开跑前校准 PRODUCT 后 **改写 Issue 正文 CLAIM 块**
- 正式派发评论可重复贴 CLAIM 块，**不替代**正文

### 示例（T-P0-PI-CUTOVER）

```text
CLAIM T-P0-PI-CUTOVER（SOLO）
BASE 1e06440dcabee4c643454483094541cdfc601182
PRODUCT UNKNOWN
合 #309 装 tip 默认 Pi+DeepSeek 并当场题验收
```

---

## 3. 空白模板（复制填空）

```text
════════════════════════════════════
标准任务卡 · T-<NAME>
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：CLEAR
角色：执行窗端到端 · 总管仅黄/红合与阶段核真源
RISK: 黄
FAST: YES
仓：https://github.com/juanwan99/pico
载体回写：https://github.com/juanwan99/pico/issues/<N>
BASE：  <40-char>
PRODUCT：<40-char|UNKNOWN>
关联：

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（改→合→装→验 同一窗串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
唯一执行窗 SOLO：改→合→装→验→回写本 Issue。

【真源】
HANDOFF-WB-PI → MEMORY-RESET → TRUTH-FREEZE → STATE-NOW → 本卡正文 → GitHub 证据

【目标】
（单一主目标 · 人话出口）

【IN】
A …
B …
C …

【OUT】
- …

【验收】
1. …
2. …
3. 不自签 CLAIM-WB-DEGREE-WEB / 产品终局 PASS

【禁止】
仅 juanwan99/pico · 禁 PROXY=1 · 禁裸露 18765/27017 · 禁打印 key · CI 红不合 · 假绿禁止

【CLAIM】
CLAIM T-<NAME>（SOLO）
BASE <40-char>
PRODUCT <40-char|UNKNOWN>
<一句人话目标>

【回写模板】
## MERGED
SHA:

## DEPLOYED
SHA:
default_runtime:
pi_agent_scope:

## TEST REPORT
verdict: PASS|FAIL
CLAIM-WB-DEGREE-WEB: NO

## BLOCKED
原因:（一行）

【合入】
黄/红：总管审后合 · 执行窗 VERDICT_AUTHORITY: NONE
════════════════════════════════════
```

---

## 4. 禁止当作「任务卡」

| 伪卡 | 为何废 |
|------|--------|
| 聊天表格 / 三行板 / 口令 | 无载体、无 BASE/PRODUCT |
| 只有 CLAIM 无 IN/OUT/验收 | 不可执行 |
| 旧 `TYPE: DAY` 多窗分轨模板当主卡 | 已被本文件 SUPERSEDE |
| 拆窗1+2+4 三张等待卡 | 违反 SOLO / MEMORY-RESET |
| 写在错误 Issue 声称已派发 | 载体错 |

---

## 5. 总管派卡检查清单

```text
[ ] 专用 Issue，标题「标准任务卡 · T-…」
[ ] 正文 = 完整 ```text 框（§1 字段齐全）
[ ] 锁定句四行正确（§1.2）
[ ] CLAIM 块唯一、可复制（§2）
[ ] 载体回写 URL = 该 Issue
[ ] BASE / PRODUCT 已 live 校准（或 PRODUCT=UNKNOWN 写明）
[ ] OUT / 禁止写清
[ ] 对话贴 CLAIM 块 + 声明「以 Issue 正文为准」
[ ] 评论「正式派发」只做指针
[ ] 日板只挂一张 IN_FLIGHT 主卡
```

---

## 6. 执行窗只认

```text
Issue 正文 > 聊天
CLAIM 后尽快首动作（合码 / 推码 / 装 tip）
回写只用卡内【回写模板】
MODE=SOLO：改→合→装→验 同一窗串行
卡住：## BLOCKED + 一行原因
```

### 开跑前校准（2 分钟）

```bash
git fetch origin main && git rev-parse origin/main   # → BASE
# 线上 PRODUCT（跳板 / 密码器机）:
# curl -sS http://127.0.0.1:18765/health  # 取 git_sha
# 写回 Issue CLAIM 块后再大干
```

---

## 7. 关卡卫生

```text
DEPLOYED + TEST 有结论且无后续 → close 或标下一阶段
禁止「已部署仍 open」僵尸完成卡
close 评论：原因 + tip/PR + 未宣称的 CLAIM
```

---

## 8. 向业主报告「已派卡」至少含

1. Issue 链接  
2. 完整 CLAIM 四行（含 BASE/PRODUCT）  
3. 一句目标  
4. **标准全文以 Issue 正文为准**

---

## 9. 权威与示例

| 文档 | 角色 |
|------|------|
| **本文件** | 格式 BINDING 真源 |
| [DAY-TASK-P0-PI-CUTOVER.md](./DAY-TASK-P0-PI-CUTOVER.md) | 现行填实示例 **T-P0-PI-CUTOVER** |
| [TEST-TASK-P0-PI-CUTOVER.md](./TEST-TASK-P0-PI-CUTOVER.md) | 点验对表（卡内 C 引用） |
| [MEMORY-RESET.md](./MEMORY-RESET.md) | 错误记忆（含废多窗） |
| [STAGE-PACKAGE-MODE.md](./STAGE-PACKAGE-MODE.md) | 单窗组织法 |
| [templates/DAY-TASK-ISSUE.md](./templates/DAY-TASK-ISSUE.md) | **指针** → 本文件（旧体例废） |

冲突：业主当轮书面 > **本文件** > HANDOFF-WB-PI > 聊天。

```
════════════════════════════════════════════════════════
BINDING · TASK-CARD-STANDARD · 2026-08-06
CLAIM + BASE + PRODUCT · 锁定句四行 · 单窗 SOLO · Issue 正文为准
════════════════════════════════════════════════════════
```
