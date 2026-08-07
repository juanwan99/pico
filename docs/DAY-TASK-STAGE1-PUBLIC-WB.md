# 标准任务卡 · T-STAGE1-PUBLIC-WB

```
DOC: docs/DAY-TASK-STAGE1-PUBLIC-WB.md
TYPE: STANDARD-TASK-CARD
ID: T-STAGE1-PUBLIC-WB
STATUS: OPEN
DATE: 2026-08-07
PLAN: docs/PLAN-STAGE1-PUBLIC-WB.md
ACCEPT: docs/ACCEPT-STAGE1-PUBLIC-WB.md
TEST: docs/TEST-TASK-STAGE1-PUBLIC-WB.md
```

```text
════════════════════════════════════
标准任务卡 · T-STAGE1-PUBLIC-WB
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP
角色：无人值守自我驱动 · 端到端测修装验 · 总管仅黄/红合与阶段核真源
RISK: 红（公网入口+产品六条路径）
FAST: YES（整包一卡；内部小任务串行，禁拆多窗）
仓：https://github.com/juanwan99/pico
载体回写：（Issue 创建后填）
BASE：  7b01e9848d8e70dc5e998ea3bddea47ed0b2895c
PRODUCT：14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
关联：PLAN/ACCEPT/TEST-STAGE1 · #318 并入 S1.1-2 · #316 CLAIM 冻结

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（测→修→装→验→自我验收 串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
唯一执行窗 SOLO，**无人值守自我驱动**：
按 S1.1→S1.11 顺序推进；每小任务自我验收；
未达 ACCEPT 文档 **EXCELLENT** 不得进入下一小任务；
自动修到优秀再晋级；整包完成写 STAGE1 VERDICT。
VERDICT_AUTHORITY: NONE（不自签 CLAIM-WB-DEGREE-WEB）。

【真源】
PLAN-STAGE1-PUBLIC-WB → ACCEPT-STAGE1-PUBLIC-WB
→ HANDOFF-WB-PI → MEMORY-RESET → 本卡正文 → GitHub 证据

【目标】
阶段一：公网入口下完成 WorkBuddy 六条任务路径（优秀级）。
人话：链接给人，能登录办多种真任务并拿到真文件。
出口：STAGE1_PUBLIC_WB=PASS；CLAIM-WB-DEGREE-WEB 仍为 NO。

【IN】
0 开跑：校准 BASE/PRODUCT；读 PLAN+ACCEPT 全文
A 串行小任务（每条循环：测→修→装→验→SELF-ACCEPT EXCELLENT）
  S1.1 公网 TLS+入口（证书+无警告 /login）
  S1.2 登录进壳
  S1.3 开放派活（当场交件题）
  S1.4 多步+真产物可下
  S1.5 同会话改一版
  S1.6 短答不硬塞文件
  S1.7 ≥3 Skill 可见可选并绑定
  S1.8 过程可见+UI 停止
  S1.9 历史/任务点回
  S1.10 失败诚实中文
  S1.11 pi-agent+DeepSeek 回归+tip
B 每条回写 ## S1.x SELF-ACCEPT（模板见 ACCEPT）
C 全 EXCELLENT 后 ## STAGE1 VERDICT + 六条总表
D 缺外部输入才 ## BLOCKED（白名单见 PLAN §2.3）

【OUT】
- PASS_WEAK 晋级下一题
- 「你好」冒充条 3/4
- 仅 loopback/API 宣称公网完成
- 自签 CLAIM-WB-DEGREE-WEB=YES
- 拆多窗 / Dify 门脸 / 双核 / 场景卷验收
- 阶段二打磨范围抢做导致六条未齐就收工
- 密钥进仓/Issue

【验收】
1. S1.1–S1.11 全部 grade=EXCELLENT（ACCEPT 逐条）
2. 六条总表全 YES，证据公网可复核
3. STAGE1_PUBLIC_WB: PASS 写入 Issue
4. CLAIM-WB-DEGREE-WEB: NO
5. tip/runtime 与 S1.11 一致

【禁止】
仅 pico · 禁 PROXY=1 主路径 · 禁裸露 18765/27017 · 禁打印 key
CI 红不合 · 假绿禁止 · 执行窗不自 PASS 产品终局

【CLAIM】
CLAIM T-STAGE1-PUBLIC-WB（SOLO）
BASE 7b01e9848d8e70dc5e998ea3bddea47ed0b2895c
PRODUCT 14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
阶段一公网六条任务包·仅EXCELLENT晋级·无人值守

【回写模板】
## S1.x SELF-ACCEPT（每条）
## STAGE1 VERDICT（包末）
## MERGED / ## DEPLOYED（有代码时）
## BLOCKED（仅白名单）
CLAIM-WB-DEGREE-WEB: NO

【合入】
黄档 CI 绿可合；入口/鉴权/runtime 默认语义升红总管审
执行窗 VERDICT_AUTHORITY: NONE
════════════════════════════════════
```
