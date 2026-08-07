# 标准任务卡 · T-STAGE2-WB-POLISH

```
DOC: docs/DAY-TASK-STAGE2-WB-POLISH.md
TYPE: STANDARD-TASK-CARD
ID: T-STAGE2-WB-POLISH
STATUS: OPEN
DATE: 2026-08-07
PLAN: docs/PLAN-STAGE2-WB-POLISH.md
ACCEPT: docs/ACCEPT-STAGE2-WB-POLISH.md
TEST: docs/TEST-TASK-STAGE2-WB-POLISH.md
PRIOR: #320 STAGE1 PASS
```

```text
════════════════════════════════════
标准任务卡 · T-STAGE2-WB-POLISH
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP
角色：无人值守自我驱动 · 打磨+证据 · 业主独签 CLAIM
RISK: 红（产品体感与 CLAIM 证据）
FAST: YES（整包一卡；S2.0–S2.11 串行）
仓：https://github.com/juanwan99/pico
载体回写：（Issue 填）
BASE：  63d11e7a0773a8c83bc144b77413b4d13f627dba
PRODUCT：14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
关联：#320 STAGE1 · #316 CLAIM · PLAN/ACCEPT/TEST-STAGE2

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（测→修→装→验→自我验收 串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
SOLO 无人值守：S2.0→S2.10 仅 EXCELLENT 晋级；
S2.10 后贴证据请业主 OWNER DECISION；
YES 后做 S2.11 真源回写；NO 则缺口清单。
禁止自签 CLAIM-WB-DEGREE-WEB=YES。

【真源】
PLAN-STAGE2 → ACCEPT-STAGE2 → HANDOFF-WB-PI → #320 → 本卡 → GitHub

【目标】
阶段二：公网打磨到愿天天用 + 证据包 + 业主签章流程。
出口：STAGE2_WB_POLISH=PASS；CLAIM 仅业主决。

【IN】
0 读 PLAN+ACCEPT；校准 BASE/PRODUCT
S2.0 阶段一回归抽检
S2.1 差距清单
S2.2 交件纪律默认硬（修 S1.5 黄）
S2.3 长任务手感
S2.4 产物露出
S2.5 失败+重试
S2.6 难任务 ≥3 题 ≥2/3 交差
S2.7 材料再问轻量
S2.8 移动端 ~390
S2.9 诚实边界文档
S2.10 公网证据包 + 请业主签
S2.11 业主 YES 后 STATE/HANDOFF 回写
每条 ## S2.x SELF-ACCEPT · 包末 ## STAGE2 VERDICT

【OUT】
PASS_WEAK 晋级 · 自签 CLAIM=YES · 削弱六条
P3 大功能插队 · 像素/workDir 宣称 · 密钥进 Issue · 多窗

【验收】
1. S2.0–S2.10 全 EXCELLENT
2. STAGE2_WB_POLISH: PASS
3. 业主 OWNER DECISION 已请（YES/NO/REVISE）
4. S2.11：YES 则 EXCELLENT 回写；NO 则 SKIP+缺口
5. 执行窗未写 CLAIM=YES

【禁止】
仅 pico · 禁 PROXY=1 · 禁裸露端口 · 禁打印 key · 假绿禁止

【CLAIM】
CLAIM T-STAGE2-WB-POLISH（SOLO）
BASE 63d11e7a0773a8c83bc144b77413b4d13f627dba
PRODUCT 14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
阶段二打磨+证据包·仅EXCELLENT·业主独签CLAIM

【回写模板】
## S2.x SELF-ACCEPT
## STAGE2 VERDICT
## OWNER DECISION（业主）
## MERGED / ## DEPLOYED
## BLOCKED
CLAIM-WB-DEGREE-WEB: PENDING|NO（执行窗）

【合入】
黄档可合；runtime 默认语义升红总管审
VERDICT_AUTHORITY: NONE（产品 CLAIM）
════════════════════════════════════
```
