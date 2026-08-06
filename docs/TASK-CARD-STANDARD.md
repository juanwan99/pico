# 标准任务卡 · 派卡铁律（Pico · BINDING）

```
DOC: docs/TASK-CARD-STANDARD.md
STATUS: BINDING · 总管派卡
DATE: 2026-08-06
SOURCE: edu-core docs/TASK-CARD-STANDARD.md 体例 + Pico SOLO / HANDOFF-WB-PI
ORG: docs/STAGE-PACKAGE-MODE.md · docs/MEMORY-RESET.md
```

> **口头摘要 ≠ 任务卡。** 聊天三行不能代替 Issue 正文。  
> **认领：Issue 正文 > 任何聊天摘要。**

---

## 1. 唯一合法体例

任务卡必须是 **Issue 正文**，外层 ` ```text ` 包裹，字段不可缺：

```text
════════════════════════════════════
标准任务卡 · T-<NAME>
════════════════════════════════════
执行窗：SOLO（唯一）          # 旧「窗口N」仅别名；日常禁止多窗并行编制
上下文：CLEAR | KEEP
角色：执行 / 总管核真源
RISK: 绿|黄|红
FAST: YES|NO
仓：https://github.com/juanwan99/pico
载体回写：https://github.com/juanwan99/pico/issues/<N>
BASE：  <main tip 40-char · 开跑前 gh 校准>
PRODUCT：<线上 health.git_sha 40-char · 开跑前校准；未知写 UNKNOWN+原因>
关联：PR #… · HANDOFF · MEMORY-RESET

【锁定句】
目标：…
方案：…
执行：单窗 SOLO …
不做：…

【你是谁】
【真源】
【目标】
【IN】
【OUT】
【验收】
【禁止】
【CLAIM】     # 唯一可复制三行：CLAIM / BASE / PRODUCT + 一句目标
【回写模板】
【合入】
════════════════════════════════════
```

### CLAIM 块（卡尾必有 · 可复制）

```text
CLAIM T-<NAME>（SOLO）
BASE <40-char>
PRODUCT <40-char>
<一句人话目标>
```

### 禁止当作「任务卡」

- 仅聊天表格/三行板/口令
- 只有 CLAIM 句没有 IN/OUT/验收
- 自创 TYPE 长文却缺 BASE/PRODUCT
- 把卡写在错误 Issue 却声称已派发
- 再拆成窗1+2+4 三张等待卡（SOLO 已废该编制）

---

## 2. 总管派卡检查清单

```text
[ ] 专用 Issue，标题「标准任务卡 · T-…」
[ ] 正文 = 完整 ```text 框
[ ] CLAIM 句唯一、可复制
[ ] 载体回写 URL = 该 Issue
[ ] BASE / PRODUCT 已 live 校准（gh + health）
[ ] OUT/禁止写清
[ ] 对话贴全文或「以 Issue 正文为准」+ 链接
[ ] 评论「正式派发」只做指针
```

---

## 3. 执行窗只认

```text
Issue 正文 > 聊天
CLAIM 后尽快首动作（合码/推码/装 tip）
回写只用卡内模板
MODE=SOLO：改→合→装→验 同一窗串行
```

---

## 4. 关卡卫生

```text
DEPLOYED + TEST PASS 且无后续 → close 或标下一阶段
禁止「已部署仍 open」僵尸完成卡
open 标准卡可控；# 日板只挂一张 IN_FLIGHT 主卡
```

---

## 5. 向业主报告「已派卡」至少含

1. Issue 链接  
2. 完整 CLAIM 三行（含 BASE/PRODUCT）  
3. 一句目标  
4. **标准全文以 Issue 正文为准**

冲突：业主当轮书面 > 本文件 > HANDOFF-WB-PI。
