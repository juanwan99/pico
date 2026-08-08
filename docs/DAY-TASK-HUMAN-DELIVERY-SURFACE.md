# 标准任务卡 · T-HUMAN-DELIVERY-SURFACE

```text
════════════════════════════════════
标准任务卡 · T-HUMAN-DELIVERY-SURFACE
════════════════════════════════════
执行窗：SOLO
角色：人本交付面 · 根因修复 · 禁机审进用户窗
RISK: 红 · FAST: YES
仓：https://github.com/juanwan99/pico
文档：docs/RCA-HUMAN-DELIVERY-SURFACE.md
      docs/PLAN-HUMAN-DELIVERY-SURFACE.md
载体：（Issue）

【锁定句】
目标：Web 上 WorkBuddy 程度 · 以人为本
方案：Pico + Pi + DeepSeek
执行：人包 final_text · 下载一等公民 · UI 一票否决
不做：美化 L0 仍进聊天 · 无下载装 PASS · 考题特判

【你是谁】
按 RCA 修 R1–R6。用户窗只给人包+下载；机审进日志；
公网登录 UI 拿不到文件 = FAIL。CLAIM-WB: NO。

【IN】
HDS1 双轨提示词
HDS2 final_text 硬门（剥源码/剥机审/补文件名）
HDS3 账本→UI 下载芯片
HDS4 verify 对内
HDS5 审查尺子文档
HDS6 公网 UI 真登录回归（孟德尔类 + 闲聊）

【验收】
主回复无机审字段与全量 HTML
UI 可下载打开能用
CLAIM-WB: NO

【CLAIM】
CLAIM T-HUMAN-DELIVERY-SURFACE（SOLO）
人包交付·下载一等公民·机审退后台·UI一票否决·CLAIM-NO
════════════════════════════════════
```
