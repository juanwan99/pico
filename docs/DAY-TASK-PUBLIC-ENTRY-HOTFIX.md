# 标准任务卡 · T-PUBLIC-ENTRY-HOTFIX

```
DOC: docs/DAY-TASK-PUBLIC-ENTRY-HOTFIX.md
TYPE: STANDARD-TASK-CARD
ID: T-PUBLIC-ENTRY-HOTFIX
STATUS: OPEN
DATE: 2026-08-07
PLAN: docs/PLAN-PUBLIC-WB-LOOP.md · H0
```

```text
════════════════════════════════════
标准任务卡 · T-PUBLIC-ENTRY-HOTFIX
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP
角色：公网止血 · 测→修→装→再测
RISK: 红（入口/TLS/反代/登录）
FAST: YES
仓：https://github.com/juanwan99/pico
载体回写：（Issue 填）
BASE：  81dadd7c804e09ff0bea0e91d518190251ff9825
PRODUCT：14615ba2c9fbbebfd3d8dd16a24188f10f310f4d（开跑校准）
关联：PLAN-PUBLIC-WB-LOOP · HANDOFF-WB-PI · #316（CLAIM 冻结）

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（测→修→装→再测）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【目标】
恢复 **公网浏览器入口** 可用：打开 → 登录 → 进壳 → 短聊一轮有回复。
人话：你从外网能进站干活的第一步；不完成不得谈六条 CLAIM。

【IN】
A 公网复现：https://pico.aivia.asia/login（多网络若可能）
B 机内对照：ssh pico-prod → loopback health + 容器/nginx 状态
C 根因分类：DNS / TLS / nginx / compose down / 证书 / 防火墙 / 上游 502
D 最小修复 + exact tip 部署（或仅运维配置，须可回写）
E 再测：浏览器登录 + 一句「你好」有回复 · ## TEST REPORT

【OUT】
- 只写「loopback 绿」当完成
- 自签 CLAIM-WB-DEGREE-WEB
- P2/P3 新功能插队
- 密钥进 Issue

【验收】
1. 公网 /login 稳定可达（非 TLS reset / 非无限加载）
2. 演示账号可登录进工作台
3. 短聊成功 · 失败则中文可读
4. health.git_sha 记录；runtime 仍 pi-agent（不破坏换核）
5. ## DEPLOYED（若有）+ ## TEST REPORT 公网路径

【CLAIM】
CLAIM T-PUBLIC-ENTRY-HOTFIX（SOLO）
BASE 81dadd7c804e09ff0bea0e91d518190251ff9825
PRODUCT 14615ba2c9fbbebfd3d8dd16a24188f10f310f4d
公网入口止血：登录+短聊（禁 loopback 冒充）

【回写】
## ROOT CAUSE
## MERGED / ## DEPLOYED（若有）
## TEST REPORT（公网）
CLAIM-WB-DEGREE-WEB: NO
下一刀: T-PUBLIC-SIX-BARS-UI
════════════════════════════════════
```
